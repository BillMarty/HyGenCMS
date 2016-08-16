# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

"""
This module is the main loop for HyGenCMS software.

The primary functions of the main loop are as follows:

- Start all necessary threads to read data asynchronously from the
    DeepSea, BMS, and analog input pins
- Start the thread to write data to a USB memory stick or fallback
    location on local disk.
- Start the thread to control the Woodward's RPM setpoint based on
    the Analog trunk current value.
- Pass through analog current value to the RPM setpoint controller
    thread.
- Enable and disable the RPM setpoint controller.
- Compile and pass through csv lines of data to the file writer
    thread.
- Update fuel and battery gauges based on values from the DeepSea.
- Read the "USB eject" switch and pass through to the file writer.
- Update the tunings of the RPM setpoint controller.
- Check kill relay and shutdown if instructed to.
- Check if new USB is plugged in and pass through to file writer.
- Check if old USB is removed to turn off safe-to-remove LED.
- Handle exceptions which arise in the main loop.
"""

###############################
# Import required libraries
###############################
import logging
import socket
import subprocess
import sys
import time

import hygencms.analogclient
import hygencms.asyncio
import hygencms.bmsclient
import hygencms.filewriter
import hygencms.woodwardcontrol
import monotonic
import serial
from hygencms import usbdrive
from hygencms.deepseaclient import DeepSeaClient

from . import gpio
from . import pins
from . import utils
from .bbio_common import setup_io
from .config import get_configuration
from .groveledbar import GroveLedBar

#################################################
# Conditional import for Python 2/3 compatibility
#################################################
if sys.version_info[0] == 2:
    import Queue as queue
else:
    import queue

# Master values dictionary
# Keys should be one of
# a) Modbus address
# b) analog pin in
# c) our assigned "one true name" for each BMS variable
# d) PWM pin out for Woodward signals
data_store = {pins.GEN_CUR: None}


def main(config, handlers, daemon=False, watchdog=False, power_off_enabled=False):
    """
    Enter a main loop, polling values from sources enabled in config
    """
    logger = logging.getLogger(__name__)
    for h in handlers:
        logger.addHandler(h)
    logger.setLevel(logging.DEBUG)

    # Keep a list of all threads we have running
    threads = []
    clients = []

    # Keep an exit code variable so we can exit nicely
    exit_code = 0

    ############################################
    # Setup IO pins
    ############################################
    setup_io()

    ############################################
    # Async Data Sources
    ############################################
    deepsea = None
    if 'deepsea' in config['enabled']:
        try:
            deepsea = DeepSeaClient(config['deepsea'], handlers, data_store)
        except ValueError:
            exc_type, exc_value = sys.exc_info()[:2]
            logger.error("Error with DeepSeaClient config: %s: %s"
                         % (str(exc_type), str(exc_value)))
        except serial.SerialException as e:
            logger.error("SerialException({0}) opening BmsClient: {1}"
                         .format(e.errno, e.strerror))
        except socket.error:
            exc_type, exc_value = sys.exc_info()[:2]
            logger.error("Error opening BMSClient: %s: %s"
                         % (str(exc_type), str(exc_value)))
        else:
            clients.append(deepsea)
            threads.append(deepsea)

    analog = None
    if 'analog' in config['enabled']:
        try:
            analog = hygencms.analogclient.AnalogClient(config['analog'], handlers, data_store)
        except ValueError:
            exc_type, exc_value = sys.exc_info()[:2]
            logger.error("Configuration error from AnalogClient: %s: %s"
                         % (str(exc_type), str(exc_value)))
        except RuntimeError:
            exc_type, exc_value = sys.exc_info()[:2]
            logger.error(
                "Error opening the analog to digital converter: %s: %s"
                % (str(exc_type), str(exc_value)))
        else:
            clients.append(analog)
            threads.append(analog)

    bms = None
    if 'bms' in config['enabled']:
        try:
            bms = hygencms.bmsclient.BmsClient(config['bms'], handlers)
        except serial.SerialException as e:
            logger.error("SerialException({0}) opening BmsClient: {1}"
                         .format(e.errno, e.strerror))
        except (OSError, IOError):
            exc_type, exc_value = sys.exc_info()[:2]
            logger.error("Error opening BMSClient: %s: %s"
                         % (str(exc_type), str(exc_value)))
        except ValueError:
            logger.error("ValueError with BmsClient config")
        else:
            clients.append(bms)
            threads.append(bms)

    #######################################
    # Other Threads
    #######################################
    woodward = None
    if 'woodward' in config['enabled']:
        try:
            woodward = hygencms.woodwardcontrol.WoodwardControl(
                config['woodward'], handlers
            )
        # ValueError can be from a missing value in the config map
        # or from an error in the parameters to PWM.start(...)
        except ValueError as e:
            logger.error("ValueError: %s"
                         % (e.args[0]))
            exit("WoodwardControl thread did not start")
        else:
            clients.append(woodward)
            threads.append(woodward)

    filewriter = None
    if 'filewriter' in config['enabled']:
        headers = []
        for c in clients:
            headers.append(c.csv_header())

        if len(headers) == 0:
            logger.error("CSV header returned by clients is blank")

        headers.append("output_woodward")
        csv_header = "linuxtime," + ','.join(headers)
        log_queue = queue.Queue()
        try:
            filewriter = hygencms.filewriter.FileWriter(
                config['filewriter'], handlers, log_queue, csv_header
            )
        except ValueError as e:
            logger.error("FileWriter did not start with message \"{0}\""
                         .format(str(e)))
        except (IOError, OSError) as e:
            logger.error("FileWriter did not start with message \"{0}\""
                         .format(str(e)))
        else:
            threads.append(filewriter)
    else:
        log_queue = None

    # Check whether we have some input
    if len(clients) == 0:
        logger.error("No clients started successfully. Exiting.")
        exit("No clients started successfully. Exiting.")  # Exits with code 1

    # We must always have Woodward thread and Analog thread at a minimum
    if not woodward or not analog:
        logger.error("Woodward or Analog client missing")
        exit("Woodward or Analog client did not start successfully. Exiting.")

    ######################################
    # LED Gauges
    ######################################
    fuel_gauge = GroveLedBar(pins.FUEL_DATA, pins.FUEL_CLK)
    battery_gauge = GroveLedBar(pins.BAT_GG_DATA, pins.BAT_GG_CLK)

    # Start all the threads
    for thread in threads:
        thread.start()

    # Keeps track of the next scheduled time for each interval
    # Key = period of job
    # value = monotonic scheduled time
    next_run = {
        0.1: 0,
        0.5: 0,
        1.0: 0,
        5.0: 0,
        10.0: 0,
        60.0: 0,
    }

    going = True
    shutdown = False
    ejecting = False
    while going:
        # noinspection PyBroadException
        try:
            now = monotonic.monotonic()
            now_time = time.time()
            csv_parts = [str(now_time)]

            ###########################
            # Every tenth of a second
            ###########################
            if now >= next_run[0.1]:
                # Get CSV data to the log file
                for client in clients:
                    csv_parts.append(client.csv_line())
                # Put the csv data in the logfile
                if len(csv_parts) > 0 and log_queue:
                    try:
                        log_queue.put(','.join(csv_parts))
                    except queue.Full:
                        exit("File writer queue full. Exiting.")

                # Connect the analog current in to the woodward process
                if woodward and not woodward.cancelled:
                    try:
                        cur = data_store["P9_40"]
                        if cur is not None:
                            woodward.process_variable = cur
                    except UnboundLocalError:
                        pass
                    except KeyError:
                        logger.critical('Generator current is not being measured.')
                        woodward.cancel()

                # Schedule next run
                next_run[0.1] = now + 0.1

            ###########################
            # Twice a second
            ###########################
            if now >= next_run[0.5]:
                # Connect the on / off signal from the deepSea to the PID
                try:
                    # Virtual LED 1
                    # From DeepSea GenComm manual, 10.57
                    pid_enable = data_store[191*256 + 0]
                    if not woodward.in_auto and pid_enable:
                        woodward.integral_term = 0.0
                        woodward.set_auto(True)
                    elif not pid_enable:
                        woodward.set_auto(False)
                        woodward.output = 0.0
                        woodward.integral_term = 0.0
                except UnboundLocalError:
                    pass
                except KeyError:
                    logger.critical("Key does not exist for the PID enable flag")

                # Check the eject button to see whether it's held
                if gpio.read(pins.USB_SW) == gpio.LOW and not ejecting:
                    filewriter.eject_drive = True
                    ejecting = True

                # Schedule next run
                next_run[0.5] = now + 0.5

            ###########################
            # Once a second
            ###########################
            if now >= next_run[1.0]:
                # If not in daemon, print to screen
                if not daemon:
                    print_data(clients)

                # Read in the config file to update the tuning coefficients
                try:
                    wc = get_configuration()['woodward']
                except IOError:
                    pass
                else:
                    woodward.set_tunings(wc['Kp'], wc['Ki'], wc['Kd'])
                    woodward.setpoint = wc['setpoint']

                if check_kill_switch():
                    going = False
                    shutdown = True

                # Schedule next run
                next_run[1.0] = now + 1.0

            ###########################
            # Once every 5 seconds
            ###########################
            if now >= next_run[5.0]:
                if watchdog:
                    update_watchdog()

                # Check for new USB drive
                plugged = usbdrive.plugged()
                if plugged:
                    mounted = usbdrive.mounted()
                    if mounted is None and not ejecting:
                        filewriter.mount_drive = plugged
                    # If the USB changes locations without realizing it
                    # (sometimes happens at startup), eject "mounted"
                    # drive (not actually working) and once we've un-
                    # mounted, we'll mount the new location.
                    elif mounted != plugged:
                        filewriter.eject_drive = True
                        ejecting = True

                # If we're ejecting and the drive is gone, turn off light
                if ejecting and not plugged:
                    filewriter.safe_to_remove = False
                    ejecting = False

                # Schedule next run
                next_run[5.0] = now + 5.0

            ###########################
            # Once every 10 seconds
            ###########################
            if now >= next_run[10.0]:
                # Ensure analog and woodward control are running
                if analog.cancelled or woodward.cancelled:
                    logger.error("Missing analog or woodward")
                    going = False
                    exit_code = 1
                # Schedule next run
                next_run[10.0] = now + 10.0

            ###########################
            # Once every minute
            ###########################
            if now >= next_run[60.0]:
                update_gauges(fuel_gauge, battery_gauge)

                # Schedule next run
                next_run[60.0] = now + 60.0

            time.sleep(0.01)

        except KeyboardInterrupt:
            going = False
            # Standard exit code when interrupted by Ctrl-C
            # http://tldp.org/LDP/abs/html/exitcodes.html
            exit_code = 130
            stop_threads(threads)

        except SystemExit:
            going = False
            exit_code = 0
            stop_threads(threads)

        except Exception as e:  # Log any other exceptions
            utils.log_exception(logger, e)

    if shutdown and power_off_enabled:
        power_off()
    exit(exit_code)


def stop_threads(threads):
    """
    Stop each thread in the list, preparatory to shutdown

    :param threads: A list of AsyncIOThread objects to shutdown
    :return: None
    """
    for thread in threads:
        thread.cancel()
        thread.join()


def print_data(clients):
    """
    Print the data for all the data source clients
    :param clients: A list of clients with a print_data function
    :return: None
    """
    for client in clients:
        client.print_data()
    print('-' * 80)


def update_watchdog():
    """
    Write to the watchdog file, keeping the system from being
    restarted. If we don't write to the watchdog for 60 seconds, the
    system will be restarted.

    :return: None
    """
    with open("/dev/watchdog", 'w') as f:
        f.write('\n')


def update_gauges(fuel_gauge, battery_gauge):
    """
    Update both the fuel and the battery gauge using data from the
    central data store.

    :param fuel_gauge: GroveLedBar object, the fuel gauge
    :param battery_gauge: GroveLedBar object, the battery gauge
    :return: None
    """
    # Update interface gauges
    # See DeepSea_Modbus_manualGenComm.docx, 10.6
    try:
        fuel = data_store[DeepSeaClient.FUEL_LEVEL]
        assert (fuel is not None)
    except KeyError:
        fuel_gauge.set_bar_level(1)
    except AssertionError:
        fuel_gauge.set_bar_level(1)
    else:
        fuel /= 10  # Scale to 10
        fuel_gauge.set_bar_level(fuel)

    # See DeepSea_Modbus_manualGenComm.docx, 10.6 (#199)
    try:
        battery_charge = data_store[DeepSeaClient.BATTERY_LEVEL]
        # TODO maybe replace this with our analog value
        assert (battery_charge is not None)
    except KeyError:
        battery_gauge.set_bar_level(1)
    except AssertionError:
        battery_gauge.set_bar_level(1)
    else:
        # Scale the range from 259 to 309 to 0-10
        # noinspection PyTypeChecker
        battery_charge = int(round((battery_charge - 259) * 0.2))
        battery_gauge.set_bar_level(battery_charge)


kill_last = False
kill_now = False


def check_kill_switch():
    """
    Check whether we are to poweroff now. Only return when the switch
    has been set for two iterations.

    :return: Whether to poweroff.
    """
    global kill_now, kill_last
    value = gpio.read(pins.OFF_SWITCH)
    kill_last = kill_now
    kill_now = value == gpio.HIGH  # TODO not sure whether this should be high or low
    return kill_now and kill_last


def power_off():
    """
    Shut down the system immediately.

    :return: None
    """
    subprocess.call(["poweroff"])

