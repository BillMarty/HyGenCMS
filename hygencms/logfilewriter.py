# -*- coding: utf-8 -*-
"""
Created on Wed Jul 06 08:18:52 2016

@author: mwest
"""
import os
import sys
import time
from datetime import datetime
from subprocess import check_call, CalledProcessError

from . import gpio
from . import pins
from . import utils
from .asynciothread import AsyncIOThread

if sys.version_info[0] == 3:
    import queue
elif sys.version_info[0] == 2:
    import Queue as queue


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
        self.log_directory = self.get_directory()

        self._queue = log_queue
        self._f = open(os.devnull, 'w')
        self._csv_header = csv_header

        self.eject_button = pins.USB_SW
        self._cancelled = False

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
        Check that the config is complete. Throw a ValueError if any
        configuration values are missing from the dictionary.
        """
        required_config = ['ldir']
        for val in required_config:
            if val not in config:
                raise ValueError("Missing required config value: " + val)
        # If we get to this point, the required values are present
        return True

    @staticmethod
    def usb_plugged():
        """
        Return the path to whatever drive is plugged in, or None
        :return: '/media/[drive]' or None
        """
        # Check for USB directory
        media = os.listdir('/media')

        drive = None
        drives = ['sda', 'sda1', 'sda2']  # Possible mount points
        for d in drives:
            if d in media:
                drive = os.path.join('/media', d)
                break

        return drive

    def get_directory(self):
        """
        Get the directory to store logs to.
        """
        drive = self.usb_plugged()

        if drive is None:
            return os.path.join('/home/hygen', self.relative_directory)
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

        # Find unique file name for this hour
        now = datetime.now()
        hour = now.strftime("%Y-%m-%d_%H")
        i = 0
        while os.path.exists(
                os.path.join(directory, hour + "_run%d.csv" % i)):
            i += 1

        file_path = os.path.join(
            self.log_directory,
            hour + "_run%d.csv" % i)

        # Try opening the file, else open the null file
        try:
            f = open(file_path, 'w')
        except IOError:
            self._logger.critical("Failed to open log file: %s" % file_path)
            return open(os.devnull, 'w')  # return a null file
        return f

    def _write_line(self, line):
        """
        Write a line to the currently open file, ending in a single new-line.
        """
        try:
            gpio.write(pins.DISK_ACT_LED, gpio.HIGH)
            if line[-1] == '\n':
                self._f.write(line)
            else:
                self._f.write(line + '\n')
            gpio.write(pins.DISK_ACT_LED, gpio.LOW)
        except (IOError, OSError):
            self._logger.error("Could not write to log file")

    def run(self):
        """
        Overrides Thread.run. Run the FileWriter
        """
        prev_hour = datetime.now().hour - 1  # ensure starting file

        while not self._cancelled:
            # noinspection PyBroadException
            try:
                hour = datetime.now().hour
                if prev_hour != hour:
                    self._f.close()
                    self._f = self._get_new_logfile()
                    prev_hour = hour
                    self._write_line(self._csv_header)

                # Get lines to print
                more_items = True
                while more_items:
                    try:
                        line = self._queue.get(False)
                    except queue.Empty:
                        more_items = False
                    else:
                        self._write_line(line)

                # TODO Poll GPIOs in a separate thread
                if gpio.read(pins.USB_SW) == gpio.LOW:
                    drive = self.usb_plugged()
                    mounted = bool(drive)
                    tries = 0
                    while mounted and tries < 100:
                        try:
                            check_call(["pumount", drive])
                        except CalledProcessError as e:
                            self._logger.critical("Could not unmount "
                                                  + drive
                                                  + ". Failed with error "
                                                  + str(e.output))
                            tries += 1
                        else:
                            gpio.write(pins.USB_LED, gpio.HIGH)
                            mounted = False
                        time.sleep(0.01)

                if not os.path.exists(self.log_directory):
                    self._f.close()
                    self._f = self._get_new_logfile()
                    self._write_line(self._csv_header)

                time.sleep(0.1)
            except Exception as e:
                utils.log_exception(self._logger, e)

    def cancel(self):
        """
        Cancels the thread, allowing it to be joined.
        """
        self._logger.info("Stopping " + str(self))
        self._cancelled = True
