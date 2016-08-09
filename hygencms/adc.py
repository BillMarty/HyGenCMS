# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

"""
The ADC module uses the Sysfs interface provided by the Linux kernel and
drivers to control and read from the analog inputs to the BeagleBone.
See `here <http://processors.wiki.ti.com/index.php/Linux_Core_ADC_User's_Guide>`_
for more details.

This module presumes that
all pinmuxing is done ahead-of-time for all pins which are to be used.
"""

import glob
import os

from recordclass import recordclass

adc_setup = False

AdcPin = recordclass('AdcPin', ['pin', 'id', 'path', 'fd'])

pins = {
    'P9_33': AdcPin('P9_33', 4, None, None),
    'P9_35': AdcPin('P9_35', 6, None, None),
    'P9_36': AdcPin('P9_36', 5, None, None),
    'P9_37': AdcPin('P9_37', 2, None, None),
    'P9_38': AdcPin('P9_38', 3, None, None),
    'P9_39': AdcPin('P9_39', 0, None, None),
    'P9_40': AdcPin('P9_40', 1, None, None),
}

SLOTS = '/sys/devices/platform/bone_capemgr/slots'


def setup():
    """
    Setup the ADC for use. Load the ADC cape if needed.

    :return:
        :const:`True` if ADC ready for use, else :const:`False`.
    """
    global adc_setup
    with open(SLOTS, 'r') as f:
        slots = f.read()

    if 'BB-ADC' not in slots:
        # Load ADC cape
        try:
            with open(SLOTS, 'w') as f:
                f.write('BB-ADC')
        except IOError:
            return False

    with open(SLOTS, 'r') as f:
        slots = f.read()

    adc_setup = 'BB-ADC' in slots

    # Calculate paths
    if adc_setup:
        try:
            base_path = glob.glob('/sys/bus/iio/devices/iio:device?')[0]
        except IndexError:
            return False

        for _, pin in pins.items():
            path = os.path.join(base_path, 'in_voltage{:d}_raw'.format(pin.id))
            if not os.path.exists(path):
                return False
            pin.path = path
            fd = os.open(pin.path, os.O_RDONLY)
            # Check that it opened successfully
            if fd >= 0:
                pin.fd = fd

    return adc_setup


def read_raw(pin):
    """
    Read the ADC count straight from the Sysfs file, as a count

    :param pin:
        Pin name to read

    :return:
        12-bit count.
    """
    if pin not in pins:
        raise ValueError("%s is not an analog input pin" % pin)

    if not adc_setup:
        raise RuntimeError("ADC must be setup before use")

    pin = pins[pin]

    os.lseek(pin.fd, 0, os.SEEK_SET)
    value = int(os.read(pin.fd, 4))
    # if not os.path.exists(pin.path):
    #     raise RuntimeError("Sysfs file for {:s} disappeared".format(pin))

    # try:
    #     with open(pin.path, 'r') as f:
    #         value = int(f.read())
    # except IOError:
    #     raise RuntimeError("Could not read sysfs file for {:s}"
    #                        .format(pin))
    # except ValueError:
    #     raise RuntimeError("Invalid non-integer value from sysfs file")

    assert (0 <= value <= 4095)
    return value


def read_volts(pin):
    """
    Read the value from a pin, scaled to volts.

    :param pin:
        Pin name to read

    :return:
        voltage.
    """
    count = read_raw(pin)
    return count * (1.8 / 4095)


def cleanup(key=None):
    """
    Cleanup either a single pin or the entire ADC.

    :return: None

    :exception ValueError:
        raised if an invalid key is passed in.

    :exception RuntimeError:
        raised if there is an error closing.
    """
    if key:
        try:
            pin = pins[key]
        except KeyError:
            raise ValueError("Invalid key passed in")
        else:
            os.close(pin.fd)
    else:
        for pin in pins.values():
            if pin.fd:
                os.close(pin.fd)
