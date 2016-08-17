# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

"""
This module provides a very simple interface to the gpio pins on the
BeagleBone Black. Pins can be written to using ``gpio.write`` or read
with ``gpio.read``. It is assumed that all necessary pinmuxing has
been done prior to calling any functions from this module. This module
implements only the pins which are used as gpio pins in the version of
the HyGenCMS software in which it is included.

This gpio module requires a Linux kernel version >= 4.1, in order to
have correct paths for the sysfs files.

All gpio functions accept pin titles as their argument, of the form
'P9_08'.
"""

from .pins import normalize_pin
import platform

if not platform.uname()[0] == 'Linux' and platform.release() >= '4.1.0':
    raise EnvironmentError('Requires Linux >=4.1.0')

pins = {
    'P8_07': {
        'id': 66,
        'description': 'Spare switch',
    },
    'P8_08': {
        'id': 67,
        'description': 'Disk activity LED',
    },
    'P8_09': {
        'id': 69,
        'description': 'USB switch',
    },
    'P8_10': {
        'id': 68,
        'description': 'Safe to remove LED',
    },
    'P8_11': {
        'id': 45,
        'description': 'Hold 12V',
    },
    'P8_12': {
        'id': 44,
        'description': 'PID LED',
    },
    'P8_13': {
        'id': 23,
        'description': 'Switch: move logs to USB',
    },
    'P8_14': {
        'id': 26,
        'description': 'Spare LED',
    },
    'P8_15': {
        'id': 47,
        'description': 'Aux START',
    },
    'P8_16': {
        'id': 46,
        'description': 'CMS Warn',
    },
    'P8_17': {
        'id': 27,
        'description': 'Aux STOP'
    },
    'P8_18': {
        'id': 65,
        'description': 'CMS Fault',
    },
    'P9_12': {
        'id': 60,
        'description': 'Battery gauge clk signal',
    },
    'P9_15': {
        'id': 48,
        'description': 'Battery gauge data signal',
    },
    'P9_23': {
        'id': 49,
        'description': 'Fuel gauge clk signal',
    },
    'P9_25': {
        'id': 117,
        'description': 'Fuel gauge data signal',
    },
}

HIGH = 1
LOW = 0
INPUT = 1
OUTPUT = 0

_base_path = '/sys/class/gpio/gpio{:d}/value'
for p in pins:
    pins[p]['path'] = _base_path.format(pins[p]['id'])


def write(pin, value):
    """
    Write to a GPIO pin.

    :param pin:
        Pin to write to, such as P9_11

    :param value:
        Interpreted as boolean

    :return: 
        :const:`None`
    """
    normalized_pin = normalize_pin(pin)
    try:
        pin_map = pins[normalized_pin]
    except KeyError:
        return  # Pin not supported

    with open(pin_map['path'], 'w') as f:
        f.write('1' if value else '0')


def read(pin):
    """
    Read a GPIO pin.

    Return gpio.HIGH or gpio.LOW.

    :param pin:
        A GPIO pin.

    :return:
        :const:`True` or :const:`False`
    """
    normalized_pin = normalize_pin(pin)
    try:
        pin_map = pins[normalized_pin]
    except KeyError:
        return  # Pin not supported

    with open(pin_map['path'], 'r') as f:
        if int(f.read()):
            return HIGH
        else:
            return LOW
