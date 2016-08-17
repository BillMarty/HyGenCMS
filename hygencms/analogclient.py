import sys
import time

from monotonic import monotonic

from . import adc, utils
from .asyncio import AsyncIOThread


class AnalogClient(AsyncIOThread):
    """
    This class reads from the BeagleBone ADC in a separate thread.
    This thread reads all values specified in the configuration file
    at a specified frequency.
    """

    NAME = 0
    UNITS = 1
    PIN = 2
    GAIN = 3
    OFFSET = 4

    def __init__(self, aconfig, handlers, data_store):
        """
        :param aconfig:
            Configuration map for the AnalogClient

        :param handlers:
            List of log handlers.

        :param data_store:
            Reference to data store map to keep values
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
        self.data_store.update({m[AnalogClient.PIN]: None for m in self._input_list})
        self.partial_values = {m[AnalogClient.PIN]: (0.0, 0) for m in self._input_list}
        self.last_updated = monotonic()

        # Open the ADC
        adc.setup()

        # Log to info that we've started
        self._logger.info("Started analogclient")

    @staticmethod
    def check_config(aconfig):
        """
        Raise an exception if the configuration is not valid.

        :param aconfig:
            Configuration map to check

        :return:
            :const:`True`

        :exception ValueError:
            raised if the configuration map is invalid
        """
        required_config = ['measurements', 'frequency', 'averages']
        for val in required_config:
            if val not in aconfig:
                raise ValueError("Missing " + val + ", required for modbus")
        # Make sure the measurements are in the right format
        for m in aconfig['measurements']:
            try:
                assert len(m) == 5
                assert isinstance(m[AnalogClient.NAME], str)
                assert isinstance(m[AnalogClient.UNITS], str)
                assert isinstance(m[AnalogClient.PIN], str)
                assert isinstance(m[AnalogClient.GAIN], float)
                assert isinstance(m[AnalogClient.OFFSET], float)
            except AssertionError:
                raise ValueError("Measurement list formatted incorrectly")
        # If we get to this point, the required values are present
        return True

    def run(self):
        """
        Overloads Thread.run, runs and reads analog inputs.
        """
        while not self.cancelled:
            # noinspection PyBroadException
            try:
                t = monotonic()
                # If we've passed the ideal time, get the value
                if t >= self.last_updated + self.mfrequency:
                    for m in self._input_list:
                        key = m[AnalogClient.PIN]
                        sum_, n = self.partial_values[key]

                        if n >= self.averages:
                            average = sum_ / n
                            self.data_store[key] = \
                                average * m[AnalogClient.GAIN] \
                                + m[AnalogClient.OFFSET]
                            sum_, n = 0., 0.

                        try:
                            sum_, n = sum_ + adc.read_volts(m[AnalogClient.PIN]), n + 1
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
            except Exception as e:
                utils.log_exception(self._logger, e)

    ###################################
    # Methods called from Main Thread
    ###################################

    def print_data(self):
        """
        Print all the data as we currently have it, in human-
        readable format.
        """
        for m in self._input_list:
            key = m[AnalogClient.PIN]
            val = self.data_store[key]
            if val is None:
                display = "%20s %10s %10s" % (m[AnalogClient.NAME],
                                              "ERR", m[AnalogClient.UNITS])
            else:
                display = "%20s %10.2f %10s" % (m[AnalogClient.NAME],
                                                val, m[AnalogClient.UNITS])
            print(display)

    def csv_header(self):
        """
        Return the CSV header line with no new line or trailing comma
        """
        names = []
        for m in self._input_list:
            names.append(m[AnalogClient.NAME])
        return ','.join(str(x) for x in names)

    def csv_line(self):
        """
        Return a CSV line of the data we currently have.

        The line is returned with no new line or trailing comma.
        """
        values = []

        for m in self._input_list:
            val = self.data_store[m[AnalogClient.PIN]]
            if val is not None:
                values.append(str(val))
            else:
                values.append('')

        return ','.join(values)
