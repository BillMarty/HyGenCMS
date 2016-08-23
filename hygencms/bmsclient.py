"""
This module provides utilities for dealing with the Becket BMS. The
BmsClient class can run as a thread to get Bms data. The BmsModule
and BmsStatus classes parse the module and status messages, reflecting
the current state of the BMS in their member variables and properties.
"""

import time

import serial

from . import utils
from .asyncio import AsyncIOThread
from .utils import PY3

if PY3:
    import queue
else:
    import Queue as queue


class BmsModule:
    """
    This class holds the information contained in a Module status report
    from the Beckett BMS.
    """

    def __init__(self, module_id, line=None):
        self.id = module_id
        self.state = None
        self.soc = None
        self.min_cell_temp = None
        self.avg_cell_temp = None
        self.max_cell_temp = None
        self.module_voltage = None
        self.min_cell_voltage = None
        self.avg_cell_voltage = None
        self.max_cell_voltage = None
        self.current = None
        self.alarm_and_status = 0
        self.max_front_power_connector_temp = None

        if line:
            self.update(line)

    def __str__(self):
        return ("BMS Module {:d}\n".format(self.id)
                + "cur: {:5.1f}\n".format(self.current)
                + "SoC: {:5d}%\n".format(self.soc)
                + "     {:5s} {:5s} {:5s}\n".format('min', 'avg', 'max')
                + "temp {:5d} {:5d} {:5d}\n".format(self.min_cell_temp,
                                                    self.avg_cell_temp,
                                                    self.max_cell_temp)
                + "volt {:5.3f} {:5.3f} {:5.3f}\n".format(self.min_cell_voltage,
                                                          self.avg_cell_voltage,
                                                          self.max_cell_voltage)
                )

    ############################################
    # Properties
    ############################################

    @property
    def temperature_warning(self):
        return bool(self.alarm_and_status & (1 << 0))

    @property
    def temperature_fault(self):
        return bool(self.alarm_and_status & (1 << 1))

    @property
    def high_current_warning(self):
        return bool(self.alarm_and_status & (1 << 2))

    @property
    def high_current_fault(self):
        return bool(self.alarm_and_status & (1 << 3))

    @property
    def high_voltage_warning(self):
        return bool(self.alarm_and_status & (1 << 4))

    @property
    def high_voltage_fault(self):
        return bool(self.alarm_and_status & (1 << 5))

    @property
    def low_voltage_warning(self):
        return bool(self.alarm_and_status & (1 << 6))

    @property
    def low_voltage_fault(self):
        return bool(self.alarm_and_status & (1 << 7))

    @property
    def cell_low_voltage_fault(self):
        return bool(self.alarm_and_status & (1 << 8))

    @property
    def charge_low_warning(self):
        return bool(self.alarm_and_status & (1 << 12))

    @property
    def communication_error(self):
        return bool(self.alarm_and_status & (1 << 13))

    @property
    def communication_fault(self):
        return bool(self.alarm_and_status & (1 << 14))

    @property
    def under_volt_disable(self):
        return bool(self.alarm_and_status & (1 << 16))

    @property
    def over_volt_disable(self):
        return bool(self.alarm_and_status & (1 << 17))

    @property
    def cell_0_balancing(self):
        return bool(self.alarm_and_status & (1 << 24))

    @property
    def cell_1_balancing(self):
        return bool(self.alarm_and_status & (1 << 25))

    @property
    def cell_2_balancing(self):
        return bool(self.alarm_and_status & (1 << 26))

    @property
    def cell_3_balancing(self):
        return bool(self.alarm_and_status & (1 << 27))

    @property
    def cell_4_balancing(self):
        return bool(self.alarm_and_status & (1 << 28))

    @property
    def cell_5_balancing(self):
        return bool(self.alarm_and_status & (1 << 29))

    @property
    def cell_6_balancing(self):
        return bool(self.alarm_and_status & (1 << 30))

    ############################################
    # Methods
    ############################################

    def update(self, line):
        """
        Takes a module status string.

        :param line:
            Periodic Module status report. Type ``str``

        :return:
            :const:`None`

        :exception ValueError:
            If the line is not valid.
        """
        if type(line) not in [str, bytes]:
            raise ValueError("Passed the wrong type for line")

        line = str(line)

        if len(line) < 125:
            raise ValueError("Line is too short")

        if line[4] != 'M':
            raise ValueError("Line is not a module status report")

        if int(line[17:19]) != self.id:
            raise ValueError("Line does not have same ID as this module")

        self.state = line[20]
        self.soc = int(line[22:25])
        self.min_cell_temp = int(line[26:29])
        self.avg_cell_temp = int(line[30:33])
        self.max_cell_temp = int(line[34:37])
        self.module_voltage = int(line[38:44]) / 1000.0
        self.min_cell_voltage = int(line[45:51]) / 1000.0
        self.avg_cell_voltage = int(line[52:58]) / 1000.0
        self.max_cell_voltage = int(line[59:65]) / 1000.0
        self.current = int(line[66:71]) / 10.0
        self.alarm_and_status = int(line[72:80], base=16)
        self.max_front_power_connector_temp = int(line[109:112])


class BmsStatus:
    """
    This class holds the information contained in a "periodic string status
    report" (ES-0092 - Serial Bus Communication Protocol Overview, 7.1).

    It provides methods to parse strings, and properties to access all the
    data.
    """

    def __init__(self, line=None):
        self.state = None
        self.soc = None
        self.temperature = None
        self.voltage = None
        self.current = None
        self.alarm_and_status = 0
        self.watt_hours_to_full_discharge = None
        self.watt_hours_to_full_charge = None
        self.min_cell_voltage = None
        self.max_cell_voltage = None
        self.front_power_connector_temperature = None

        self.modules = {}

        if line:
            self.update(line)

    def __str__(self):
        s = ("BMS Status\n"
             + "volt: {:5.3f}\n".format(self.voltage)
             + "cur:  {:5.1f}\n".format(self.current)
             + "SoC:  {:5d}%\n".format(self.soc)
             + "Temp: {:5d} degC\n".format(self.temperature)
             + "     {:5s} {:5s}\n".format('min', 'max')
             + "volt {:5.3f} {:5.3f}\n".format(self.min_cell_voltage,
                                               self.max_cell_voltage)
             + "modules:\n"
             )
        module_strings = [str(m) for m in self.modules.values()]
        return s + '\n'.join(module_strings)

    ###############################################
    # Alarms and Warnings
    ###############################################
    @property
    def temperature_warning(self):
        return bool(self.alarm_and_status & (1 << 0))

    @property
    def temperature_fault(self):
        return bool(self.alarm_and_status & (1 << 1))

    @property
    def high_current_warning(self):
        return bool(self.alarm_and_status & (1 << 2))

    @property
    def high_current_fault(self):
        return bool(self.alarm_and_status & (1 << 3))

    @property
    def high_voltage_warning(self):
        return bool(self.alarm_and_status & (1 << 4))

    @property
    def high_voltage_fault(self):
        return bool(self.alarm_and_status & (1 << 5))

    @property
    def low_voltage_warning(self):
        return bool(self.alarm_and_status & (1 << 6))

    @property
    def low_voltage_fault(self):
        return bool(self.alarm_and_status & (1 << 7))

    @property
    def cell_low_voltage_nonrecoverable_fault(self):
        return bool(self.alarm_and_status & (1 << 8))

    @property
    def charge_low_warning(self):
        return bool(self.alarm_and_status & (1 << 12))

    @property
    def module_communication_error(self):
        return bool(self.alarm_and_status & (1 << 13))

    @property
    def module_communication_fault(self):
        return bool(self.alarm_and_status & (1 << 14))

    @property
    def bms_selfcheck_warning(self):
        return bool(self.alarm_and_status & (1 << 15))

    @property
    def under_volt_disable(self):
        return bool(self.alarm_and_status & (1 << 16))

    @property
    def over_volt_disable(self):
        return bool(self.alarm_and_status & (1 << 17))

    @property
    def string_contactor_or_fet_on(self):
        return bool(self.alarm_and_status & (1 << 31))

    ######################################
    # Methods
    ######################################

    def update(self, line):
        """
        Update the components of the status with a new line
        from the BMS serial.

        :param line:
            The periodic string or module status report or from the BMS.
            Type ``bytes`` or ``str``.

        :return:
            :const:`None`

        :exception ValueError:
            If the argument is the wrong type, or too short.
        """
        if type(line) not in [str, bytes]:
            raise ValueError("Passed the wrong type for line")

        line = str(line)

        if len(line) < 125:
            raise ValueError("Line is too short")

        if line[4] == 'S':
            self._update_status(line)
        elif line[4] == 'M':
            self._update_module(line)
        else:
            raise ValueError("Not one of update status or update module")

    def _update_status(self, line):
        """
        Update the components of the top-level status with a "module
        status report" from the BMS.

        :param line:
            The periodic string line. Type ``str``

        :return:
            :const:`None`
        """
        self.state = line[17]
        self.soc = int(line[19:22])
        self.temperature = int(line[23:26])
        self.voltage = int(line[27:33]) / 1000.0
        self.current = int(line[34:39]) / 10.0
        self.alarm_and_status = int(line[40:48], base=16)
        self.watt_hours_to_full_discharge = int(line[77:83])
        self.watt_hours_to_full_charge = int(line[84:90])
        self.min_cell_voltage = int(line[91:97]) / 1000.0
        self.max_cell_voltage = int(line[98:104]) / 1000.0
        self.front_power_connector_temperature = int(line[105:107])

    def _update_module(self, line):
        """
        Update the module with a module status report from the BMS.

        :param line:
            The periodic module status report. Type ``str``

        :return:
            :const:`None`

        :exception ValueError:
            If the wrong type is used, or an invalid line.
        """
        module_id = int(line[17:19])
        try:
            module = self.modules[module_id]
            module.update(line)
        except KeyError:
            module = BmsModule(module_id, line)
            self.modules[module_id] = module


class BmsClient(AsyncIOThread):
    """
    This class provides a thread to get data from the Becket battery
    management system. The get_data and
    print_data methods will read the battery percentage at that moment
    and return or print it.
    """

    def __init__(self, bconfig, handlers, bms_queue):
        """
        Initialize the bms client from the configuration values.

        :param bconfig:
            Configuration map for the BmsClient

        :param handlers:
            List of log handlers.

        :param bms_queue:
            A queue to put the lines from the BMS.

        :exception IOError:
            In case the serial port does not open successfully

        :exception SerialException:
            In case the serial port does not open successfully

        :exception ValueError:
            Will be raised when configuration values are missing.
        """
        # Initialize the parent class
        super(BmsClient, self).__init__(handlers)
        self.daemon = False

        # Read config values
        BmsClient.check_config(bconfig)
        dev = bconfig['dev']
        baud = bconfig['baudrate']

        # Open serial port
        try:
            self._ser = serial.Serial(
                dev, baud, timeout=1.0)  # 1 second timeout
            if not self._ser.isOpen():
                self._ser.open()
        except serial.SerialException as e:
            self._logger.critical("SerialException({0}): {1}"
                                  .format(e.errno, e.strerror))
            raise

        # Setup status class
        self.status = BmsStatus()

        self.queue = bms_queue
        self._logger.info("Started BmsClient")

    def __del__(self):
        self._ser.close()
        del self._ser

    @staticmethod
    def check_config(bconfig):
        """
        Check that the config is complete. Throw a ValueError if any
        configuration values are missing.

        :param bconfig:
            Configuration map.

        :return:
            :const:`True`

        :exception ValueError:
            Will be raised when configuration map missing required configuration options.
        """

        required_config = ['dev', 'baudrate']
        for val in required_config:
            if val not in bconfig:
                raise ValueError("Missing " + val + ", required for BMS")
        # If we get to this point, the required values are present
        return True

    def run(self):
        """
        Overloads Thread.run, continuously reads from the serial port.
        Updates member variables for last lines.
        """
        while not self.cancelled:
            # noinspection PyBroadException
            try:
                line = self._ser.readline()
            except serial.SerialException as e:
                self._logger.warning("BMS not connected: %s" % str(e))
            except Exception as e:
                utils.log_exception(self._logger, e)
            else:
                # If the checksum is wrong, skip it
                try:
                    data = line[:122]
                    checksum = int(line[122:126], 16)
                except ValueError:
                    # If we don't have a long enough line the
                    # conversion fails with a blank string
                    continue
                except IndexError:
                    # I'm not sure we ever hit this, but it also
                    # would indicate a short line
                    continue

                # If the checksum fails we have a bad line
                if not self.fletcher16(data) == checksum:
                    continue

                try:
                    self.queue.put(str(time.strftime("%Y-%m-%d %H:%M:%S"))
                                   + ',' + str(line))
                except queue.Full:
                    pass  # Ignore

                self.status.update(line)

    @staticmethod
    def fletcher16(data):
        """
        Performs the fletcher-16 checksum for a string of bytes.
        Puts the bytes in the reverse order from the ordinary order.
        See https://en.wikipedia.org/wiki/Fletcher%27s_checksum

        :param data:
            a ``bytes`` array

        :return:
            the integer checksum
        """
        if not isinstance(data, bytes):
            return None
        if PY3:
            sum1, sum2 = 0, 0
            for byte in data:
                sum1 = (sum1 + byte) % 255
                sum2 = (sum2 + sum1) % 255
        else:
            sum1, sum2 = 0, 0
            for byte in data:
                # noinspection PyTypeChecker
                sum1 = (sum1 + ord(byte)) % 255
                sum2 = (sum2 + sum1) % 255
        return (sum1 << 8) | sum2

    #########################################
    # Methods called from Main thread
    #########################################

    def print_data(self):
        """
        Print the charge and current as we currently have it, in
        human-readable format.

        :return: :const:`None`
        """
        charge = self.status.soc
        cur = self.status.current
        if charge is not None:
            print("%20s %10d %10s" % ("State of Charge", charge, "%"))
        else:
            print("%20s %10s %10s" % ("State of Charge", "ERR", "%"))

        if cur is not None:
            print("%20s %10d %10s" % ("Battery Current", cur, "A"))
        else:
            print("%20s %10s %10s" % ("Battery Current", "ERR", "A"))

    @staticmethod
    def csv_header():
        """
        Return a string of the CSV header for our data.

        No newline or trailing comma.
        """
        return "SoC (%),BMS Voltage,Current (A)"

    def csv_line(self):
        """
        Return the CSV data in the form ``"%f,%f"%(charge, cur)``
        """
        # Short circuit if we haven't started reading data yet
        charge = self.status.soc
        voltage = self.status.voltage
        cur = self.status.current
        if charge is not None and voltage is not None and cur is not None:
            return "%d,%f,%d" % (charge, voltage, cur)
        else:
            return ",,"
