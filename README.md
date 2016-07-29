# HyGenCMS
Communication Management System Software Development

# Hardware Interface:

The pin lists are located in three places, which should be kept synchronized. `SBC_IO.xlsx` formats them visually in a way that makes it easy to see what pins are used. `logger/pins.py` assigns the names used on the schematic to the standard string representations of the pin name (e.g. "P9_21"). The `setup_io.sh` script uses the `config-pin` utility from the [Univeral Beaglebone IO Library](https://github.com/cdsteinkuehler/beaglebone-universal-io) to setup all the pins to their expected values for the program to run. It also documents all the pin functions.

# Installation

Follow the documentation in the [Linux setup guide](LINUX_SETUP.md).