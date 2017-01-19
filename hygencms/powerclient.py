# Copyright (C) Planetary Power Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium, is prohibited.
# Proprietary and confidential.
# Bill Marty <bmarty@planetarypower.com>, January 2017.

import sys
import time
from .asyncio import AsyncIOThread
from .deepseaclient import DeepSeaClient

# TODO Update setpoint in config.py and tuning.py.
# TODO We're not using an_300v_volt, so let's comment it out.
# TODO Add my calculated power to the run log file.


class PowerClient(AsyncIOThread):
    """
    This class calculates the high bus power from deepsea voltage and
    analog current.
    """

    # Indices of items in measurement lists
    NAME = 0
    UNITS = 1
    PIN = 2
    GAIN = 3
    OFFSET = 4

    def __init__(self, config, handlers, data_store):
        """
        PowerClient constructor.
        """
        super(PowerClient, self).__init__(handlers)
        self.cancelled = False
        self.data_store = data_store
        self.new_log_file = False
        # Input items:
        #   current measurement
        analog_dict = config['analog']
        analog_measurements = analog_dict['measurements']
        self.analog_current = analog_measurements[0]
        # Debug
        print('self.analog_current: {}'.format(self.analog_current))
        #   voltage measurement
        deepsea_dict = config['deepsea']
        measurement_file = deepsea_dict['mlistfile']
        deepsea_measurement_list = \
            DeepSeaClient.read_measurement_description(measurement_file)
        for m in deepsea_measurement_list:
            if m[PowerClient.NAME] == '300V Bus Voltage':
                self.hibus_voltage = m
        if not self.hibus_voltage:
            self._logger.info('!!PowerClient failed to read voltage'
                              'measurement info!!')
        # Debug
        print('self.hibus_voltage: {}'.format(self.hibus_voltage))
        # Initialize our output variable in the data store.
        self.data_store['calc_300v_pwr'] = 0.0
        # Debug - write the voltage and current values that we're reading so
        #   I know the reading is working.
        self.data_store['pwr.voltage'] = 0.0
        self.data_store['pwr.current'] = 0.0
        # Debug
        self.first_pass = True
        # Log to info that we've started
        self._logger.info('Started PowerClient')

    def run(self):
        """
        Overloads Thread.run, runs and calculates high bus charge power,
        as the product of GEN_CUR and deep sea bus voltage.
        """
        while not self.cancelled:
            # Debug - verify that logger writes work from here.
            if self.first_pass:
                self._logger.info('Verified - logger writes are working :-)')
                self.first_pass = False
                print(self.data_store)
            # Try reading GEN_CUR.
            try:
                current = self.data_store[self.analog_current[PowerClient.PIN]]
            except:
                exc_type, exc_value = sys.exc_info()[:2]
                self._logger.info('!!Current reading error: {} {}'
                                  .format(exc_type, exc_value))
            # Try reading hi bus voltage.
            try:
                voltage = self.data_store[self.hibus_voltage[PowerClient.PIN]]
            except:
                exc_type, exc_value = sys.exc_info()[:2]
                self._logger.info('!!Voltage reading error: {} {}'
                                  .format(exc_type, exc_value))
            # Calculate and store power, and the input values
            # In early passes, voltage and current may be None types, until
            #   readings come in.  Prevent the exception...
            if voltage and current:
                self.data_store['calc_300v_pwr'] = voltage * current
                self.data_store['pwr.voltage'] = voltage
                self.data_store['pwr.current'] = current
        time.sleep(0.25)

    def print_data(self):
        """
        Print PowerClient's data of interest.
        """
        # Calculated power.
        display = '%20s %10.2f %10s' % ('calc_300v_pwr',
                                        self.data_store['calc_300v_pwr'],
                                        'W')
        print(display)
        # Input variables
        display = '%20s %10.2f %10s' % ('pwr.voltage',
                                        self.data_store['pwr.voltage'],
                                        'V')
        print(display)
        display = '%20s %10.2f %10s' % ('pwr.current',
                                        self.data_store['pwr.current'],
                                        'A')
        print(display)

    def csv_header(self):
        """
        Empty for now, just to keep main happy.
        """
        return ''

    def csv_line(self):
        """
        Empty for now, just to keep main happy.
        """
        return ''
