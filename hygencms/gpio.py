import re
import platform

if not platform.uname()[0] == 'Linux' and platform.release() >= '4.1.0':
    raise EnvironmentError('Requires Linux >=4.1.0')
    # pass

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


def normalize_pin(pin):
    """Return a standardized format of a pin number"""
    return re.sub(r'[Pp]([89]).*([0-9]{2})', r'P\1_\2', pin)


def write(pin, value):
    """
    Write to a GPIO pin.
    :param pin: Pin to write to, such as P9_11
    :param value: Interpreted as boolean
    :return: None
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
    Read a GPIO pin. Return gpio.HIGH=1=True or gpio.LOW=0=False
    :param pin: A GPIO pin
    :return: True/False
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
