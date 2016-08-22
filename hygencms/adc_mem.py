# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

"""
The ADC Mem module uses memory mapping to directly control the ADC
using the hardware. The most useful reference for this approach is
the am335x Technical Reference Manual. This module attempts to
retain compatibility with the adc.py module's API, while changing the
implementation behind the scenes.

This module presumes that all pinmuxing is done ahead-of-time for all
pins which are to be used.


References:
-----------
    [1] am335x Technical Reference Manual
"""

from .pins import normalize_pin

adc_setup = False

# Base addresses
ADC_TSC_offset = 0x44E0D000
ADC_TSC_size = 0x44E0EFFF - ADC_TSC_offset

# CTRL register
# We will perform the following non-default configurations:
# StepConfig_WriteProtect - bit 2, set high (make writable)
# Step_ID_tag - Store the Step ID number with the captured ADC data
# in the FIFO (channel ID tag)
#
# Documented in [1] 12.5.1.10 (p.1808)
CTRL_offset = 0x40

# STEPENABLE Register
# Documented in [1] 12.5.1.15 (p.1813)
STEPENABLE_offset = 0x54

# IDLECONFIG Register
# Documented in [1] 12.5.1.16 (p.1814)
IDLECONFIG_offset = 0x58
# This allows each step to be configured (muxes for reference and
# measured voltages to be read). We want the following values:
# RFM (negative reference voltage) = VREFN
# INP (in positive voltage) = Channel #
# INM (In negative voltage) = VREFN (ground, see BBB schematic, p.4/11)
# RFP (positive reference voltage) = VREFP


# STEPCONFIGx Registers
# Documented in [1] 12.5.1.19 - 12.5.1.
def STEPCONFIGx_offset(x):
    """
    Return the offset for the config register of step x.

    :param x:
        The step to find

    :return:
        The memory offset from the ADC_TSC base offset.
    """
    if type(x) is not int:
        raise ValueError("x is not an integer")
    elif not 1 <= x <= 16:
        raise ValueError("x is not in range")
    else:
        return 0x64 + 8 * (x - 1)


# STEPDELAYx Registers
# Documented in [1] 12.5.1.20 - 12.5.1.
def STEPDELAYx_offset(x):
    """
    Return the offset for the delay register of step x.

    :param x:
        The step to find.

    :return:
        The memory offset from the ADC_TSC base offset.

    :exception ValueError:
        Raised if x is not an integer 1 <= x <= 16.
    """
    if type(x) is not int:
        raise ValueError("x is not an integer")
    elif not 1 <= x <= 16:
        raise ValueError("x is not in range")
    else:
        return 0x68 + 8 * (x - 1)

# FIFOnCOUNT Register
# Bits 6:0 contain the number of words in FIFOn
# Documented in [1] 12.5.1.51 (p.1867)
FIFO0_COUNT_offset = 0xE4
FIFO1_COUNT_offset = 0xF0

pins = {
    'P9_33': AdcPin('P9_33', 4, None, None),
    'P9_35': AdcPin('P9_35', 6, None, None),
    'P9_36': AdcPin('P9_36', 5, None, None),
    'P9_37': AdcPin('P9_37', 2, None, None),
    'P9_38': AdcPin('P9_38', 3, None, None),
    'P9_39': AdcPin('P9_39', 0, None, None),
    'P9_40': AdcPin('P9_40', 1, None, None),
}


def setup():
    """
    Setup the ADC for use. Load the ADC cape if needed.

    :return:
        :const:`True` if ADC ready for use, else :const:`False`.
    """
    pass


def read_raw(pin):
    """
    Read the 12-bit ADC count straight from the sysfs file, as an int.

    :param pin:
        Pin name to read

    :return:
        12-bit count as an int
    """
    pass


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
    pass
