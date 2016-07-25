"""
A module to asynchronously read in values from the ADC inputs.
All values are read in at the same frequency.
"""

import monotonic
import time
import sys
import Adafruit_BBIO.ADC as ADC

from asynciothread import AsyncIOThread

NAME = 0
UNITS = 1
PIN = 2
GAIN = 3
OFFSET = 4


class AnalogClient(AsyncIOThread):

    def __init__(self, aconfig, handlers, data_store):
        """
        Set up a thread to read in analog values
        aconfig: the configuration values to read in
            {'measurements': [['current', 'A', "P9_39", 1.0, 0.0], ...],
             'frequency': 0.1, # seconds
             'averages': 8, # Number of values to average
            }
        """
        super(AnalogClient, self).__init__(handlers)

        # Read configuration values
        AnalogClient.check_config(aconfig)
        self._input_list = aconfig['measurements']
        self.frequency = aconfig['frequency']
        self.averages = aconfig['averages']
        if self.averages == 0:
            raise ValueError("Cannot average 0 values")
        self.mfrequency = self.frequency / self.averages

        # Initialize our array of values
        self.data_store = data_store
        self.data_store.update({m[PIN]: None for m in self._input_list})
        self.partial_values = {m[PIN]: (0.0, 0) for m in self._input_list}
        self.last_updated = monotonic.monotonic()

        # Open the ADC
        ADC.setup()

        # Log to debug that we've started
        self._logger.debug("Started analogclient")

    @staticmethod
    def check_config(aconfig):
        """
        Check that the config is complete. Throw an exception if any
        configuration values are missing.
        """
        required_config = ['measurements', 'frequency', 'averages']
        for val in required_config:
            if val not in aconfig:
                raise ValueError("Missing " + val + ", required for modbus")
        # Make sure the measurements are in the right format
        for m in aconfig['measurements']:
            try:
                assert len(m) == 5
                assert isinstance(m[NAME], str)
                assert isinstance(m[UNITS], str)
                assert isinstance(m[PIN], str)
                assert isinstance(m[GAIN], float)
                assert isinstance(m[OFFSET], float)
            except AssertionError:
                raise ValueError("Measurement list formatted incorrectly")
        # If we get to this point, the required values are present
        return True

    def run(self):
        """
        Overloads Thread.run, runs and reads analog inputs
        """
        while not self.cancelled:
            t = monotonic.monotonic()
            # If we've passed the ideal time, get the value
            if t >= self.last_updated + self.mfrequency:
                for m in self._input_list:
                    key = m[PIN]
                    sum_, n = self.partial_values[key]

                    if n >= self.averages:
                        average = sum_ / (n * 1000.)
                        self.data_store[key] = average * m[GAIN] + m[OFFSET]
                        sum_, n = 0., 0.

                    try:
                        sum_, n = sum_ + ADC.read_raw(m[PIN]), n + 1
                    except RuntimeError:  # Shouldn't ever happen
                        exc_type, exc_value = sys.exc_info()[:2]
                        self._logger.error("ADC reading error: %s %s"
                                           % (exc_type, exc_value))
                    except ValueError:  # Invalid AIN or pin name
                        exc_type, exc_value = sys.exc_info()[:2]
                        self._logger.error("Invalid AIN or pin name: %s %s"
                                           % (exc_type, exc_value))
                    except IOError:  # File reading error
                        exc_type, exc_value = sys.exc_info()[:2]
                        self._logger.error("%s %s", exc_type, exc_value)

                    self.partial_values[key] = sum_, n
                self.last_updated = t

            time.sleep(0.01)

    ###################################
    # Methods called from Main Thread
    ###################################

    def print_data(self):
        """
        Print all the data as we currently have it, in human-
        readable format.
        """
        for m in self._input_list:
            key = m[PIN]
            val = self.data_store[key]
            if val is None:
                display = "%20s %10s %10s" % (m[NAME], "ERR", m[UNITS])
            else:
                display = "%20s %10.2f %10s" % (m[NAME], val, m[UNITS])
            print(display)

    def csv_header(self):
        """
        Return the CSV header line with no new line or trailing comma
        """
        names = []
        for m in self._input_list:
            names.append(m[NAME])
        return ','.join(str(x) for x in names)

    def csv_line(self):
        """
        Return a CSV line of the data we currently have.

        The line is returned with no new line or trailing comma.
        """
        values = []
        for m in self._input_list:
            val = self.data_store[m[PIN]]
            if val is not None:
                values.append(str(val))
            else:
                values.append('')
        return ','.join(values)
