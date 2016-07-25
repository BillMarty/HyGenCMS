#!/usr/bin/env python3
"""
Perform the telemetric logging functions as a daemon.

This wraps logger, ensuring proper daemon functionality,
including PID files, start / stop, and context management.
"""

# System imports
import argparse
import logging
import signal
import subprocess

from daemon import pidfile

# Our Imports
import hygencms
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
args = parser.parse_args()

# Handle --config
if args.config:
    config = get_configuration(from_console=True)
else:
    config = get_configuration()

# Run the shell script to setup IO pins
subprocess.call(["bash", "../setup_io.sh"])

# create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# create stream handler to stderr and set level to debug
sh = logging.StreamHandler()  # default is sys.stderr

# Create file handler
fh = logging.FileHandler(
    '/home/hygen/log/errors.log')

# create formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

handlers = [sh, fh]
# add sh to logger
for h in handlers:
    h.setLevel(logging.DEBUG)
    h.setFormatter(formatter)
    logger.addHandler(h)

if args.daemon:
    # Setup daemon context
    context = daemon.DaemonContext(
        working_directory='/',
        pidfile=pidfile.PIDLockFile('/var/run/hygenlogger.pid'),
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
        main(config, handlers)
else:
    main(config, handlers)

