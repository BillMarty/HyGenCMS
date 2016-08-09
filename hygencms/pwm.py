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
`here <https://github.com/cdsteinkuehler/beaglebone-universal-io>`_.

This module requires a Linux kernel >= 4.1, in order for the ``sysfs``
file paths in the library to work.

Each pin must be started before setting its frequency or duty cycle.

Every pin name argument uses the notation on the BeagleBone Black:
Pa_bb, where ``a = header number`` and ``bb = pin number``.
"""

import glob
import os
import os.path as path
import platform
import subprocess
import time

from .bbio_common import setup_io, universal_cape_present

if not platform.uname()[0] == 'Linux' and platform.release() >= '4.1.0':
    raise EnvironmentError('Requires Linux >=4.1.0')


class PwmPin:
    def __init__(self,
                 chip, addr, index,
                 name=None,
                 description=None,
                 period_fd=None,
                 duty_fd=None,
                 polarity_fd=None,
                 enable_fd=None,
                 duty=50.0,
                 freq=100000):
        self.chip = chip
        self.addr = addr
        self.index = index
        self.name = name
        self.description = description
        self.period_fd = period_fd
        self.duty_fd = duty_fd
        self.polarity_fd = polarity_fd
        self.enable_fd = enable_fd
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

    if not universal_cape_present():
        setup_io()

    # Mux the pin
    subprocess.call(['config-pin', pin_name, 'pwm'])

    if not universal_cape_present():
        raise ValueError("Could not setup IO pins")

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

    pin.period_fd = os.open(period_path, os.O_RDWR)
    pin.duty_fd = os.open(duty_cycle_path, os.O_RDWR)
    pin.polarity_fd = os.open(polarity_path, os.O_RDWR)
    pin.enable_fd = os.open(enable_path, os.O_RDWR)
    pin.duty = 0
    pin.freq = 0

    pin.initialized = True

    # It sometimes takes a bit to open
    enabled = False
    tries = 0
    while not enabled and tries < 100:
        time.sleep(0.01)
        os.lseek(pin.enable_fd, 0, os.SEEK_SET)
        n = os.write(pin.enable_fd, bytes('1', encoding='utf-8'))

        if n <= 0:
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
    pin.freq = freq

    period_ns = int(1e9 / freq)

    # If we're shortening the period, update the
    # duty cycle first, to avoid ever setting the
    # period to a value < duty cycle (which raises
    # an error in the kernel)
    if period_ns < pin.period_ns:
        pin.period_ns = period_ns

        # Calculate updated duty cycle
        duty_ns = int((pin.duty / 100.) * period_ns)

        os.lseek(pin.duty_fd, 0, os.SEEK_SET)
        n1 = os.write(pin.duty_fd,
                      bytes("{:d}".format(duty_ns), encoding='utf-8'))

        os.lseek(pin.period_fd, 0, os.SEEK_SET)
        n2 = os.write(pin.period_fd,
                      bytes("{:d}".format(period_ns), encoding='utf-8'))

    # if we're lengthening the period, update the
    # period first, in order to avoid ever setting
    # the duty cycle to a value > period (which raises
    # an error in the kernel)
    elif period_ns > pin.period_ns:
        pin.period_ns = period_ns

        os.lseek(pin.period_fd, 0, os.SEEK_SET)
        n1 = os.write(pin.period_fd,
                      bytes("{:d}".format(period_ns), encoding='utf-8'))

        # Calculate updated duty cycle
        duty_ns = int((pin.duty / 100.) * period_ns)

        os.lseek(pin.duty_fd, 0, os.SEEK_SET)
        n2 = os.write(pin.duty_fd,
                      bytes("{:d}".format(duty_ns), encoding='utf-8'))
    else:
        return

    # If we had an error writing to the files
    if n1 < 0 or n2 < 0:
        raise RuntimeError("Could not update frequency")
    elif n1 + n2 == 0:
        raise RuntimeError("Wrote a total of 0 bytes - failure")

    return


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

    duty_ns = int(pin.period_ns * (duty / 100))

    # Write to file
    os.lseek(pin.duty_fd, 0, os.SEEK_SET)
    n = os.write(pin.duty_fd, bytes("{:d}".format(duty_ns), encoding='utf-8'))

    if n <= 0:
        print("Error writing to {:s}".format(pin.duty_path))
    pin.duty = duty


def stop(key):
    """
    Stop a PWM from running.

    :param key: The pin name
    :return: None

    :exception ValueError:
        Raised if the pin name entered is invalid.
    :exception RuntimeError:
        If there is an error stopping the pin or the
        pin has not been initialized.
    """
    try:
        pin = pins[key]
    except KeyError:
        raise ValueError("Unimplemented key")

    if not pin.initialized:
        raise RuntimeError("{:s} has not been initialized".format(key))

    # Write 0 to the enable file descriptor
    os.lseek(pin.enable_fd, 0, os.SEEK_SET)
    n = os.write(pin.enable_fd, bytes('0', encoding='utf-8'))

    # n will be the number of bytes written, or -1 for error
    if n <= 0:
        raise RuntimeError("Could not stop PWM.")

    # Close file descriptors
    os.close(pin.period_fd)
    os.close(pin.enable_fd)
    os.close(pin.duty_fd)
    os.close(pin.polarity_fd)
