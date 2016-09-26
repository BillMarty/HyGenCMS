# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

"""
The ADC module uses the Sysfs interface provided by the Linux kernel and
drivers to control and read from the analog inputs to the BeagleBone.
See the
`Users Guide <http://processors.wiki.ti.com/index.php/Linux_Core_ADC_User's_Guide>`_
for more details.

This module presumes that
all pinmuxing is done ahead-of-time for all pins which are to be used.
"""

import glob
import os
import time
import logging

from recordclass import recordclass

from .pins import normalize_pin

adc_setup = False


class AdcPin(recordclass('AdcPin', ['pin', 'id', 'path', 'fd'])):
    """
    Provide a namedtuple-like store for ADC pin information.

    :param pin:  The pin header and number
    :param id:  The ADC ID of that pin
    :param path:  The path to the sysfs file of the ADC count
    :param fd:  The file descriptor referring to the sysfs file
    """

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


def setup(logger):
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
        path_success = False
        #Apparently, file system additions due to adding BB-ADC cape take time, ...
        #   so we build in delay and retry :-)
        for delay in range(1,11):
            time.sleep(0.2)
            try:
                base_path = glob.glob('/sys/bus/iio/devices/iio:device?')[0]
            except IndexError:
                continue
            else:
                path_success = True
                break

        if path_success:
            logger.info('ADC path_success at delay = ' + str(delay))
            #print('ADC path_success at delay = ' + str(delay))
        else:
            logger.warning('ADC path failed!')
            #print('ADC path failed!')
            adc_setup = False
            return adc_setup

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
    Read the 12-bit ADC count straight from the sysfs file, as an int.

    :param pin:
        Pin name to read

    :return:
        12-bit count as an int
    """
    pin = normalize_pin(pin)
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
        voltage in volts, as a float
    """
    count = read_raw(pin)
    return count * (1.8 / 4095)


def cleanup(key=None):
    """
    Cleanup either a single pin or the entire ADC.

    :return: :const:`None`

    :exception ValueError:
        raised if an invalid key is passed in.

    :exception RuntimeError:
        raised if there is an error closing.
    """
    if key:
        key = normalize_pin(key)
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
