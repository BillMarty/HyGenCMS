"""
"""
import logging
from threading import Thread


class AsyncIOThread(Thread):
    """
    Super-class for all the threads which read from a source.
    """

    def __init__(self, handlers):
        """
        Constructor
        :param config: A configuration map
        :param handlers: A list of log handlers
        :param data_store: A reference to the central dictionary where
                           values are stored
        """
        super(AsyncIOThread, self).__init__()
        self.daemon = False
        self.cancelled = False

        self._logger = None
        self.start_logger(handlers)

    def start_logger(self, handlers):
        """
        Start a logger with the name of the instance type
        :param handlers: Log handlers to add
        :return: None
        """
        self._logger = logging.getLogger(type(self).__name__)
        for h in handlers:
            self._logger.addHandler(h)
        self._logger.setLevel(logging.DEBUG)

    #####################################
    # Methods for call from parent thread
    #####################################

    def cancel(self):
        self.cancelled = True
        self._logger.debug("Stopping " + str(self) + "...")
