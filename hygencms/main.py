"""
This will be the main entry point for the python program for the hygen.

The program implements the following functionality:
    - Read data asynchronously from the DeepSea, BMS, and analog
        input pins
    - Write the read data to a USB memory stick location.
    - When a flag from the DeepSea is enabled, control the Woodward
        based on the Analog trunk current value
"""

###############################
# Import required libraries
###############################
import logging
import socket
import sys
import time

import monotonic
import serial

from . import analogclient
from . import bmsclient
from . import deepseaclient
from . import logfilewriter
from . import pins
from . import woodwardcontrol
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
data_store = {}


def main(config, handlers, daemon=True):
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

    ############################################
    # Async Data Sources
    ############################################
    if 'deepsea' in config['enabled']:
        try:
            deepsea = deepseaclient.DeepSeaClient(config['deepsea'], handlers, data_store)
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

    if 'analog' in config['enabled']:
        try:
            analog = analogclient.AnalogClient(config['analog'], handlers, data_store)
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

    if 'bms' in config['enabled']:
        try:
            bms = bmsclient.BmsClient(config['bms'], handlers)
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
    if 'woodward' in config['enabled']:
        try:
            woodward = woodwardcontrol.WoodwardControl(
                config['woodward'], handlers
            )
        # ValueError can be from a missing value in the config map
        # or from an error in the parameters to PWM.start(...)
        except ValueError as e:
            logger.error("ValueError: %s"
                         % (e.args[0]))
        else:
            clients.append(woodward)
            threads.append(woodward)

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
            filewriter = logfilewriter.FileWriter(
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
        exit(-1)

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
                        pass
                        # TODO What should we do here?

                # Connect the analog current in to the woodward process
                if woodward and not woodward.cancelled:
                    try:
                        cur = data_store[pins.GEN_CUR]
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
                    pid_enable = data_store[3345]  # From DeepSea GenComm manual
                    if pid_enable and int(pid_enable) & (1 << 6):
                        woodward.set_auto(True)
                    else:
                        woodward.set_auto(False)
                        woodward.output = 0.0
                except UnboundLocalError:
                    pass
                except KeyError:
                    logger.critical("Key does not exist for the PID enable flag")

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

                # Schedule next run
                next_run[1.0] = now + 1.0

            ###########################
            # Once every 5 seconds
            ###########################
            if now >= next_run[5.0]:
                update_watchdog()
                # Schedule next run
                next_run[5.0] = now + 5.0

            ###########################
            # Once every 10 seconds
            ###########################
            if now >= next_run[10.0]:
                # Check threads to ensure they're running
                revive(threads, logger)
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

        except SystemExit:
            going = False
            stop_threads(threads, logger)

        except Exception:
            exc_type, exc_value = sys.exc_info()[:2]
            logger.error("%s raised in main loop: %s"
                         % (str(exc_type), str(exc_value)))
            revive(threads, logger)

    exit(0)


def stop_threads(threads, logger):
    for thread in threads:
        thread.cancel()
        thread.join()
        logger.debug("Joined " + str(thread))


def print_data(clients):
    for client in clients:
        client.print_data()
    print('-' * 80)


def revive(threads, logger):
    """
    Check to make sure each thread is running, and restart any which
    have stopped.
    :param threads: An iterable of threads
    :param logger: The logger to which any messages will be written
    :return: None
    """
    for thread in threads:
        if not thread.is_alive():
            logger.error("%s not running. Exiting"
                         % str(thread))
            raise RuntimeError("%s died." % str(thread))


def update_watchdog():
    """
    Write to the watchdog file, keeping the system from being restarted.
    If we don't write to the watchdog for 60 seconds, the system will be
    restarted.
    :return: None
    """
    with open("/dev/watchdog", 'w') as f:
        f.write('\n')


def update_gauges(fuel_gauge, battery_gauge):
    """
    Update both the fuel and the battery gauge using data from the central
    data store.
    :param fuel_gauge: GroveLedBar object of the fuel gauge
    :param battery_gauge: GroveLedBar object of the battery gauge
    :return: None
    """
    # Update interface gauges
    # See DeepSea_Modbus_manualGenComm.docx, 10.6
    fuel = data_store[1027]  # Modbus fuel address
    fuel /= 10  # Scale to 10
    fuel_gauge.set_bar_level(fuel)

    # See DeepSea_Modbus_manualGenComm.docx, 10.6 (#199)
    battery_charge = data_store[1223]  # Modbus DC voltage address
    # TODO maybe replace this with our analog value
    # Scale the range from 259 to 309 to 0-10
    battery_charge = int(round((battery_charge - 259) * 0.2))
    battery_gauge.set_bar_level(battery_charge)


if __name__ == "__main__":
    sh = logging.StreamHandler()
    sh.setFormatter(
        logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    configuration = get_configuration()
    main(configuration, [sh], daemon=False)
