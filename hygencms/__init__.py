# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016
"""
HyGenCMS implements the control management system for Planetary Power's
HyGen generator. It has two main roles. First, it controls the RPM setpoint
for the engine, based on the trunk current as measured by an onboard
12-bit ADC. Second, it records data from a number of sources, including
a Battery Management System from Beckett, Modbus values from a DeepSea
7450, and Analog values from our onboard ADC.

The HyGenCMS module runs as multiple threads, one for each input source.
"""

__version__ = '0.1.0'

