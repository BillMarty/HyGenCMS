# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016
"""
This module provides a wrapper around the sysfs interface to the
BeagleBone PWM system. It operates by writing to files in the ``/sys``
directory. Therefore, it either must be run as root, or permissions
must be adjusted in such a way that the files are writable by non-root.

This module supports all PWM pins that are implemented on the
BeagleBone Black. Before using this library, each pin must be correctly
pinmuxed for PWM and its Device Tree Overlay must have been loaded. The
recommended way to do this is via the BeagleBone Universal IO library
[here](https://github.com/cdsteinkuehler/beaglebone-universal-io).

This module requires a Linux kernel >= 4.1, in order for the ``sysfs``
file paths in the library to work.

Each pin must be started before setting its frequency or duty cycle.

Every pin name argument uses the notation on the BeagleBone Black:
Pa_bb, where ``a = header number`` and ``bb = pin number``.
"""


import glob
import os.path as path
import time
import platform

if not platform.uname()[0] == 'Linux' and platform.release() >= '4.1.0':
    raise EnvironmentError('Requires Linux >=4.1.0')


class PwmPin:
    def __init__(self,
                 chip, addr, index,
                 name=None,
                 description=None,
                 period_path=None,
                 duty_path=None,
                 polarity_path=None,
                 duty=50.0,
                 freq=100000):
        self.chip = chip
        self.addr = addr
        self.index = index
        self.name = name
        self.description = description
        self.period_path = period_path
        self.duty_path = duty_path
        self.polarity_path = polarity_path
        self.period_ns = 0
        self.duty = duty
        self.freq = freq
        self.initialized = False


pins = {
    'P8_13': PwmPin(chip='48304000',
                    addr='48304200',
                    index=1),
    'P8_19': PwmPin(chip='48304000',
                    addr='48304200',
                    index=0),
    'P8_34': PwmPin(chip='48302000',
                    addr='48302200',
                    index=1),
    'P8_36': PwmPin(chip='48302000',
                    addr='48302200',
                    index=0),
    'P8_45': PwmPin(chip='48304000',
                    addr='48304200',
                    index=0),
    'P8_46': PwmPin(chip='48304000',
                    addr='48304200',
                    index=1),
    'P9_14': PwmPin(chip='48302000',
                    addr='48302200',
                    index=0),
    'P9_16': PwmPin(chip='48302000',
                    addr='48302200',
                    index=1),
    'P9_21': PwmPin(chip='48300000',
                    addr='48300200',
                    index=1,
                    name='OLD_WW_PWM',
                    description='[old] PWM signal to Woodward RPM setpoint'),
    'P9_22': PwmPin(chip='48300000',
                    addr='48300200',
                    index=0),
    'P9_24': PwmPin(chip='48304000',
                    addr='48304100',
                    index=2),
    'P9_29': PwmPin(chip="48300000",
                    addr='48300200',
                    index=1,
                    name='WW_PWM',
                    description='PWM signal to Woodward RPM setpoint'),
    'P9_31': PwmPin(chip='48300000',
                    addr='48300200',
                    index=0,
                    name='SOC_PWM',
                    description='State of Charge analog signal'),
    'P9_42': PwmPin(chip='48300000',
                    addr='48300100',
                    index=0),
}

ocp_path = '/sys/devices/platform/ocp'


def start(pin_name, duty_cycle=50.0, frequency=100000):
    """
    Start a PWM pin.

    :param pin_name: The pin name
    :param duty_cycle: Initial duty cycle
    :param frequency: Initial frequency

    :exception ValueError:
        Raised if the pin name entered is invalid.
    :exception RunTimeError:
        Raised if unable to start the PWM pin.
    """
    try:
        pin = pins[pin_name]
    except KeyError:
        raise ValueError("PWM pin not implemented")

    chip_path = path.join(ocp_path,
                          pin.chip + '.epwmss')
    if not path.exists(chip_path):
        raise RuntimeError("Could not find PWM subsystem")

    try:
        addr_path = glob.glob(chip_path + '/' + pin.addr + '.*')[0]
    except IndexError:
        raise RuntimeError("Could not find PWM address")

    try:
        pwm_path = glob.glob(addr_path + '/pwm/pwmchip?')[0]
    except IndexError:
        raise RuntimeError("Could not find any PWM chip")

    # Export the correct pin
    export_path = path.join(
        pwm_path,
        'export',
    )
    try:
        export_file = open(export_path, 'w')
    except IOError:
        raise RuntimeError("Could not find export file")
    else:
        export_file.write(str(pin.index))

    # Try to open the directory
    pwm_dir = path.join(
        pwm_path,
        'pwm' + str(pin.index)
    )

    period_path = path.join(pwm_dir, 'period')
    duty_cycle_path = path.join(pwm_dir, 'duty_cycle')
    polarity_path = path.join(pwm_dir, 'polarity')
    enable_path = path.join(pwm_dir, 'enable')
    if not path.exists(period_path) \
            and path.exists(duty_cycle_path) \
            and path.exists(enable_path) \
            and path.exists(polarity_path):
        raise RuntimeError("Missing sysfs files")

    pin.period_path = period_path
    pin.duty_path = duty_cycle_path
    pin.polarity_path = polarity_path
    pin.duty = 0
    pin.freq = 0

    pin.initialized = True

    # It sometimes takes a bit to open
    enabled = False
    tries = 0
    while not enabled and tries < 100:
        time.sleep(0.01)
        try:
            with open(enable_path, 'w') as f:
                f.write('1')
        except OSError:
            tries += 1
        else:
            enabled = True

    if tries >= 100:
        pin.initialized = False
        raise RuntimeError("Couldn't enable {:s}".format(pin_name))

    set_frequency(pin_name, frequency)
    set_duty_cycle(pin_name, duty_cycle)


def set_frequency(pin_name, freq):
    """
    Set the frequency for a PWM pin.

    :param pin_name: The pin name
    :param freq: Frequency in Hz

    :exception ValueError:
        Raised if the pin name entered is invalid.
    :exception RuntimeError:
        Raised if the pin has not been initialized first.
    """
    try:
        pin = pins[pin_name]
    except KeyError:
        raise ValueError("Unimplemented key")

    if not pin.initialized:
        raise RuntimeError("Pin has not been initialized")

    if pin.freq == freq:
        return  # nothing to do

    period_ns = int(1e9 / freq)
    try:
        with open(pin.period_path, 'w') as f:
            f.write(str(period_ns))
    except OSError as e:
        print("Error writing to {:s}: {:s}".format(pin.period_path, str(e)))
    pin.period_ns = period_ns
    pin.freq = freq
    set_duty_cycle(pin_name, pin.duty)  # stay constant after changing period


def set_duty_cycle(key, duty):
    """
    Set the duty cycle for a pin.

    :param key: The pin name
    :param duty: The new duty cycle between 0 and 100 inclusive

    :exception ValueError:
        Raised if the pin name entered is invalid or
        if the duty cycle given is out of range.
    :exception RuntimeError:
        Raised if the pin has not been initialized first.
    """
    try:
        pin = pins[key]
    except KeyError:
        raise ValueError("Unimplemented key")

    if not pin.initialized:
        raise RuntimeError("Pin has not been initialized")

    if not 0 <= duty <= 100:
        raise ValueError("Duty cycle must be between 0 and 100 percent")

    duty_cycle = int(pin.period_ns * (duty / 100))
    try:
        with open(pin.duty_path, 'w') as f:
            f.write(str(duty_cycle))
    except OSError as e:
        print("Error writing to {:s}: {:s}".format(pin.duty_path, str(e)))
    pin.duty = duty
