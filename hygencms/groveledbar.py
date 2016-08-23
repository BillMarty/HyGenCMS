# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

"""
This module provides the GroveLedBar class, which implements a driver for the
Grove LED Bar v2.0. This bar, available from Grove electronics, provides ten
LED segments, which represent a gauge.
"""

import time

from . import gpio

LEDS_PER_INSTANCE = 12
HIGH = 0x77
LOW = 0x00
RED = 0x44


class GroveLedBar:
    """
    Driver for the Grove LED Bar 2.0.
    Modeled very closely off the my9221 and groveledbar drivers on UPM
    https://github.com/Pillar1989/upm/blob/BBGW/src/my9221
    """

    def __init__(self, data_pin, clock_pin):
        """
        :param data_pin:
            Pin to use for data.

        :param clock_pin:
            Pin for clock.
        """
        self._data_pin = data_pin
        self._clock_pin = clock_pin
        self._auto_refresh = True
        self._command_word = 0x0000
        self._clock_high = False
        self._bit_states = [0] * 12
        self._clock_state = True

    def set_auto_refresh(self, enable):
        """
        Enable auto-refreshing on changes.
        
        :param enable:
            Whether to enable the auto-refreshing
        """
        self._auto_refresh = bool(enable)

    def set_bar_level(self, level, invert_direction=False):
        """
        Set the LED bar level.

        :param level:
            Level to set.

        :param invert_direction:
            Fill the bar in the opposite direction.
        """
        if level > 10:
            level = 10

        if not invert_direction:
            self._bit_states[0] = RED if 0 < level else LOW
            for i in range(1, LEDS_PER_INSTANCE):
                self._bit_states[i] = HIGH if i < level else LOW
        else:
            self._bit_states[0] = RED if 10 == level else LOW
            for i in range(LEDS_PER_INSTANCE):
                self._bit_states[i] = HIGH if (12 - i) < (level + 2) else LOW

        if self._auto_refresh:
            self.refresh()

    def refresh(self):
        """
        Send the current state of the object out to the bar
        """
        for i in range(LEDS_PER_INSTANCE):
            self.send_16_bit_block(self._bit_states[i])

        self.lock_data()

    def lock_data(self):
        """
        Ensure the data is set in the LED bar.
        """
        gpio.write(self._data_pin, 0)
        # We don't need a sleep here to latch data,
        # because we're not driving multiple bars
        # in series.
        for i in range(4):
            gpio.write(self._data_pin, 1)
            gpio.write(self._data_pin, 0)
            # same here

    def send_16_bit_block(self, data):
        """
        Send a 16-bit block of bytes.

        :param data:
            16-bits, as an integer.
        """
        for i in range(16):
            gpio.write(self._data_pin, data & 0x8000)
            self._clock_state = not self._clock_state
            gpio.write(self._clock_pin, self._clock_state)
            data <<= 1


def main():
    """
    A testing routine
    """
    bar = GroveLedBar("P9_12", "P9_15")

    while True:
        for i in range(11):
            bar.set_bar_level(i)
            time.sleep(1.0)


if __name__ == "__main__":
    main()
