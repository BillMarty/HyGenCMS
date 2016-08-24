# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

"""
This module provides a subclass of thread, AsyncIOThread, which adds
logging and the ability to cancel the thread. Ordinary threads continue
until "completion", but this class enables the run to have a loop which
continues until the thread is cancelled.
"""
import logging
from threading import Thread


class AsyncIOThread(Thread):
    """
    Super-class for all the threads which run parallel to the main
    thread and do input or output, and logging.
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

        # Flag for whether we need to start a new log file (if
        # configuration changed)
        self.new_log_file = False

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
        """
        Cancel the thread, and log its stopping to the logger.

        :return: :const:`None`
        """
        self.cancelled = True
        self._logger.info("Stopping " + str(self) + "...")
