import serial

from . import utils
from .asynciothread import AsyncIOThread
from .utils import PY3


class BmsClient(AsyncIOThread):
    """
    This class specifies the specifics for the Becket battery
    management system to communicate asynchronously. The get_data and
    print_data methods will read the battery percentage at that moment
    and return or print it.
    """

    def __init__(self, bconfig, handlers):
        """
        Initialize the bms client from the configuration values.

        Could throw the following exceptions:
        - IOError
        - serial.SerialException
        - ValueError
        """
        # Initialize the parent class
        super(BmsClient, self).__init__(handlers)
        self.daemon = False

        # Read config values
        BmsClient.check_config(bconfig)
        dev = bconfig['dev']
        baud = bconfig['baudrate']
        sfilename = bconfig['sfilename']

        # Open serial port
        try:
            self._ser = serial.Serial(
                dev, baud, timeout=1.0)  # 1 second timeout
            if not self._ser.isOpen():
                self._ser.open()
        except serial.SerialException as e:
            self._logger.critical("SerialException({0}): {1}"
                                  .format(e.errno, e.strerror))
            raise

        # Open file - IOError could be thrown
        self._f = open(sfilename, 'a')

        # Setup global last line variables
        self.last_string_status = ""
        self.last_module_status = ""

        # Setup flags for fresh values
        self._last_string_fresh = False
        self._last_module_fresh = False

        self._cancelled = False
        self._logger.info("Started BmsClient")

    def __del__(self):
        self._ser.close()
        del self._ser
        self._f.close()

    @staticmethod
    def check_config(bconfig):
        """
        Check that the config is complete. Throw an exception if any
        configuration values are missing.
        """
        required_config = ['dev', 'baudrate', 'sfilename']
        for val in required_config:
            if val not in bconfig:
                raise ValueError("Missing " + val + ", required for BMS")
        # If we get to this point, the required values are present
        return True

    def run(self):
        """
        Overloads Thread.run, continuously reads from the serial port.
        Updates self.lastline.
        """
        while not self._cancelled:
            # noinspection PyBroadException
            try:
                line = self._ser.readline()
            except serial.SerialException:
                self._logger.warning("BMS not connected")
            except Exception as e:
                utils.log_exception(self._logger, e)
            else:
                # If the checksum is wrong, skip it
                try:
                    data = line[:122]
                    checksum = int(line[122:126], 16)
                except ValueError:
                    # If we don't have a long enough line the
                    # conversion fails with a blank string
                    continue
                except IndexError:
                    # I'm not sure we ever hit this, but it also
                    # would indicate a short line
                    continue

                # If the checksum fails we have a bad line
                if not self.fletcher16(data) == checksum:
                    continue

                try:
                    self._f.write(str(line))
                except IOError:
                    pass  # Ignore IOErrors

                if len(line) <= 4:
                    pass
                elif line[4] == 'S':
                    self.last_string_status = line
                    self._last_string_fresh = True
                elif line[4] == 'M':
                    self.last_module_status = line
                    self._last_module_fresh = True

    @staticmethod
    def fletcher16(data):
        """
        Returns the fletcher-16 checksum for data, of type bytes.
        Puts the bytes in the reverse order from the ordinary order.
        See https://en.wikipedia.org/wiki/Fletcher%27s_checksum
        """
        if not isinstance(data, bytes):
            return None
        if PY3:
            sum1, sum2 = 0, 0
            for byte in data:
                sum1 = (sum1 + byte) % 255
                sum2 = (sum2 + sum1) % 255
        else:
            sum1, sum2 = 0, 0
            for byte in data:
                # noinspection PyTypeChecker
                sum1 = (sum1 + ord(byte)) % 255
                sum2 = (sum2 + sum1) % 255
        return (sum1 << 8) | sum2

    #########################################
    # Methods called from Main thread
    #########################################

    def get_data(self):
        """
        Get the data
        """
        # If we have a last string
        if self.last_string_status and self._last_string_fresh:
            charge = int(self.last_string_status[19:22])
            cur = int(self.last_string_status[34:39])
            self._last_string_fresh = False
            return charge, cur
        else:
            return None, None

    def print_data(self):
        """
        Print all the data as we currently have it, in human-readable
        format
        """
        # Short circuit if we haven't started reading data yet
        if self.last_string_status == "":
            return

        charge, cur = self.get_data()
        if charge is not None:
            print("%20s %10d %10s" % ("State of Charge", charge, "%"))
        else:
            print("%20s %10s %10s" % ("State of Charge", "ERR", "%"))

        if cur is not None:
            print("%20s %10d %10s" % ("Battery Current", cur, "A"))
        else:
            print("%20s %10s %10s" % ("Battery Current", "ERR", "A"))

    @staticmethod
    def csv_header():
        """
        Return a string of the CSV header for our data.

        No newline or trailing comma.
        """
        return "SoC (%),Current (A)"

    def csv_line(self):
        """
        Return the CSV data in the form:
        "%f,%f"%(charge, cur)
        """
        # Short circuit if we haven't started reading data yet
        if self.last_string_status == "":
            return ","
        charge, cur = self.get_data()
        if charge is not None and cur is not None:
            return "%d,%d" % (charge, cur)
        else:
            return ","
