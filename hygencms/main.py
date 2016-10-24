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
from os import path

import monotonic
import serial
import ast

from . import gpio
from . import pins
from . import usbdrive
from . import utils
from .analogclient import AnalogClient
from .bbid import MAC_ID0
from .bbio_common import setup_io
from .bmsclient import BmsClient
from .config import TUNING_FILE
from .deepseaclient import DeepSeaClient
from .filewriter import FileWriter
from .groveledbar import GroveLedBar
from .woodwardcontrol import WoodwardControl

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


def main(config, handlers, daemon=False, watchdog=False, time_from_deepsea=False):
    """
    Enter a main loop, polling values from sources enabled in config.

    :param config:
        The master configuration map, containing a list of enabled data
        sources, global configuration values, and configuration maps
        specific to each enabled thread.

    :param handlers:
        An iterable of log handlers, which will be added to each logger
        throughout the program.

    :param daemon:
        A Boolean of whether to run the program as a daemon or in the
        foreground.

    :param watchdog:
        A Boolean of whether to use the hardware watchdog timer on the
        BeagleBone Black.

    :param time_from_deepsea:
        A Boolean of whether to set the Linux system time from the
        DeepSea time.
    """
    logger = logging.getLogger(__name__)
    for h in handlers:
        logger.addHandler(h)
    logger.setLevel(logging.DEBUG)

    # Make the logger reference available everywhere.
    global logger

    # Keep a list of all threads we have running
    threads = []
    clients = []

    # Keep an exit code variable so we can exit nicely
    exit_code = 0

    ############################################
    # Setup IO pins
    ############################################
    setup_io()
    time.sleep(1)

    ############################################
    # Async Data Sources
    ############################################
    try:
        deepsea = DeepSeaClient(config['deepsea'], handlers, data_store)
    except ValueError:
        exc_type, exc_value = sys.exc_info()[:2]
        logger.error("Error with DeepSeaClient config: %s: %s"
                     % (str(exc_type), str(exc_value)))
        exit("Could not open DeepSeaClient")
    except serial.SerialException as e:
        logger.error("SerialException({0}) opening BmsClient: {1}"
                     .format(e.errno, e.strerror))
        exit("Could not open DeepSeaClient")
    except socket.error:
        exc_type, exc_value = sys.exc_info()[:2]
        logger.error("Error opening BMSClient: %s: %s"
                     % (str(exc_type), str(exc_value)))
        exit("Could not open DeepSeaClient")
    else:
        clients.append(deepsea)
        threads.append(deepsea)

    analog = None
    try:
        analog = AnalogClient(config['analog'], handlers, data_store)
    except ValueError:
        exc_type, exc_value = sys.exc_info()[:2]
        logger.error("Configuration error from AnalogClient: %s: %s"
                     % (str(exc_type), str(exc_value)))
        exit("Could not open AnalogClient")
    except RuntimeError:
        exc_type, exc_value = sys.exc_info()[:2]
        logger.error(
            "Error opening the analog to digital converter: %s: %s"
            % (str(exc_type), str(exc_value)))
        exit("Could not open AnalogClient")
    else:
        clients.append(analog)
        threads.append(analog)

    bms_queue = queue.Queue()
    try:
        bms = BmsClient(config['bms'], handlers, bms_queue)
    except serial.SerialException as e:
        logger.error("SerialException({0}) opening BmsClient: {1}"
                     .format(e.errno, e.strerror))
        exit("Could not open BmsClient")
    except (OSError, IOError):
        exc_type, exc_value = sys.exc_info()[:2]
        logger.error("Error opening BMSClient: %s: %s"
                     % (str(exc_type), str(exc_value)))
        exit("Could not open BmsClient")
    except ValueError:
        logger.error("ValueError with BmsClient config")
        exit("Could not open BmsClient")
    else:
        # clients.append(bms)
        threads.append(bms)

    #######################################
    # Other Threads
    #######################################
    # Woodward thread
    woodward = None
    try:
        woodward = WoodwardControl(
            config['woodward'], handlers
        )
    # ValueError can be from a missing value in the config map
    # or from an error in the parameters to PWM.start(...)
    except ValueError as e:
        logger.error("ValueError: %s"
                     % (e.args[0]))
        exit("WoodwardControl thread did not start")
    else:
        # clients.append(woodward)
        threads.append(woodward)

    # Open filewriter thread
    csv_header = build_csv_header(clients, logger)
    slow_log_queue = queue.Queue()
    fast_log_queue = queue.Queue()
    try:
        filewriter = FileWriter(
            config['filewriter'], handlers, slow_log_queue, fast_log_queue,
            bms_queue, csv_header)
    except ValueError as e:
        logger.error("FileWriter did not start with message \"{0}\""
                     .format(str(e)))
    except (IOError, OSError) as e:
        logger.error("FileWriter did not start with message \"{0}\""
                     .format(str(e)))
    else:
        threads.append(filewriter)

    ######################################
    # LED Gauges
    ######################################
    fuel_gauge = GroveLedBar(pins.FUEL_DATA, pins.FUEL_CLK)
    battery_gauge = GroveLedBar(pins.BAT_GG_DATA, pins.BAT_GG_CLK)

    # Start all the threads
    for thread in threads:
        thread.start()

    # If we get cancelled during this stage, stop threads cleanly.
    try:
        # Don't wait for DeepSea connection
        blink_leds(fuel_gauge, battery_gauge)
        update_gauges(fuel_gauge, battery_gauge)
    except SystemExit:
        stop_threads(threads)
        exit(0)

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
        3600.0: 0,
    }

    going = True
    shutdown = False
    ejecting = False
    potential_new_measurement_list = False
    heartbeat = False

    while going:
        # noinspection PyBroadException
        try:
            now = monotonic.monotonic()
            now_time = time.time()

            ###########################
            # Every tenth of a second
            ###########################
            if now >= next_run[0.1]:
                # Put the data for the "fast log file" into the queue
                csv_parts = ['{:.1f}'.format(now_time)]
                for addr in [DeepSeaClient.RPM,
                             DeepSeaClient.BATTERY_LEVEL,
                             DeepSeaClient.GENERATOR_CURRENT]:
                    try:
                        value = data_store[addr]
                    except KeyError:
                        value = ''  # We might not have these on first run

                    if value is not None:
                        csv_parts.append('{:.1f}'.format(value))
                    else:
                        csv_parts.append('')
                fast_log_queue.put(','.join(csv_parts))

                # Connect the analog current in to the woodward process
                if woodward and not woodward.cancelled:
                    try:
                        cur = data_store[pins.GEN_CUR]
                        if cur is not None:
                            woodward.process_variable = cur
                    except KeyError:
                        logger.critical('Generator current is not being measured.')
                        exit('Generator current is not being measured.')

                # Schedule next run
                next_run[0.1] = now + 0.1

            ###########################
            # Twice a second
            ###########################
            if now >= next_run[0.5]:
                # Connect the CMS PID enable virtual LED from the deepSea to the PID
                try:
                    # Virtual LED 1
                    # From DeepSea GenComm manual, 10.57
                    pid_enable = data_store[DeepSeaClient.VIRTUAL_LED_1]
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
                    if usbdrive.mounted():
                        filewriter.eject_drive = True
                        ejecting = True

                # Toggle the spare LED like a heartbeat
                heartbeat = not heartbeat
                gpio.write(pins.SPARE_LED, heartbeat)

                # Schedule next run
                next_run[0.5] = now + 0.5

            ###########################
            # Once a second
            ###########################
            if now >= next_run[1.0]:
                # If not in daemon, print to screen
                if not daemon:
                    print_data(clients)

                ###############################
                # Get CSV data to the log file
                ###############################
                # If any of the clients say we should get a new log
                # file, get a new log file.
                new_log_file = False
                for client in clients:
                    new_log_file = new_log_file or client.new_log_file

                csv_parts = ["{:.1f}".format(now_time)]

                # Get the CSV line from each client, and reset
                # new_log_file flag, as we've gotten the message.
                for client in clients:
                    csv_parts.append(client.csv_line())
                    client.new_log_file = False

                # Send a None over the queue (signal to filewriter
                # to start a new file)
                if new_log_file:
                    try:
                        slow_log_queue.put(None)
                    except queue.Full:
                        exit("File writer queue full. Exiting.")

                # Put the csv data in the logfile
                if len(csv_parts) > 0 and slow_log_queue:
                    try:
                        slow_log_queue.put(','.join(csv_parts))
                    except queue.Full:
                        exit("File writer queue full. Exiting.")

                # Read in the config file to update the tuning coefficients
                try:
                    with open(TUNING_FILE) as f:
                        s = f.read()
                    wc = ast.literal_eval(s)
                except IOError:
                    pass
                else:
                    woodward.set_tunings(wc['Kp'], wc['Ki'], wc['Kd'])
                    woodward.setpoint = wc['setpoint']

                if check_kill_switch():
                    logger.info("check_kill_switch() = True, opening contactor")
                    gpio.write(pins.CMS_FAULT, True)
                    going = False
                    shutdown = True

                # Schedule next run
                next_run[1.0] = now + 1.0

            ###########################
            # Once every 5 seconds
            ###########################
            if now >= next_run[5.0]:
                # Check for new USB drive
                plugged = usbdrive.plugged()
                if plugged:
                    mounted = usbdrive.mounted()
                    if mounted is None and not ejecting:
                        filewriter.mount_drive = plugged
                        potential_new_measurement_list = True

                    elif ejecting:
                        # if we're already ejecting, don't do anything
                        pass

                    # If the USB changes locations without realizing it
                    # (sometimes happens at engine startup), eject "mounted"
                    # drive (not actually working) and once we've un-
                    # mounted, we'll mount the new location.
                    elif mounted != plugged:
                        filewriter.eject_drive = True

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
                if watchdog:
                    update_watchdog()

                # Ensure analog and woodward control are running
                if analog.cancelled or woodward.cancelled:
                    logger.error("Missing analog or woodward")
                    going = False
                    exit_code = 1

                # Read in a "measurements.csv" file from the drive and apply
                # it to DeepSea.
                if potential_new_measurement_list:
                    drive = usbdrive.mount_point()
                    if drive:
                        potential_new_measurement_list = False
                        filename = path.join(drive, "measurements.csv")
                        if path.exists(filename):
                            logger.info("Reading new measurement list")
                            mlist = deepsea.read_measurement_description(filename)
                            if set(mlist) != set(deepsea.input_list):
                                deepsea.new_input_list = mlist
                                csv_header = build_csv_header(clients, logger)
                                filewriter.update_csv_header(csv_header)

                # Schedule next run
                next_run[10.0] = now + 10.0

            ###########################
            # Once every minute
            ###########################
            if now >= next_run[60.0]:
                update_gauges(fuel_gauge, battery_gauge)

                # Schedule next run
                next_run[60.0] = now + 60.0

            ###########################
            # Once every hour
            ###########################
            if now >= next_run[3600.0]:
                if time_from_deepsea:
                    set_linux_time()

                # Schedule next run
                next_run[3600.0] = now + 3600.0

            time.sleep(0.01)

        except KeyboardInterrupt:
            logger.info("Dying due to KeyboardInterrupt.")
            going = False
            # Standard exit code when interrupted by Ctrl-C
            # http://tldp.org/LDP/abs/html/exitcodes.html
            exit_code = 130
            close_watchdog()
            stop_threads(threads)

        except SystemExit:
            exception_info = str(sys.exc_info())
            logger.info("Dying due to SystemExit: " + exception_info)
            going = False
            exit_code = 0
            close_watchdog()
            stop_threads(threads)

        except Exception as e:  # Log any other exceptions
            utils.log_exception(logger, e)

    logger.info("Exited while loop.")
    if shutdown:
        logger.info("Calling power_off().")
        power_off()
    logger.info("Calling exit(exit_code).")
    close_watchdog()
    exit(exit_code)


def build_csv_header(clients, logger):
    headers = []
    for c in clients:
        headers.append(c.csv_header())
    if len(headers) == 0:
        logger.error("CSV header returned by clients is blank")
    headers.append("output_woodward")
    csv_header = "linuxtime," + ','.join(headers) + ',id={:x}'.format(MAC_ID0)
    return csv_header


def stop_threads(threads):
    """
    Stop each thread in the list, preparatory to shutdown

    :param threads: A list of AsyncIOThread objects to shutdown
    :return: :const:`None`
    """
    for thread in threads:
        thread.cancel()
        thread.join()


def print_data(clients):
    """
    Print the data for all the threads which get data.

    :param clients: A list of clients with a print_data function
    :return: :const:`None`
    """
    for client in clients:
        client.print_data()
    print('-' * 80)


def update_watchdog():
    """
    Write to the watchdog file, keeping the system from being
    restarted. If we don't write to the watchdog for 60 seconds, the
    system will be restarted.

    :return: :const:`None`
    """
    with open("/dev/watchdog", 'w') as f:
        f.write('\n')


def close_watchdog():
    """
    When we exit, we should shutdown the watchdog daemon politely so as
    not to surprise the user with a reboot.
    """
    logger.info('Closing watchdog...')
    f = open("/dev/watchdog", 'w')
    f.write('V')
    f.close()


def update_gauges(fuel_gauge, battery_gauge):
    """
    Update both the fuel and the battery gauge using data from the
    central data store.

    :param fuel_gauge: GroveLedBar object, the fuel gauge
    :param battery_gauge: GroveLedBar object, the battery gauge
    :return: :const:`None`
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


def check_kill_switch():
    """
    Check whether we are to poweroff now.

    :return: Boolean, whether to poweroff.
    """
    try:
        val = data_store[DeepSeaClient.VIRTUAL_LED_2]
    except KeyError:
        val = None

    if val:
        return True
    else:
        return False


def set_linux_time():
    """
    Set the Linux time from the DeepSea time.

    :return: :const:`None`
    """
    t = data_store[DeepSeaClient.TIME]
    if t is not None:
        s = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t))
        subprocess.call(['timedatectl', 'set-time', s])


def power_off():
    """
    Shut down the system immediately.

    :return: :const:`None`
    """
    subprocess.call(["poweroff"])


def blink_leds(fuel_gauge, batt_gauge):
    """
    Do a blinking LED show at startup

    :return: :const:`None`
    """
    for i in range(11):
        fuel_gauge.set_bar_level(i)
        batt_gauge.set_bar_level(i)
        gpio.write(pins.USB_LED, i % 2)
        gpio.write(pins.SPARE_LED, i % 2)
        gpio.write(pins.DISK_ACT_LED, (i + 1) % 2)
        gpio.write(pins.PID_LED, (i + 1) % 2)
        time.sleep(0.1)
    # Turn them all off
    gpio.write(pins.USB_LED, 0)
    gpio.write(pins.PID_LED, 0)
    gpio.write(pins.DISK_ACT_LED, 0)
    gpio.write(pins.SPARE_LED, 0)
