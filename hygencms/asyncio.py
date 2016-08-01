# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

"""
"""
import logging
import os
import queue  # For Python2, Queue as queue
import subprocess
import sys
import time
from datetime import datetime
from subprocess import CalledProcessError, check_call, STDOUT
from threading import Thread

import monotonic
import serial
from modbus_tk import defines as defines
from modbus_tk.exceptions import ModbusInvalidResponseError, ModbusError
from modbus_tk.modbus_rtu import RtuMaster
from modbus_tk.modbus_tcp import TcpMaster
from monotonic import monotonic
from serial import SerialException

from hygencms import adc, utils, gpio, pins, pwm
from hygencms.utils import PY3


class AsyncIOThread(Thread):
    """
    Super-class for all the threads which read from a source.
    """

    def __init__(self, handlers):
        """
        Constructor
        :param handlers: A list of log handlers
        """
        super(AsyncIOThread, self).__init__()
        self.daemon = False
        self.cancelled = False

        self._logger = None
        self.start_logger(handlers)

    def start_logger(self, handlers):
        """
        Start a logger with the name of the instance type
        :param handlers: Log handlers to add
        :return: None
        """
        self._logger = logging.getLogger(type(self).__name__)
        for h in handlers:
            self._logger.addHandler(h)
        self._logger.setLevel(logging.DEBUG)

    #####################################
    # Methods for call from parent thread
    #####################################

    def cancel(self):
        self.cancelled = True
        self._logger.info("Stopping " + str(self) + "...")


class AnalogClient(AsyncIOThread):
    """
    This class reads from the BeagleBone ADC in a separate thread.
    This thread reads all values specified in the configuration file
    at a specified frequency.
    """

    NAME = 0
    UNITS = 1
    PIN = 2
    GAIN = 3
    OFFSET = 4

    def __init__(self, aconfig, handlers, data_store):
        """

        :param aconfig:
        :param handlers:
        :param data_store:
        """
        super(AnalogClient, self).__init__(handlers)

        # Read configuration values
        AnalogClient.check_config(aconfig)
        self._input_list = aconfig['measurements']
        self.frequency = aconfig['frequency']
        self.averages = aconfig['averages']
        if self.averages == 0:
            raise ValueError("Cannot average 0 values")
        self.mfrequency = self.frequency / self.averages

        # Initialize our array of values
        self.data_store = data_store
        self.data_store.update({m[AnalogClient.PIN]: None for m in self._input_list})
        self.partial_values = {m[AnalogClient.PIN]: (0.0, 0) for m in self._input_list}
        self.last_updated = monotonic.monotonic()
        self._last_written = 0

        # Open the ADC
        adc.setup()

        # Log to info that we've started
        self._logger.info("Started analogclient")

    @staticmethod
    def check_config(aconfig):
        """

        :param aconfig:
        :return:
        """
        required_config = ['measurements', 'frequency', 'averages']
        for val in required_config:
            if val not in aconfig:
                raise ValueError("Missing " + val + ", required for modbus")
        # Make sure the measurements are in the right format
        for m in aconfig['measurements']:
            try:
                assert len(m) == 5
                assert isinstance(m[AnalogClient.NAME], str)
                assert isinstance(m[AnalogClient.UNITS], str)
                assert isinstance(m[AnalogClient.PIN], str)
                assert isinstance(m[AnalogClient.GAIN], float)
                assert isinstance(m[AnalogClient.OFFSET], float)
            except AssertionError:
                raise ValueError("Measurement list formatted incorrectly")
        # If we get to this point, the required values are present
        return True

    def run(self):
        """
        Overloads Thread.run, runs and reads analog inputs.
        """
        while not self.cancelled:
            # noinspection PyBroadException
            try:
                t = monotonic.monotonic()
                # If we've passed the ideal time, get the value
                if t >= self.last_updated + self.mfrequency:
                    for m in self._input_list:
                        key = m[AnalogClient.PIN]
                        sum_, n = self.partial_values[key]

                        if n >= self.averages:
                            average = sum_ / n
                            self.data_store[key] = \
                                average * m[AnalogClient.GAIN] \
                                + m[AnalogClient.OFFSET]
                            sum_, n = 0., 0.

                        try:
                            sum_, n = sum_ + adc.read_volts(m[AnalogClient.PIN]), n + 1
                        except RuntimeError:  # Shouldn't ever happen
                            exc_type, exc_value = sys.exc_info()[:2]
                            self._logger.error("ADC reading error: %s %s"
                                               % (exc_type, exc_value))
                        except ValueError:  # Invalid AIN or pin name
                            exc_type, exc_value = sys.exc_info()[:2]
                            self._logger.error("Invalid AIN or pin name: %s %s"
                                               % (exc_type, exc_value))
                        except IOError:  # File reading error
                            exc_type, exc_value = sys.exc_info()[:2]
                            self._logger.error("%s %s", exc_type, exc_value)

                        self.partial_values[key] = sum_, n
                    self.last_updated = t

                time.sleep(0.01)
            except Exception as e:
                utils.log_exception(self._logger, e)

    ###################################
    # Methods called from Main Thread
    ###################################

    def print_data(self):
        """
        Print all the data as we currently have it, in human-
        readable format.
        """
        for m in self._input_list:
            key = m[AnalogClient.PIN]
            val = self.data_store[key]
            if val is None:
                display = "%20s %10s %10s" % (m[AnalogClient.NAME],
                                              "ERR", m[AnalogClient.UNITS])
            else:
                display = "%20s %10.2f %10s" % (m[AnalogClient.NAME],
                                                val, m[AnalogClient.UNITS])
            print(display)

    def csv_header(self):
        """
        Return the CSV header line with no new line or trailing comma
        """
        names = []
        for m in self._input_list:
            names.append(m[AnalogClient.NAME])
        return ','.join(str(x) for x in names)

    def csv_line(self):
        """
        Return a CSV line of the data we currently have.

        The line is returned with no new line or trailing comma.
        """
        values = []
        now = monotonic.monotonic()
        if now > self._last_written:
            for m in self._input_list:
                val = self.data_store[m[AnalogClient.PIN]]
                if val is not None:
                    values.append(str(val))
                else:
                    values.append('')
            self._last_written = now
        return ','.join(values)


class BmsClient(AsyncIOThread):
    """
    This class provides a thread to get data from the Becket battery
    management system. The get_data and
    print_data methods will read the battery percentage at that moment
    and return or print it.
    """

    def __init__(self, bconfig, handlers):
        """
        Initialize the bms client from the configuration values.

        Could throw the following exceptions:
        - IOError
        - serial.SerialException
        - ValueError

        :param bconfig:
        :param handlers:
        """
        # Initialize the parent class
        super(BmsClient, self).__init__(handlers)
        self.daemon = False

        # Read config values
        BmsClient.check_config(bconfig)
        dev = bconfig['dev']
        baud = bconfig['baudrate']
        sfilename = bconfig['sfilename']

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

        # Open file - IOError could be thrown
        self._f = open(sfilename, 'a')

        # Setup global last line variables
        self.last_string_status = ""
        self.last_module_status = ""

        # Setup flags for fresh values
        self._last_string_fresh = False
        self._last_module_fresh = False

        self._logger.info("Started BmsClient")

    def __del__(self):
        self._ser.close()
        del self._ser
        self._f.close()

    @staticmethod
    def check_config(bconfig):
        """
        Check that the config is complete. Throw a ValueError if any
        configuration values are missing.

        :param bconfig:
        :return:
        """

        required_config = ['dev', 'baudrate', 'sfilename']
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
                    self._f.write(str(line))
                except IOError:
                    pass  # Ignore IOErrors

                if len(line) <= 4:
                    pass
                elif line[4] == 'S':
                    self.last_string_status = line
                    self._last_string_fresh = True
                elif line[4] == 'M':
                    self.last_module_status = line
                    self._last_module_fresh = True

    @staticmethod
    def fletcher16(data):
        """
        Performs the fletcher-16 checksum for a string of bytes.
        Puts the bytes in the reverse order from the ordinary order.
        See https://en.wikipedia.org/wiki/Fletcher%27s_checksum

        :param data: a ``bytes`` array
        :return: the integer checksum
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

    def get_data(self):
        """
        Get the charge and current
        :return: a tuple of (charge, current)
        """
        # If we have a last string
        if self.last_string_status and self._last_string_fresh:
            charge = int(self.last_string_status[19:22])
            cur = int(self.last_string_status[34:39])
            self._last_string_fresh = False
            return charge, cur
        else:
            return None, None

    def print_data(self):
        """
        Print the charge and current as we currently have it, in
        human-readable format.

        :return: None
        """
        # Short circuit if we haven't started reading data yet
        if self.last_string_status == "":
            return

        charge, cur = self.get_data()
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
        return "SoC (%),Current (A)"

    def csv_line(self):
        """
        Return the CSV data in the form ``"%f,%f"%(charge, cur)``
        """
        # Short circuit if we haven't started reading data yet
        if self.last_string_status == "":
            return ","
        charge, cur = self.get_data()
        if charge is not None and cur is not None:
            return "%d,%d" % (charge, cur)
        else:
            return ","


class DeepSeaClient(AsyncIOThread):
    def __init__(self, dconfig, handlers, data_store):
        """
        Set up a DeepSeaClient
        dconfig: the configuration values specific to deepsea
        """
        super(DeepSeaClient, self).__init__(handlers)

        # Do configuration setup
        DeepSeaClient.check_config(dconfig)
        if dconfig['mode'] == "tcp":
            host = dconfig['host']
            port = dconfig['port']
            self._client = TcpMaster(host=host, port=port)
            self._client.open()
        elif dconfig['mode'] == 'rtu':
            dev = dconfig['dev']
            baud = dconfig['baudrate']
            self.unit = dconfig['id']
            self._client = RtuMaster(serial.Serial(port=dev, baudrate=baud))
            self._client.set_timeout(0.1)
            self._client.open()

        # Read and save measurement list
        measurement_list = self.read_measurement_description(
            dconfig['mlistfile'])
        # Add mandatory measurements if they're not included
        self._input_list = self.add_mandatory_measurements(measurement_list)
        # A list of last updated time
        self._data_store = data_store
        self._data_store.update({m[self.ADDRESS]: None
                                 for m in self._input_list})
        self._last_updated = {m[self.ADDRESS]: 0 for m in self._input_list}
        self._last_written = {m[self.ADDRESS]: 0 for m in self._input_list}
        self._logger.info("Started deepsea client")

    def __del__(self):
        if self._client:
            self._client.close()
            del self._client

    def run(self):
        """
        Overloads Thread.run, runs and reads from the DeepSea.
        """
        while not self.cancelled:
            # noinspection PyBroadException
            try:
                for m in self._input_list:
                    key = m[self.ADDRESS]
                    t, last_time = monotonic.monotonic(), self._last_updated[key]
                    if len(m) > self.PERIOD:
                        period = m[self.PERIOD]
                    else:
                        period = 1.0

                    if t - last_time >= period:
                        value = self.get_value(m)
                        if value is not None:
                            self._data_store[key] = value
                            self._last_updated[key] = t
                time.sleep(0.01)
            except Exception:  # Log exceptions but don't exit
                exc_type, exc_value = sys.exc_info()[:2]
                self._logger.error("%s raised in DeepSea thread: %s"
                                   % (str(exc_type), str(exc_value)))

    @staticmethod
    def add_mandatory_measurements(measurement_list):
        """
        Ensure that all required measurements are present in the list.
        If any are missing, add them using the default templates.

        :param measurement_list: The list of measurements read in
        :return: A new measurement list, possibly changed.
        """
        addresses = set(map(lambda m: m[DeepSeaClient.ADDRESS],
                            measurement_list))
        for address in DeepSeaClient.MANDATORY_ADDRESSES:
            if address not in addresses:
                measurement_list.append(
                    DeepSeaClient.MANDATORY_TEMPLATES[address]
                )

        return measurement_list

    @staticmethod
    def check_config(config):
        """
        Check that the config is complete. Throw a ValueError if any
        configuration values are missing.

        :param config: The configuration map to check
        :return: True if success, else raise ValueError
        """
        required_config = ['mode', 'mlistfile']
        required_rtu_config = ['dev', 'baudrate', 'id']
        required_tcp_config = ['host', 'port']
        for val in required_config:
            if val not in config:
                raise ValueError("Missing " + val + ", required for modbus")
        if config['mode'] == 'tcp':
            for val in required_tcp_config:
                if val not in config:
                    raise ValueError("Missing " + val + ", required for tcp")
        elif config['mode'] == 'rtu':
            for val in required_rtu_config:
                if val not in config:
                    raise ValueError("Missing " + val + ", required for rtu")
        else:
            raise ValueError("Mode must be 'tcp' or 'rtu'")
        # If we get to this point, the required values are present
        return True

    @staticmethod
    def read_measurement_description(filename):
        """
        Read a CSV containing the descriptions of modbus values to fetch

        :param filename: The filename from which to read the CSV
        :return: a list of lists, containing the measurement list
        """
        with open(filename) as mdf:
            lines = mdf.readlines()
            measurement_list = []
            for line in lines[2:]:
                fields = line.split(',')
                m = [
                    fields[0],  # name
                    fields[1],  # units
                    int(fields[2]),  # address
                    int(fields[3]),  # length
                    float(fields[4]),  # gain
                    float(fields[5]),  # offset
                ]
                if len(fields) > 6:
                    m.append(float(fields[6]))  # period
                measurement_list.append(m)
        return measurement_list

    def get_value(self, m):
        """
        Get a data value from the deepSea
        :param m: The measurement description list
        :return: The value, an integer
        """
        x = None
        address = m[self.ADDRESS]
        length = m[self.LENGTH]
        try:
            if length == 2:
                if address in self.SIGNED_ADDRESSES:
                    data_format = ">i"
                else:
                    data_format = ">I"
            else:
                if address in self.SIGNED_ADDRESSES:
                    data_format = ">h"
                else:
                    data_format = ">H"

            result = self._client.execute(
                self.unit,  # Slave ID
                defines.READ_HOLDING_REGISTERS,  # Function code
                address,  # Starting address
                length,  # Quantity to read
                data_format=data_format,
            )

            if result:
                x = float(result[0]) * m[self.GAIN] + m[self.OFFSET]
        except ModbusInvalidResponseError:
            exc_type, exc_value = sys.exc_info()[:2]
            self._logger.debug("ModbusInvalidResponseError occurred: %s, %s"
                               % (str(exc_type), str(exc_value)))
        except ModbusError as e:
            self._logger.debug("DeepSea returned an exception: %s"
                               % e.args[0])
        except SerialException:
            exc_type, exc_value = sys.exc_info()[:2]
            self._logger.debug("SerialException occurred: %s, %s"
                               % (str(exc_type), str(exc_value)))
        return x

    ##########################
    # Methods from Main thread
    ##########################

    def print_data(self):
        """
        Print all the data as we currently have it, in human-
        readable format.

        :return: None
        """
        for m in self._input_list:
            name = m[self.NAME]
            val = self._data_store[m[self.ADDRESS]]
            if val is None:
                display = "%20s %10s %10s" % (name, "ERR", m[self.UNITS])
            elif m[self.UNITS] == "sec":
                t = time.gmtime(val)
                time_string = time.strftime("%Y-%m-%d %H:%M:%S", t)
                display = "%20s %21s" % (name, time_string)
            else:
                display = "%20s %10.2f %10s" % (name, val, m[self.UNITS])
            print(display)

    def csv_header(self):
        """
        Get the CSV header line for the DeepSea.
        Does not include newline or trailing comma.

        :return: A string containing the header line.
        """
        names = []
        for m in self._input_list:
            names.append(m[self.NAME])
        return ','.join(names)

    def csv_line(self):
        """
        Get a CSV line of the data we currently have.
        Does not include newline or trailing comma.

        Only includes values which have been updated since
        we last wrote them to file.

        :return: A String containing the csv line.
        """
        values = []
        now = monotonic.monotonic()
        for m in self._input_list:
            key = m[self.ADDRESS]
            val = self._data_store[key]
            updated = self._last_updated[key]
            if updated > self._last_written[key] and val is not None:
                values.append(str(val))
                self._last_written[key] = now
            else:
                values.append('')
        return ','.join(values)

    # List of addresses which hold signed values
    # Ref: DeepSea_Modbus_manualGenComm
    SIGNED_ADDRESSES = {
        # Page 4
        256 * 4 + 1,  # Coolant temperature, degC, 16 bits
        256 * 4 + 2,  # Oil temperature, degC, 16 bits
        256 * 4 + 28,  # Generator L1 watts, W, 32 bits
        256 * 4 + 30,  # Generator L2 watts, W, 32 bits
        256 * 4 + 32,  # Generator L3 watts, W, 32 bits
        256 * 4 + 34,  # Generator current lag/lead, deg, 16 bits
        256 * 4 + 48,  # Mains voltage phase lag/lead, deg, 16 bits
        256 * 4 + 51,  # Mains current phase lag/lead, deg, 16 bits
        256 * 4 + 60,  # Mains L1 watts, W, 32 bits
        256 * 4 + 62,  # Mains L2 watts, W, 32 bits
        256 * 4 + 64,  # Mains L3 watts, W, 32 bits
        256 * 4 + 66,  # Bus current lag/lead, deg, 16 bits
        256 * 4 + 88,  # Bus L1 watts, W, 32 bits
        256 * 4 + 90,  # Bus L2 watts, W, 32 bits
        256 * 4 + 92,  # Bus L3 watts, W, 32 bits
        256 * 4 + 116,  # Bus 2 L1 watts, W, 32 bits
        256 * 4 + 118,  # Bus 2 L2 watts, W, 32 bits
        256 * 4 + 120,  # Bus 2 L3 watts, W, 32 bits
        256 * 4 + 123,  # Bus 2 current lag/lead, deg, 16 bits
        256 * 4 + 145,  # S1 L1 watts, W, 32 bits
        256 * 4 + 147,  # S1 L2 watts, W, 32 bits
        256 * 4 + 149,  # S1 L3 watts, W, 32 bits
        256 * 4 + 151,  # S1 current lag/lead, deg, 16 bits
        256 * 4 + 173,  # S2 L1 watts, W, 32 bits
        256 * 4 + 175,  # S2 L2 watts, W, 32 bits
        256 * 4 + 177,  # S2 L3 watts, W, 32 bits
        256 * 4 + 179,  # S2 current lag/lead, deg, 16 bits
        256 * 4 + 186,  # Load L1 watts, W, 32 bits
        256 * 4 + 188,  # Load L2 watts, W, 32 bits
        256 * 4 + 190,  # Load L3 watts, W, 32 bits
        256 * 4 + 192,  # Load current lag/lead, deg, 16 bits
        256 * 4 + 195,  # Governor output, %, 16 bits
        256 * 4 + 196,  # AVR output, %, 16 bits
        256 * 4 + 200,  # DC Shunt 1 Current, A, 32 bits
        256 * 4 + 202,  # DC Shunt 2 Current, A, 32 bits
        256 * 4 + 204,  # DC Load Current, A, 32 bits
        256 * 4 + 206,  # DC Plant Battery Current, A, 32 bits
        256 * 4 + 208,  # DC Total Current, A, 32 bits
        256 * 4 + 212,  # DC Charger Watts, W, 32 bits
        256 * 4 + 214,  # DC Plant Battery Watts, W, 32 bits
        256 * 4 + 216,  # DC Load Watts, W, 32 bits
        256 * 4 + 218,  # DC Total Watts, W, 32 bits
        256 * 4 + 221,  # DC Plant Battery temperature, degC, 16 bits
        256 * 4 + 223,  # Mains zero sequence voltage angle, deg, 16 bits
        256 * 4 + 224,  # Mains positive sequence voltage angle, deg, 16 bits
        256 * 4 + 225,  # Mains negative sequence voltage angle, deg, 16 bits
        256 * 4 + 232,  # Battery Charger Output Current, mA, 32 bits
        256 * 4 + 234,  # Battery Charger Output Voltage, mV, 32 bits
        256 * 4 + 236,  # Battery Open Circuit Voltage, mV, 32 bits
        256 * 4 + 252,  # Battery Charger Auxiliary Voltage, mV, 32 bits
        256 * 4 + 254,  # Battery Charger Auxiliary Current, mV, 32 bits
        # Page 5
        256 * 5 + 6,  # Inlet manifold temperature 1, degC, 16 bits
        256 * 5 + 7,  # Inlet manifold temperature 2, degC, 16 bits
        256 * 5 + 8,  # Exhaust temperature 1, degC, 16 bits
        256 * 5 + 9,  # Exhaust temperature 2, degC, 16 bits
        256 * 5 + 15,  # Fuel temperature, degC, 16 bits
        256 * 5 + 49,  # Auxiliary sender 1 value, 16 bits
        256 * 5 + 51,  # Auxiliary sender 2 value, 16 bits
        256 * 5 + 53,  # Auxiliary sender 3 value, 16 bits
        256 * 5 + 55,  # Auxiliary sender 4 value, 16 bits
        256 * 5 + 66,  # After treatment temperature T1, degC, 16 bits
        256 * 5 + 67,  # After treatment temperature T3, degC, 16 bits
        256 * 5 + 70,  # Engine percentage torque, %, 32 bits
        256 * 5 + 72,  # Engine demand torque, %, 32 bits
        256 * 5 + 76,  # Nominal friction percentage torque, %, 16 bits
        256 * 5 + 78,  # Crank case pressure, kPa, 16 bits
        256 * 5 + 86,  # Exhaust gas port 1 temperature, degC, 16 bits
        256 * 5 + 87,  # Exhaust gas port 2 temperature, degC, 16 bits
        256 * 5 + 88,  # Exhaust gas port 3 temperature, degC, 16 bits
        256 * 5 + 89,  # Exhaust gas port 4 temperature, degC, 16 bits
        256 * 5 + 90,  # Exhaust gas port 5 temperature, degC, 16 bits
        256 * 5 + 91,  # Exhaust gas port 6 temperature, degC, 16 bits
        256 * 5 + 92,  # Exhaust gas port 7 temperature, degC, 16 bits
        256 * 5 + 93,  # Exhaust gas port 8 temperature, degC, 16 bits
        256 * 5 + 94,  # Exhaust gas port 9 temperature, degC, 16 bits
        256 * 5 + 95,  # Exhaust gas port 10 temperature, degC, 16 bits
        256 * 5 + 96,  # Exhaust gas port 11 temperature, degC, 16 bits
        256 * 5 + 97,  # Exhaust gas port 12 temperature, degC, 16 bits
        256 * 5 + 98,  # Exhaust gas port 13 temperature, degC, 16 bits
        256 * 5 + 99,  # Exhaust gas port 14 temperature, degC, 16 bits
        256 * 5 + 100,  # Exhaust gas port 15 temperature, degC, 16 bits
        256 * 5 + 101,  # Exhaust gas port 16 temperature, degC, 16 bits
        256 * 5 + 102,  # Intercooler temperature, degC, 16 bits
        256 * 5 + 103,  # Turbo oil temperature, degC, 16 bits
        256 * 5 + 104,  # ECU temperature, degC, 16 bits
        256 * 5 + 113,  # Inlet manifold temperature 3, degC, 16 bits
        256 * 5 + 114,  # Inlet manifold temperature 4, degC, 16 bits
        256 * 5 + 115,  # Inlet manifold temperature 5, degC, 16 bits
        256 * 5 + 116,  # Inlet manifold temperature 6, degC, 16 bits
        256 * 5 + 154,  # Battery current, A, 16 bits
        256 * 5 + 190,  # LCD Temperature, degC, 16 bits
        256 * 5 + 192,  # DEF Tank Temperature, degC, 16 bits
        256 * 5 + 201,  # EGR Temperature, degC, 16 bits
        256 * 5 + 202,  # Ambient Air Temperature, degC, 16 bits
        256 * 5 + 203,  # Air Intake Temperature, degC, 16 bits
        256 * 5 + 210,  # Oil Pressure, kPa, 16 bits
        256 * 5 + 217,  # Exhaust gas port 17 temperature, degC, 16 bits
        256 * 5 + 218,  # Exhaust gas port 18 temperature, degC, 16 bits
        256 * 5 + 219,  # Exhaust gas port 19 temperature, degC, 16 bits
        256 * 5 + 220,  # Exhaust gas port 20 temperature, degC, 16 bits
        # Page 6
        256 * 6 + 0,  # Generator total watts, W, 32 bits
        256 * 6 + 8,  # Generator total VA, VA, 32 bits
        256 * 6 + 10,  # Generator L1 Var, Var, 32 bits
        256 * 6 + 12,  # Generator L2 Var, Var, 32 bits
        256 * 6 + 14,  # Generator L3 Var, Var, 32 bits
        256 * 6 + 16,  # Generator total Var, Var, 32 bits
        256 * 6 + 18,  # Generator power factor L1, no units, 16 bits
        256 * 6 + 19,  # Generator power factor L2, no units, 16 bits
        256 * 6 + 20,  # Generator power factor L3, no units, 16 bits
        256 * 6 + 21,  # Generator average power factor, no units, 16 bits
        256 * 6 + 22,  # Generator percentage of full power, %, 16 bits
        256 * 6 + 23,  # Generator percentage of full Var, %, 16 bits
        256 * 6 + 24,  # Mains total watts, W, 32 bits
        256 * 6 + 34,  # Mains L1 Var, Var, 32 bits
        256 * 6 + 36,  # Mains L2 Var, Var, 32 bits
        256 * 6 + 38,  # Mains L3 Var, Var, 32 bits
        256 * 6 + 40,  # Mains total Var, Var, 32 bits
        256 * 6 + 42,  # Mains power factor L1, no units, 16 bits
        256 * 6 + 43,  # Mains power factor L2, no units, 16 bits
        256 * 6 + 44,  # Mains power factor L3, no units, 16 bits
        256 * 6 + 45,  # Mains average power factor, no units, 16 bits
        256 * 6 + 46,  # Mains percentage of full power, %, 16 bits
        256 * 6 + 47,  # Mains percentage of full Var, %, 16 bits
        256 * 6 + 48,  # Bus total watts, W, 32 bits
        256 * 6 + 58,  # Bus L1 Var, Var, 32 bits
        # Some values omitted from exhaustion
        # Page 7
        256 * 7 + 2,  # Time to next engine maintenance, sec, 32 bits
        256 * 7 + 44,  # Time to next engine maintenance alarm 1, sec, 32 bits
        256 * 7 + 48,  # Time to next engine maintenance alarm 2, sec, 32 bits
        256 * 7 + 52,  # Time to next engine maintenance alarm 3, sec, 32 bits
        256 * 7 + 56,  # Time to next plant battery maintenance, sec, 32 bits
        256 * 7 + 64,  # Time to next plant battery maintenance alarm 1, sec, 32 bit
        256 * 7 + 72,  # Time to next plant battery maintenance alarm 2, sec, 32 bit
        256 * 7 + 80,  # Time to next plant battery maintenance alarm 3, sec, 32 bit
    }

    # Indices in measurement lists
    NAME = 0
    UNITS = 1
    ADDRESS = 2
    LENGTH = 3
    GAIN = 4
    OFFSET = 5
    PERIOD = 6

    # Mandatory values to read
    # See DeepSea_Modbus_manualGenComm.docx, 10.6
    FUEL_LEVEL = 1027  # section 10.6, address 3
    BATTERY_LEVEL = 1223  # section 10.6, address 199
    RPM = 1030  # section 10.6, address 6

    # Addresses which are required
    MANDATORY_ADDRESSES = {
        FUEL_LEVEL,
        BATTERY_LEVEL,
        RPM,
    }

    # Templates to use if mandatory values are missing.
    MANDATORY_TEMPLATES = {
        FUEL_LEVEL: ["Fuel level", '%', FUEL_LEVEL, 1, 1, 0, 60],
        BATTERY_LEVEL: ["battery level", 'V', BATTERY_LEVEL, 1, 1.0, 0.0, 1.0],
        RPM: ["Engine speed", 'RPM', RPM, 1, 1.0, 0.0, 0.1],
    }


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
    base_dir = '/home/hygen'

    def __init__(self, config, handlers, log_queue, csv_header):
        """
        Initialize a filewriter which writes to file whatever is put
        on its queue.

        Can raise:
        - ValueError for invalid config
        - IOError (Python < 3.3) or OSError (Python >= 3.3) for inaccessible file

        :param config: The configuration map for the FileWriter
        :param handlers: All the log handlers to log to
        :param log_queue: The queue to pull csv lines off
        :param csv_header: The header to put at the top of each file
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

        :param config:  The configuration map for the FileWriter
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
        # Initial values
        device = None
        prev_hour = -1  # Always start a new file to start
        while not self.cancelled:
            # noinspection PyBroadException
            try:
                now = monotonic.monotonic()

                # Twice a second
                if now >= next_run[0.5]:
                    # if eject button is pressed
                    if gpio.read(pins.USB_SW) == gpio.LOW:
                        # if file closed and unmounted
                        if self.unmount_usb():
                            self.safe_to_remove = True

                    # Update safe-to-remove LED
                    self.safe_to_remove = device and not self.drive_mounted

                    # Schedule next run
                    next_run[0.5] = now + 0.5

                # Every second
                if now >= next_run[1.0]:
                    # Check whether USB is plugged in, and mounted
                    device = self.usb_plugged()
                    mounted_drive = self.usb_mounted()

                    # If we've mounted a new drive and Python hasn't handled it
                    if mounted_drive and not self.drive_mounted:
                        # Get new file (presumably on USB)
                        self._f.close()
                        self._f = self._get_new_logfile()
                        self._write_line(self._csv_header)
                        self.drive_mounted = True

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

    def usb_mounted(self):
        """
        Return the path to whatever drive is mounted, or None

        :return: '/media/[drive]' or None
        """
        # Check for USB directory
        try:
            mount_list = str(subprocess.check_output(['mount']))
        except CalledProcessError:
            self._logger.debug("Error in mount")
            return None

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
            return os.path.join(self.base_dir, self.relative_directory)
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

        :return: A python file object to write to
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

        :param line: Line to write to file.
        :return: None
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


class WoodwardControl(AsyncIOThread):
    """
    Send a square wave input via the PWM
    """
    # Define directions
    DIRECT = 0
    REVERSE = 1

    def __init__(self, wconfig, handlers):
        super(WoodwardControl, self).__init__(handlers)
        # Check configuration to ensure all values present
        WoodwardControl.check_config(wconfig)

        # Initialize member variables
        self.cancelled = False
        self._pin = wconfig['pin']
        self._sample_time = wconfig['period']
        self._direction = self.DIRECT
        self.setpoint = wconfig['setpoint']
        self.out_min = 0.0
        self.out_max = 100.0
        self.last_time = 0  # ensure that we run on the first time
        self.process_variable = self.setpoint  # Start by assuming we are there
        self.last_input = self.process_variable  # Initialize
        self.integral_term = 0.0  # Start with no integral windup
        self.in_auto = False  # Start in manual control
        self.kp, self.ki, self.kd = None, None, None
        self.set_tunings(wconfig['Kp'],
                         wconfig['Ki'],
                         wconfig['Kd'])

        # Mode switch: step or pid
        self.mode = 'pid'

        # Initialize the property for output and PWM
        self._output = 0.0
        pwm.start(self._pin, 0.0, 100000)

        # { Step configuration
        # Values for step
        self.period = 20  # period in seconds
        self.on = False
        self.low_val = 40
        self.high_val = 50
        # }

        self._logger.info("Started Woodward controller")

    # Output property automatically updates
    def get_output(self):
        return self._output

    def set_output(self, value):
        # Only set it if it's in the valid range
        if 0 <= value <= 100:
            pwm.set_duty_cycle(self._pin, value)
            self._output = value

    def del_output(self):
        # Maybe close PWM here
        del self._output

    output = property(get_output, set_output, del_output, "PWM Output Value")

    @staticmethod
    def check_config(wconfig):
        """
        Check to make sure all the required values are present in the
        configuration map.
        """
        required_config = ['pin', 'Kp', 'Ki', 'Kd', 'setpoint', 'period']
        for val in required_config:
            if val not in wconfig:
                raise ValueError(
                    "Missing " + val + ", required for woodward config")
                # If we get to this point, the required values are present

    def set_tunings(self, kp, ki, kd):
        """Set new PID controller tunings.

        Kp, Ki, Kd are positive floats or integers that serve as the
        PID coefficients.
        """
        # We can't ever have negative tunings
        # that is accomplished with self.controller_direction
        if kp < 0 or ki < 0 or kd < 0:
            return
        self.kp = kp
        self.ki = ki * self._sample_time
        self.kd = kd / self._sample_time

        if self._direction == self.REVERSE:
            self.kp = -self.kp
            self.ki = -self.ki
            self.kd = -self.kd

    def set_controller_direction(self, direction):
        """
        Set the controller direction to one of DIRECT
        or REVERSE.
        """
        old_direction = self._direction
        if direction in [self.DIRECT, self.REVERSE]:
            self._direction = direction
            if direction != old_direction:
                # If we've changed direction, invert the tunings
                self.set_tunings(self.kp, self.ki, self.kd)

    def set_sample_time(self, new_sample_time):
        """
        Set the current sample time. The sample time is factored into
        the stored values for the tuning parameters, so recalculate
        those also.
        """
        if self._sample_time == 0:
            self._sample_time = new_sample_time
        elif new_sample_time > 0:
            ratio = float(new_sample_time) / self._sample_time
            self.ki *= ratio
            self.kd /= ratio
            self._sample_time = float(new_sample_time)

    def set_output_limits(self, out_min, out_max):
        """
        Set limits on the output. If the current output or integral term is
        outside those limits, bring it inside the boundaries.
        """
        if out_max < out_min:
            return
        self.out_min = out_min
        self.out_max = out_max

        if self.output < self.out_min:
            self.output = self.out_min
        elif self.output > self.out_max:
            self.output = self.out_max

        if self.integral_term < self.out_min:
            self.integral_term = self.out_min
        elif self.integral_term > self.out_max:
            self.integral_term = self.out_max

    def set_auto(self, new_auto):
        """
        Set whether we're in auto mode or manual.
        """
        if new_auto and not self.in_auto:
            self.initialize_pid()

        if new_auto != self.in_auto:
            self.in_auto = new_auto
            if new_auto:
                self._logger.info('Entering auto mode')
            else:
                self._logger.info('Exiting auto mode')

    def initialize_pid(self):
        """
        Initialize the PID to match the current output.
        """
        self.last_input = self.process_variable
        self.integral_term = self.output
        if self.integral_term > self.out_max:
            self.integral_term = self.out_max
        elif self.integral_term < self.out_min:
            self.integral_term = self.out_min

    def compute(self):
        """
        Compute the next output value for the PID based on the member variables
        """
        if not self.in_auto:
            return self.output

        now = monotonic.monotonic()
        time_change = (now - self.last_time)

        if time_change >= self._sample_time:
            # Compute error variable
            error = self.setpoint - self.process_variable

            # Calculate integral term
            self.integral_term += error * self.ki
            if self.integral_term > self.out_max:
                self.integral_term = self.out_max
            elif self.integral_term < self.out_min:
                self.integral_term = self.out_min

            # Compute the proxy for the derivative term
            d_pv = (self.process_variable - self.last_input)

            # Compute output
            output = (self.kp * error +
                      self.integral_term -
                      self.kd * d_pv)
            if output > self.out_max:
                output = self.out_max
            elif output < self.out_min:
                output = self.out_min

            # Save variables for the next time
            self.last_time = now
            self.last_input = self.process_variable

            # Return the calculated value
            return output
        else:
            return self.output

    def run(self):
        """
        Overloaded method from Thread.run. Start sending a square wave.
        """
        i = 0
        if self.mode == 'step':
            # If we're in step mode, we do a square wave
            half_period = 0.5 * self.period
            while not self.cancelled:
                # noinspection PyBroadException
                try:
                    # Period
                    if i >= half_period:
                        if self.on:
                            self.output = self.low_val
                        else:
                            self.output = self.high_val
                        self.on = not self.on
                        i = 0
                    i += 1
                    time.sleep(1.0)
                except Exception as e:
                    utils.log_exception(self._logger, e)

        elif self.mode == 'pid':
            while not self.cancelled:
                # noinspection PyBroadException
                try:
                    # output property automatically adjusts PWM output
                    self.output = self.compute()
                    time.sleep(0.1)  # avoid tight looping
                except Exception as e:
                    utils.log_exception(self._logger, e)

    ##########################
    # Methods from Main thread
    ##########################

    def print_data(self):
        """
        Print all the data as we currently have it, in human-
        readable format.
        """
        print("%20s %10s %10s" % ("PID enabled", str(self.in_auto), "T/F"))
        print("%20s %10.2f %10s" % ("PID output", self.output, "%"))
        print("%20s %10.2f %10s" % ("Setpoint A", self.setpoint, "A"))

        factor = 1
        if self._direction == self.REVERSE:
            factor = -1
        print("%20s %10.2f" % ("Kp", self.kp * factor))
        print("%20s %10.2f" % ("Ki", self.ki * factor / self._sample_time))
        print("%20s %10.2f" % ("Kd", self.kd * factor * self._sample_time))

    @staticmethod
    def csv_header():
        """
        Return the CSV header line.
        Does not include newline or trailing comma.
        """
        titles = ["pid_out_percent", "setpoint_amps", "kp", "ki", 'kd']
        return ','.join(titles)

    def csv_line(self):
        """
        Return a CSV line of the data we currently have.
        Does not include newline or trailing comma.
        """
        if self._direction == self.REVERSE:
            factor = -1
        else:
            factor = 1
        values = [
            str(self.output),
            str(self.setpoint),
            str(self.kp * factor),
            str(self.ki * factor / self._sample_time),
            str(self.kd * factor * self._sample_time),
        ]
        return ','.join(values)