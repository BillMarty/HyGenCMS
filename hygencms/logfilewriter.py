# -*- coding: utf-8 -*-
"""
Created on Wed Jul 06 08:18:52 2016

@author: mwest
"""
import os
import subprocess
import sys
import time
from datetime import datetime
from subprocess import check_call, CalledProcessError, STDOUT

import monotonic

from . import gpio
from . import pins
from . import utils
from .asynciothread import AsyncIOThread

if sys.version_info[0] == 3:
    import queue
elif sys.version_info[0] == 2:
    import Queue as queue

# Location to store log files if a USB is not available
base_dir = '/home/hygen'


class FileWriter(AsyncIOThread):
    def __init__(self, config, handlers, log_queue, csv_header):
        """
        Initialize a filewriter which writes to file whatever is put
        on its queue.

        Can raise:
        - ValueError for invalid config
        - IOError (Python < 3.3) or OSError (Python >= 3.3) for inaccessible file
        """
        # General config for the thread
        super(FileWriter, self).__init__(handlers)

        # Specific config for the logger
        self.check_config(config)

        self.relative_directory = config['ldir']  # Relative directory on USB
        self._queue = log_queue
        self._f = open(os.devnull, 'w')
        self._csv_header = csv_header

        self.drive_mounted = bool(self.usb_mounted())

        self._safe_to_remove = None
        self._usb_activity = None

    ########################################################
    # Properties
    ########################################################

    @property
    def safe_to_remove(self):
        """Safe to remove LED"""
        return self._safe_to_remove

    @safe_to_remove.setter
    def safe_to_remove(self, value):
        if value:
            gpio.write(pins.USB_LED, gpio.HIGH)
            self._safe_to_remove = True
        else:
            gpio.write(pins.USB_LED, gpio.LOW)
            self._safe_to_remove = False

    @safe_to_remove.deleter
    def safe_to_remove(self):
        gpio.write(pins.USB_LED, gpio.LOW)
        del self._safe_to_remove

    @property
    def usb_activity(self):
        """USB Activity LED"""
        return self._usb_activity

    @usb_activity.setter
    def usb_activity(self, value):
        if value:
            gpio.write(pins.DISK_ACT_LED, gpio.HIGH)
            self._usb_activity = True
        else:
            gpio.write(pins.DISK_ACT_LED, gpio.LOW)
            self._usb_activity = False

    @usb_activity.getter
    def usb_activity(self):
        return self._usb_activity

    @usb_activity.deleter
    def usb_activity(self):
        gpio.write(pins.DISK_ACT_LED, gpio.LOW)
        del self._usb_activity

    #######################################################
    # Methods
    #######################################################

    def __del__(self):
        """
        Close the file object on object deletion.
        """
        try:
            if self._f:
                self._f.close()
        except IOError:
            pass

    @staticmethod
    def check_config(config):
        """
        Check that the configuration map is complete. Throw a
        ValueError if any configuration values are missing from
        the dictionary.
        """
        required_config = ['ldir']
        for val in required_config:
            if val not in config:
                raise ValueError("Missing required config value: " + val)
        # If we get to this point, the required values are present
        return True

    def run(self):
        """
        Overrides Thread.run. Run the FileWriter.
        """
        next_run = {
            0.5: 0,
            1.0: 0,
            10.0: 0,
            60.0: 0,
        }
        prev_hour = -1  # Always start a new file to start
        while not self.cancelled:
            # noinspection PyBroadException
            try:
                now = monotonic.monotonic()

                # Twice a second
                if now >= next_run[0.5]:
                    # Check if eject button is pressed
                    if gpio.read(pins.USB_SW) == gpio.LOW:
                        # If eject button pressed, close file and unmount
                        self.unmount_usb()

                    # Schedule next run
                    next_run[0.5] = now + 0.5

                # Every second
                if now >= next_run[1.0]:
                    # Check whether USB is plugged in, and mounted
                    device = self.usb_plugged()
                    drive = self.usb_mounted()

                    # If we've unplugged it, turn off light
                    if not device and self.safe_to_remove:
                        # Reset safe to remove light
                        self.safe_to_remove = False
                        self.drive_mounted = False

                    # If we've mounted a new drive
                    if drive and not self.drive_mounted:
                        # Get new file (presumably on USB)
                        self._f.close()
                        self._f = self._get_new_logfile()
                        self._write_line(self._csv_header)
                        self.drive_mounted = bool(drive)

                    # Print out lines
                    more_items = True
                    while more_items:
                        try:
                            line = self._queue.get(False)
                        except queue.Empty:
                            more_items = False
                        else:
                            self._write_line(line)

                    # Schedule next run
                    next_run[1.0] = now + 1.0

                # Every 10 seconds
                if now >= next_run[10.0]:
                    # Disable the safe-to-remove light if the drive is out
                    if self.safe_to_remove:
                        if self.usb_plugged():
                            pass  # TODO remount the drive
                        else:
                            self.safe_to_remove = False

                    # Schedule next run
                    next_run[10.0] = now + 10.0

                # Every minute
                if now >= next_run[60.0]:
                    # Check to see whether it's a new hour
                    # and open a new file
                    hour = datetime.now().hour
                    if prev_hour != hour:
                        self._f.close()
                        self._f = self._get_new_logfile()
                        prev_hour = hour
                        self._write_line(self._csv_header)

                    # Schedule next run
                    next_run[60.0] = now + 60.0

                # TODO Poll GPIOs in a separate thread

                time.sleep(0.01)
            except Exception as e:
                utils.log_exception(self._logger, e)

    @staticmethod
    def usb_mounted():
        """
        Return the path to whatever drive is mounted, or None
        :return: '/media/[drive]' or None
        """
        # Check for USB directory
        mount_list = str(subprocess.check_output(['mount']))

        position = mount_list.find('/dev/sd')
        if position == -1:
            return None

        line = mount_list[position:].splitlines()[0]
        position = line.find("/media/sd")
        if position == -1:
            return None

        path = line[position:].split()[0]

        return path

    def usb_plugged(self):
        """Return True if a USB device is plugged in"""
        try:
            output = str(subprocess.check_output(['ls', '/dev']))
        except CalledProcessError:
            self._logger.debug("Error in ls.")
            return False
        else:
            position = output.rfind('sd')
            if position >= 0:
                # Get the device fil
                return '/dev/' + output[position:].split()[0]
            else:
                return False

    def unmount_usb(self):
        """
        Unmount the currently mounted USB. Close the current file
        and open a new file.
        :return: None
        """
        if not self.drive_mounted:
            return
        else:
            drive = self.usb_mounted()

        # Close file and unmount
        self._f.close()
        tries = 0
        while self.drive_mounted and tries < 100:
            try:
                check_call(["pumount", drive], stderr=STDOUT)
            except CalledProcessError as e:
                self._logger.critical("Could not unmount "
                                      + drive
                                      + ". Failed with error "
                                      + str(e.output))
                tries += 1
            else:
                self.safe_to_remove = True
                self.drive_mounted = False
            time.sleep(0.01)
        self._f = self._get_new_logfile()

    def get_directory(self):
        """
        Get the directory to store logs to.
        """
        drive = self.usb_mounted()

        if drive is None:
            return os.path.join(base_dir, self.relative_directory)
        else:
            log_directory = os.path.join(drive, self.relative_directory)

        # Make any necessary paths
        try:
            os.makedirs(log_directory)
        except OSError:
            # Directory already exists
            pass
        return log_directory

    def _get_new_logfile(self):
        """
        Open a new logfile for the current hour. If opening the file fails,
        returns the null file.
        """
        directory = self.get_directory()
        if not os.path.isdir(directory):
            return open(os.devnull)  # If the directory doesn't exist, fail

        # Find unique file name for this hour
        now = datetime.now()
        hour = now.strftime("%Y-%m-%d_%H")
        i = 0
        while os.path.exists(
                os.path.join(directory, hour + "_run%d.csv" % i)):
            i += 1

        file_path = os.path.join(
            directory,
            hour + "_run%d.csv" % i)

        # Try opening the file, else open the null file
        try:
            f = open(file_path, 'w')
        except IOError:
            self._logger.critical("Failed to open log file: %s" % file_path)
            return open(os.devnull, 'w')  # return a null file
        else:
            return f

    def _write_line(self, line):
        """
        Write a line to the currently open file, ending in a single new-line.
        """
        try:
            if self.drive_mounted:
                self.usb_activity = True
            if line[-1] == '\n':
                self._f.write(line)
            else:
                self._f.write(line + '\n')
            if self.drive_mounted:
                self.usb_activity = False
        except (IOError, OSError):
            self._logger.error("Could not write to log file")
