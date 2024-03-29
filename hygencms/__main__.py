#!/usr/bin/env python3
# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

"""
Open the HyGenCMS program, possibly as a daemon.

This wraps logger, ensuring proper daemon functinality,
including PID files, start / stop, and context management.
"""

# System imports
import argparse
import logging
import signal
import os

from daemon import pidfile, DaemonContext

from .config import defaults
from .main import main as main_entry

debug = True


def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="Start the Hygen logging daemon")
    parser.add_argument(
        '-d', '--daemon', action='store_const', dest='daemon', const=True,
        default=False, help='run the logger as a daemon')
    parser.add_argument(
        '-w', '--watchdog', action='store_const', dest='watchdog', const=True,
        default=False, help='run the logger with a watchdog timer')
    parser.add_argument(
        '-t', '--time', action='store_const', dest='time', const=True,
        default=False, help='Set system time from DeepSea')
    args = parser.parse_args()

    # Get configuration
    config = defaults

    # create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    handlers = []

    # create stream handler to stderr and set level to debug
    sh = logging.StreamHandler()  # default is sys.stderr
    sh.setLevel(logging.INFO)
    handlers.append(sh)

    # Only use errors log if we're debugging
    # We don't want to use up our write cycles in production.
    fh = None
    if debug:
        # Make sure the logs directory exists
        dir_contents = os.listdir('/home/hygen')
        if 'logs' not in dir_contents:
            try:
                os.chdir('/home/hygen')
                os.mkdir('logs', mode = 0o777)
            except:
                # No place to log the exception yet :-|
                pass

        # Create file handler
        fh = logging.FileHandler('/home/hygen/logs/errors.log')
        fh.setLevel(logging.INFO)
        handlers.append(fh)

    # create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # add handlers to logger
    for h in handlers:
        h.setFormatter(formatter)
        logger.addHandler(h)

    if args.daemon:
        # Setup daemon context
        if fh:
            context = DaemonContext(
                working_directory='/',
                pidfile=pidfile.PIDLockFile('/var/run/hygencms.pid'),
                files_preserve=[
                    fh.stream,
                ],
                umask=0o002,
            )
        else:
            context = DaemonContext(
                working_directory='/',
                pidfile=pidfile.PIDLockFile('/var/run/hygencms.pid'),
                umask=0o002,
            )

        # Handle signals
        context.signal_map = {signal.SIGTERM: 'terminate',  # program cleanup
                              signal.SIGHUP: 'terminate',  # hangup
                              signal.SIGTSTP: 'terminate',  # suspend - configurable
                              }
        with context:
            main_entry(config, handlers, daemon=True, watchdog=args.watchdog, time_from_deepsea=args.time)
    else:
        main_entry(config, handlers, daemon=False, watchdog=args.watchdog, time_from_deepsea=args.time)


if __name__ == '__main__':
    main()
