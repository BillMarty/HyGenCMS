# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

"""
Provide subclasses of thread, which can be used to do asynchronous IO.
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
        :param handlers:
            List of log handlers to use
        """
        super(AsyncIOThread, self).__init__()
        self.daemon = False
        self.cancelled = False

        self._logger = None
        self.start_logger(handlers)

    def start_logger(self, handlers):
        """
        Start a logger with the name of the instance type

        :param handlers:
            Log handlers to add
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
        self._logger.info("Stopping " + str(self) + "...")


