# System imports
import time
import sys
from monotonic import monotonic

from modbus_tk.modbus_rtu import RtuMaster
from modbus_tk.modbus_tcp import TcpMaster
import modbus_tk.defines as defines
from modbus_tk.exceptions import ModbusError, ModbusInvalidResponseError
from serial import SerialException
import serial
from asynciothread import AsyncIOThread

NAME = 0
UNITS = 1
ADDRESS = 2
LENGTH = 3
GAIN = 4
OFFSET = 5
PERIOD = 6

# List of addresses which hold signed values.
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
        self._input_list = self.read_measurement_description(dconfig['mlistfile'])
        # A list of last updated time
        self._data_store = data_store
        self._data_store.update({m[ADDRESS]: None for m in self._input_list})
        self._last_updated = {m[ADDRESS]: 0 for m in self._input_list}
        self._last_written = {m[ADDRESS]: 0 for m in self._input_list}
        self._logger.debug("Started deepsea client")

    def __del__(self):
        if self._client:
            self._client.close()
            del self._client

    def run(self):
        """
        Overloads Thread.run, runs and reads from the DeepSea.
        """
        while not self.cancelled:
            for m in self._input_list:
                key = m[ADDRESS]
                t, last_time = monotonic(), self._last_updated[key]
                if len(m) > PERIOD:
                    period = m[PERIOD]
                else:
                    period = 1.0

                if t - last_time >= period:
                    value = self.get_value(m)
                    if value is not None:
                        self._data_store[key] = value
                        self._last_updated[key] = t
            time.sleep(0.01)

    @staticmethod
    def check_config(config):
        """
        Check that the config is complete. Throw an exception if any
        configuration values are missing.
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
        Read a CSV containing the descriptions of modbus values.
        Returns a list of lists, containing the values.
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
        """
        x = None
        address = m[ADDRESS]
        length = m[LENGTH]
        # self._logger.debug("Reading from {0}, length {1}"
        #                    .format(address, length))
        try:
            if length == 2:
                if address in SIGNED_ADDRESSES:
                    data_format = ">i"
                else:
                    data_format = ">I"
            else:
                if address in SIGNED_ADDRESSES:
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
                x = float(result[0]) * m[GAIN] + m[OFFSET]
        except ModbusInvalidResponseError:
            exc_type, exc_value = sys.exc_info()[:2]
            self._logger.error("ModbusInvalidResponseError occurred: %s, %s"
                               % (str(exc_type), str(exc_value)))
        except ModbusError as e:
            self._logger.error("DeepSea returned an exception: %s"
                               % e.args[0])
        except SerialException:
            exc_type, exc_value = sys.exc_info()[:2]
            self._logger.error("SerialException occurred: %s, %s"
                               % (str(exc_type), str(exc_value)))
        # self._logger.debug("Returning from {0}, value {1}"
        #                    .format(address, x))
        return x

    ##########################
    # Methods from Main thread
    ##########################

    def print_data(self):
        """
        Print all the data as we currently have it, in human-
        readable format.
        """
        for m in self._input_list:
            name = m[NAME]
            val = self._data_store[m[ADDRESS]]
            if val is None:
                display = "%20s %10s %10s" % (name, "ERR", m[UNITS])
            elif m[UNITS] == "sec":
                t = time.gmtime(val)
                time_string = time.strftime("%Y-%m-%d %H:%M:%S", t)
                display = "%20s %21s" % (name, time_string)
            else:
                display = "%20s %10.2f %10s" % (name, val, m[UNITS])
            print(display)

    def csv_header(self):
        """
        Return the CSV header line.
        Does not include newline or trailing comma.
        """
        names = []
        for m in self._input_list:
            names.append(m[NAME])
        return ','.join(names)

    def csv_line(self):
        """
        Return a CSV line of the data we currently have.
        Does not include newline or trailing comma.
        """
        values = []
        now = monotonic()
        for m in self._input_list:
            key = m[ADDRESS]
            val = self._data_store[key]
            updated = self._last_updated[key]
            if updated > self.last_written[key] and val is not None:
                values.append(str(val))
                self._last_written[key] = now
            else:
                values.append('')
        return ','.join(values)

