# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

"""
Provides configuration utilities for the logger.

The configuration file will be in the form of a python literal dictionary.
"""

from . import pins

###############################
# Constants
###############################
defaults = {
    # DeepSea Configuration
    'deepsea': {
        # Where to find the measurement list
        'mlistfile':\
        '/home/hygen/HyGenCMS/hygencms/cur_rpm.csv',
        # Possible mode values are 'rtu' or 'tcp'
        'mode': 'rtu',
        # RTU settings
        'baudrate': 19200,  # serial port baudrate
        'dev': '/dev/ttyO1',  # serial device
        'id': 10,  # Set on deepsea - slave ID
    },

    # BMS Configuration
    'bms': {
        # serial port settings
        'baudrate': 9600,
        'dev': '/dev/ttyO4',
    },

    # Control signal to Woodward
    'woodward': {
        'Kp': 0.0,
        'Ki': 0.5,
        'Kd': 0.0,
        'slew': 100,  # In percent per second max change
        'setpoint': 25.0,  # Amps
        'period': 1.0,
    },

    # Analog measurements to take
    'analog': {
        # How many values to average for each reported value
        'averages': 64,
        'measurements': [
            # [ 'name', 'units', 'pin', gain, offset ]
            ['an_300v_cur', 'A', pins.GEN_CUR, 40.0, -0.2],  # Theoretical gain, observed offset
            ['an_300v_volt', 'V', pins.SIG_300V, 191.4, 0.4],  # Theoretical values
        ],
        # How often to report values
        'frequency': 1.0,
    },

    # filewriter thread configuration (write data to disk)
    'filewriter': {
        'ldir': 'logs',
    },
}
