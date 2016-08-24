import os
import queue
import time
from datetime import datetime
from os import path

from . import gpio, pins, utils
from . import usbdrive
from .asyncio import AsyncIOThread


class FileWriter(AsyncIOThread):
    """
    Write lines from a queue into log files in a separate thread.

    This thread polls a queue every second, writing the lines to a
    file. Starts a new file every hour. Checks for pressing of the
    eject button, and when it is pressed, closes the file and unmounts
    the drive. Continues logging data onto the local drive.

    If a drive is plugged in, begins logging files on drive again.
    """
    # Location to store log files if a USB is not available
    fallback_directory = '/home/hygen'

    def __init__(self, config, handlers, log_queue, bms_queue, csv_header):
        """
        Initialize a filewriter which writes to file whatever is put
        on its queue.

        Can raise:
        - ValueError for invalid config
        - IOError (Python < 3.3) or OSError (Python >= 3.3) for inaccessible file

        :param config:
            The configuration map for the FileWriter

        :param handlers:
            All the log handlers to log to

        :param log_queue:
            The queue to pull csv lines off

        :param bms_queue:
            The queue from which to pull bms stream lines.

        :param csv_header:
            The header to put at the top of each file

        :exception ValueError:
            Raised if the configuration map is missing values

        :exception IOError:
        :exception OSError:
            Could not open file
        """
        # General config for the thread
        super(FileWriter, self).__init__(handlers)

        # Specific config for the logger
        self.check_config(config)

        self.relative_directory = config['ldir']  # Relative directory on USB
        self._log_queue = log_queue
        self._bms_queue = bms_queue
        self._csv_header = csv_header
        self._header_changed = False

        # Set the base directory to use
        mounted_directory = usbdrive.mount_point()
        if mounted_directory:
            self.base_directory = mounted_directory
        else:
            self.base_directory = self.fallback_directory

        # Open file
        self._log_file = open(os.devnull, 'w')
        self._bms_file = open(os.devnull, 'w')

        # Private variables behind properties
        self._safe_to_remove = None
        self._usb_activity = None

        # Initialize LEDs to off
        self.safe_to_remove = False
        self.usb_activity = False

        # Flags set by main thread
        self.eject_drive = None
        self.mount_drive = None

    ########################################################
    # Properties
    ########################################################

    @property
    def safe_to_remove(self):
        """Property for Safe to remove LED"""
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
        """Property for USB Activity LED"""
        return self._usb_activity

    @usb_activity.setter
    def usb_activity(self, value):
        if value:
            gpio.write(pins.DISK_ACT_LED, gpio.HIGH)
            self._usb_activity = True
        else:
            gpio.write(pins.DISK_ACT_LED, gpio.LOW)
            self._usb_activity = False

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
            if self._log_file:
                self._log_file.close()
            if self._bms_file:
                self._bms_file.close()
        except IOError:
            pass

    @staticmethod
    def check_config(config):
        """
        Check that the configuration map is complete.

        :param config:
            The configuration map for the FileWriter

        :exception ValueError:
            Raises if the configuration map is invalid.
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
        prev_hour = -1  # Always start a new file to start

        while not self.cancelled:
            # noinspection PyBroadException
            try:
                hour = datetime.now().hour
                if self.mount_drive:
                    self._log_file.close()
                    self._bms_file.close()
                    usbdrive.mount(self.mount_drive)

                    self.base_directory = self.mount_drive
                    self._log_file = self.new_logfile()
                    self._bms_file = self.new_bmsfile()
                    self._write_line(self._log_file, self._csv_header)
                    self.mount_drive = None

                elif self.eject_drive:
                    self._log_file.close()
                    self._bms_file.close()
                    usbdrive.unmount_mounted()
                    self.safe_to_remove = True

                    self.base_directory = self.fallback_directory
                    self._log_file = self.new_logfile()
                    self._bms_file = self.new_bmsfile()
                    self._write_line(self._log_file, self._csv_header)
                    self.eject_drive = False

                elif hour != prev_hour:
                    self._log_file.close()
                    self._log_file = self.new_logfile()
                    self._write_line(self._log_file, self._csv_header)

                    self._bms_file.close()
                    self._bms_file = self.new_bmsfile()

                    prev_hour = hour

                elif self._header_changed:
                    # Get all the lines before the None flag
                    more = True
                    while more:
                        try:
                            line = self._log_queue.get(False)
                        except queue.Empty:
                            # Sleep if there aren't any lines
                            time.sleep(0.1)
                        else:
                            # Handle None flag
                            if line is None:
                                more = False
                            else:
                                self._write_line(self._log_file, line)

                    # Close file and get new one (with new CSV header)
                    self._log_file.close()
                    self._log_file = self.new_logfile()
                    self._write_line(self._log_file, self._csv_header)
                    self._header_changed = False

                # Print out lines
                self.print_from_queue(self._log_file, self._log_queue)
                self.print_from_queue(self._bms_file, self._bms_queue)

                time.sleep(0.1)
            except Exception as e:
                utils.log_exception(self._logger, e)

    def print_from_queue(self, file, q):
        """
        Write all the lines from a queue to file.

        :param file:
            File to write.

        :param q:
            Queue to source lines.
        """
        more = True
        while more:
            try:
                line = q.get(False)
            except queue.Empty:
                more = False
            else:
                self._write_line(file, line)

    def _write_line(self, file, line):
        """
        Write a line to the currently open file, ending in a single new-line.

        :param line:
            Line to write to file.
        """
        if file.name.startswith('/media'):
            drive = True
        else:
            drive = False
        try:
            if drive:
                self.usb_activity = True
            if line[-1] == '\n':
                file.write(line)
            else:
                file.write(line + '\n')
            if drive:
                self.usb_activity = False
        except (IOError, OSError):
            self._logger.error("Could not write to log file")

    def get_directory(self):
        """
        Get the directory to store logs to.

        :return:
            Either a folder in the fallback directory, or a
            folder on the mounted drive.
        """
        drive = usbdrive.mount_point()

        if drive is None:
            log_directory = path.join(self.fallback_directory,
                                      self.relative_directory)
        else:
            log_directory = path.join(drive,
                                      self.relative_directory)

        # Make any necessary paths
        try:
            os.makedirs(log_directory)
        except OSError:
            # Directory already exists
            pass
        return log_directory

    def new_logfile(self):
        """
        Open a new logfile for the current hour. If opening the file fails,
        returns the null file.

        :return:
            A writeable file object from open(), either a log file or
            the null file.
        """
        directory = self.get_directory()
        if not path.isdir(directory):
            return open(os.devnull)  # If the directory doesn't exist, fail

        # Find unique file name for this hour
        now = datetime.now()
        base_file_name = now.strftime("%Y-%m-%d_%H")
        i = 0
        while path.exists(path.join(directory,
                                    base_file_name + "_run%d.csv" % i)):
            i += 1

        file_path = os.path.join(
            directory,
            base_file_name + "_run%d.csv" % i)

        # Try opening the file, else open the null file
        try:
            f = open(file_path, 'w')
        except IOError:
            self._logger.critical("Failed to open log file: %s" % file_path)
            return open(os.devnull, 'w')  # return a null file
        else:
            self._logger.info("Opened new log file at %s" % f.name)
            return f

    def new_bmsfile(self):
        """
        Open a new file for the BMS stream for the current hour. If
        opening the file fails, returns the null file.

        :return:
            A writeable file object from open(), either a BMS file or
            the null file.
        """
        directory = self.get_directory()
        if not path.isdir(directory):
            return open(os.devnull)  # If the directory doesn't exist, fail

        # Find unique file name for this hour
        now = datetime.now()
        base_file_name = now.strftime("%Y-%m-%d_%H")
        i = 0
        while path.exists(path.join(directory,
                                    base_file_name + "_bms%d.csv" % i)):
            i += 1

        file_path = os.path.join(
            directory,
            base_file_name + "_bms%d.csv" % i)

        # Try opening the file, else open the null file
        try:
            f = open(file_path, 'w')
        except IOError:
            self._logger.critical("Failed to open bms file: %s" % file_path)
            return open(os.devnull, 'w')  # return a null file
        else:
            self._logger.info("Opened new BMS file at %s" % f.name)
            return f

    def update_csv_header(self, csv_header):
        """
        Update the CSV header used for logfiles. Open new logfiles.

        :param csv_header:
        :return:
        """
        self._csv_header = csv_header
        self._header_changed = True
