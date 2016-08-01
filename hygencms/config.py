# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

"""
Provides configuration utilities for the logger.

The configuration file will be in the form of a python literal dictionary.
It will be structured as a nested dictionary of the following form::

    {
        "enabled": ["deepsea", "bms"], # list of async components which are
                # enabled. Sub configuration maps will use the strings
                # here as their key

        "datafile": "/path/to/data.log",

        "logfile": "/path/to/program/log.log",

        # Sub-configuration maps
        "deepsea": { # If enabled in enabled
            "mode": "tcp", # or "rtu"

            "mlistfile": "/path/to/list/of/measurements.csv",

            # TCP
            "host": "192.168.1.212", # IP as string
            "port": 1003, # Integer port number

            # RTU
            "dev": "/dev/ttyO1", # Linux device file for serial
            "baudrate": 9600, # Integer baud rate
            "id": 8, # Slave device id
        },

        "bms": {
            "dev": "/dev/ttyO2", # Linux device file for serial
            "baudrate": 9600, # baud rate to read in
            "sfilename": "bmsstream.txt", # A file to store the stream of data verbatim
        },

        "woodward": {
            "ww_sig": "P9_21", # PWM signal to the Woodward
        },
    }
"""
###############################
# Python imports
###############################
import ast
import os

import serial
from modbus_tk.modbus_rtu import RtuMaster
from modbus_tk.modbus_tcp import TcpMaster

from .utils import is_int, get_input

###############################
# Constants
###############################
default_config_file = \
    "/home/hygen/HyGenCMS/hygencms/hygen_logger.py"

ddefaults = {
    'mlistfile': "mdf.csv",
    # TCP
    'host': "192.168.1.212",
    'port': 1003,
    # RTU
    'dev': "/dev/ttyO1",
    'baudrate': 9600,
    'id': 0x8,
}

bdefaults = {
    'dev': "/dev/ttyO2",
    'baudrate': 9600,
    'sfilename': '/home/hygen/log/bmsstream.log',
}

wdefaults = {
    'ww_sig': 'P9_21',
}

defaults = {
    'enabled': [],
    'datafile': "/home/hygen/log/datalog.log",
    'logfile': "/home/hygen/log/hygen_telemetry.log",
}


def get_configuration(from_console=False, config_file=default_config_file):
    """
    Return a configuration map, either from file or from user input on the
    console.
    """
    config = {'enabled': []}
    if from_console:
        if get_input("Use config file [y/n]?",
                     default='n').strip().lower()[0] == "y":
            config_file = get_input(
                "Enter the path to the config file:",
                default=default_config_file)
            config = get_configuration(config_file=config_file)
        else:
            # Get DeepSea Configuration
            ans = get_input("Use the DeepSea [y/n]?",
                            default='n').strip().lower()[0]
            if ans == "y":
                config['enabled'].append('deepsea')
                config['deepsea'] = get_deepsea_configuration()

            # Get BMS configuration
            ans = get_input("Use the Beckett BMS [y/n]?",
                            default='n').strip().lower()[0]
            if ans == "y":
                config['enabled'].append('bms')
                config['bms'] = get_bms_configuration()

            # Get woodward configuration
            ans = get_input("Drive the woodward PWM output [y/n]?",
                            default='n').strip().lower()[0]
            if ans == 'y':
                config['enabled'].append('woodward')
                config['woodward'] = get_woodward_configuration()

            # Get analog input configuration
            ans = get_input("Use analog inputs [y/n]?",
                            default='n').strip().lower()[0]
            if ans == 'y':
                config['enabled'].append('analog')
                config['analog'] = get_analog_configuration()

            # Get filewriter configuration
            ans = get_input("Write to file [y/n]?",
                            default='n').strip().lower()[0]
            if ans == 'y':
                config['enabled'].append('filewriter')
                config['filewriter'] = get_filewriter_configuration()

            # Add additional async components here

            # Set up data log
            ans = get_input("Where to store the data log file?",
                            default=defaults['datafile'])
            if os.path.exists(ans) and \
                    os.access(os.path.dirname(ans), os.W_OK):
                config['datafile'] = ans
            else:
                raise IOError("Error with data file")

            # Enable saving to config file
            ans = get_input("Save configuration to file [y/n]?", default='n')
            if ans.strip().lower()[0] == "y":
                ans = get_input("Save file:", default=default_config_file)
                if not write_config_file(config, ans):
                    ans = get_input("Writing to disk failed. Continue?",
                                    default='n').strip().lower()[0]
                    if ans != 'y':
                        raise IOError("Error writing config to disk")

    else:
        try:
            config_file = os.path.abspath(config_file)
            with open(config_file, 'r') as f:
                s = f.read()
                try:
                    config = ast.literal_eval(s)
                except:
                    raise ValueError("Syntax errors in configuration file")
        except:
            raise IOError(
                "Could not open configuration file \"%s\". Exiting..."
                % config_file)

    return config


def read_measurement_description(filename):
    """
    Read a CSV containing the descriptions of modbus values.

    Returns a list of lists, containing the values.
    """
    measurement_list = []
    with open(filename) as mdf:
        lines = mdf.readlines()
        for (n, line) in enumerate(lines):
            line = line.split(',')
            if n >= 2:
                measurement_list.append([line[0], line[1], int(line[2]),
                                         int(line[3]), float(line[4]),
                                         float(line[5])])
    return measurement_list


def get_deepsea_configuration():
    """
    Get configuration values for the DeepSea from the user console.
    """
    config = {}
    ans = ""
    while ans != "tcp" and ans != "rtu":
        ans = get_input("Use tcp or rtu?").lower().strip()

    if ans == "tcp":
        config['mode'] = "tcp"
        config['host'] = get_input("Host address?",
                                   default=ddefaults['host']).strip()

        ans = get_input("Port #?", default=str(ddefaults['port'])).strip()
        while not is_int(ans):
            get_input("Invalid. Port #?", default=str(ddefaults['port']))
        config['port'] = int(ans)

        try:
            c = TcpMaster(host=config['host'], port=config['port'])
            c.open()
        except:
            raise ValueError("Error with host or port params. Exiting...")
        else:
            c.close()

    elif ans == "rtu":
        config['mode'] = "rtu"
        config['dev'] = get_input("Input device?", default=ddefaults['dev'])

        ans = get_input("Baud rate?", default=str(ddefaults['baudrate']))
        while not is_int(ans):
            get_input("Invalid. Baud rate?",
                      default=str(ddefaults['baudrate']))
        config['baudrate'] = int(ans)

        try:
            c = RtuMaster(serial.Serial(
                port=config['dev'],
                baudrate=config['baudrate']
            ))
            c.open()
        except:
            raise ValueError(
                "Error with device or baudrate params. Exiting...")
        else:
            c.close()

        ans = get_input("Slave device ID?", default=str(ddefaults['id']))
        while not is_int(ans):
            get_input("Invalid. Slave device ID?",
                      default=str(ddefaults['id']))
        config['id'] = int(ans)

    ans = get_input("Enter path to measurement list CSV:",
                    default=ddefaults['mlistfile'])

    try:
        f = open(ans)
    except:
        raise IOError("Problem reading measurement list. Exiting...")
    else:
        config['mlistfile'] = ans
        f.close()

    return config


def get_bms_configuration():
    """
    Get configuration values for the Beckett BMS from the user console.
    """
    config = {'dev': get_input("Serial Device?", default=bdefaults['dev'])}

    ans = get_input("Baud rate?", default=str(bdefaults['baudrate']))
    while not is_int(ans):
        get_input("Invalid. Baud rate?", default=str(bdefaults['baudrate']))
    config['baudrate'] = int(ans)

    ans = get_input("Ascii stream file name?", default=bdefaults['sfilename'])
    if os.path.exists(ans):
        config['sfilename'] = ans
    elif os.access(os.path.dirname(ans), os.W_OK):
        config['sfilename'] = ans
    else:
        raise IOError("Error with log file")

    return config


def get_woodward_configuration():
    """
    Get configuration values for the woodward PWM control signal
    """
    config = {'ww_sig': get_input("Pin to Woodward RPM signal?",
                                  default=wdefaults['ww_sig'])}
    return config


def get_analog_configuration():
    """
    Get configuration values for reading in analog components
    """
    config = {}

    first = True
    ans = 'n'
    ms = []
    while first or ans == 'y':
        m = [
            get_input("Enter a measurement name:"),
            get_input("Enter measurement units:"),
            get_input("Enter the pin in form \"P9_25\":"),
            float(get_input("Enter the gain")),
            float(get_input("Enter the offset"))
        ]
        ms.append(m)
        first = False
        ans = get_input("Add another measurement [y/n]?",
                        default='n').strip().lower()[0]
    config['measurements'] = ms

    cont = True
    while cont:
        try:
            ans = get_input("Enter how often to measure analog values",
                            default="1.0")
            f = float(ans)
            cont = False
        except ValueError:  # Invalid conversion to float
            cont = True
        else:
            config['frequency'] = f

    cont = True
    while cont:
        try:
            ans = get_input("How many values to average for each measurement",
                            default="8")
            i = int(ans)
            cont = False
        except ValueError:  # Invalid conversion to int
            cont = True
        else:
            config['averages'] = i

    return config


def get_filewriter_configuration():
    config = {}
    ans = get_input("Directory for log files:")
    while not os.path.exists(ans):
        ans = get_input("Try again: directory for log files:")
    config['ldir'] = ans
    return config


def write_config_file(config, path):
    """
    Attempt to write a configuration map to the filename given.
    Returns True on success, False on failure.
    """
    path = os.path.abspath(path)
    if os.path.exists(path):
        ans = get_input("File exists. Overwrite [y/n]? ").strip.lower()[0]
        if ans != "y":
            return False
    elif os.access(os.path.dirname(path), os.W_OK):
        pass
    else:
        return False

    try:
        with open(path, 'w') as f:
            f.write(str(config))
            f.write('\n')
    except IOError:
        return False

    return True
