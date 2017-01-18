# Copyright (C) Planetary Power Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium, is prohibited.
# Proprietary and confidential.
# Bill Marty <bmarty@planetarypower.com>, January 2017.

import sys
import time
import logging
from monotonic import monotonic
from . import pins
from .asyncio import AsyncIOThread

# TODO Instantiate the power client in main.
# TODO Update setpoint in config.py and tuning.py.
# TODO We're not using an_300v_volt, so let's comment it out.

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
        # Input items:
        #   current measurement
        analog_dict = config["analog"]
        analog_measurements = analog_dict["measurements"]
        self.analog_current = analog_measurements[0]
        #   voltage measurement
        deepsea_dict = config["deepsea"]
        measurement_file = deepsea_dict["mlistfile"]
        deepsea_measurement_list = DeepSeaClient.read_measurement_description(measurement_file)
        for m in deepsea_measurement_list:
            if m[NAME] == "300V Bus Voltage":
                self.hibus_voltage = m
        if not self.hibus_voltage:
            self._logger.info("!!PowerClient failed to read voltage"
                              "measurement info!!")
        # Initialize our output variable in the data store.
        self.data_store["calc_300v_pwr"] = 0.0
        # Debug - write the voltage and current values that we're reading so
        #   I know the reading is working.
        self.data_store["pwr:voltage"] = 0.0
        self.data_store["pwr:current"] = 0.0
        # Log to info that we've started
        self._logger.info("Started PowerClient")

    def run(self):
        """
        Overloads Thread.run, runs and calculates high bus charge power,
        as the product of GEN_CUR and deep sea bus voltage.
        """
        while not self.cancelled:
            # Try reading GEN_CUR and deep sea bus voltage.



    def print_data(self):
