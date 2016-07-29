#!/usr/bin/env python3
# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

"""
Perform the telemetric logging functions as a daemon.

This wraps logger, ensuring proper daemon functionality,
including PID files, start / stop, and context management.
"""

# System imports
import argparse
import logging
import signal

from daemon import pidfile, DaemonContext

from hygencms.config import get_configuration
from hygencms.main import main

# Parse arguments
parser = argparse.ArgumentParser(description="Start the Hygen logging daemon")
parser.add_argument(
    '-c', '--config', action='store_const', dest='config', const=True,
    default=False, help='set configuration variables from the console')
parser.add_argument(
    '-d', '--daemon', action='store_const', dest='daemon', const=True,
    default=False, help='run the logger as a daemon')
parser.add_argument(
    '-w', '--watchdog', action='store_const', dest='watchdog', const=True,
    default=False, help='run the logger with a watchdog timer')
parser.add_argument(
    '-p', '--poweroff', action='store_const', dest='poweroff', const=True,
    default=False, help='Trigger poweroff on GPIO P8_19 input')
args = parser.parse_args()

# Handle --config
if args.config:
    config = get_configuration(from_console=True)
else:
    config = get_configuration()

# create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# create stream handler to stderr and set level to debug
sh = logging.StreamHandler()  # default is sys.stderr
sh.setLevel(logging.INFO)

# Create file handler
fh = logging.FileHandler(
    '/home/hygen/logs/errors.log')
fh.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

handlers = [sh, fh]
# add sh to logger
for h in handlers:
    h.setFormatter(formatter)
    logger.addHandler(h)

if args.daemon:
    # Setup daemon context
    context = DaemonContext(
        working_directory='/',
        pidfile=pidfile.PIDLockFile('/var/run/hygencms.pid'),
        files_preserve=[
            fh.stream,
        ],
        umask=0o002,
    )

    # Handle signals
    context.signal_map = {signal.SIGTERM: 'terminate',  # program cleanup
                          signal.SIGHUP: 'terminate',  # hangup
                          signal.SIGTSTP: 'terminate',  # suspend - configurable
                          }
    with context:
        main(config, handlers, daemon=True, watchdog=args.watchdog,
             power_off_enabled=args.poweroff)
else:
    main(config, handlers, daemon=False, watchdog=args.watchdog,
         power_off_enabled=args.poweroff)
