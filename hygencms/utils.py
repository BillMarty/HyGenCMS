# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

import os
import sys
from contextlib import contextmanager

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3


def get_input(s, default=""):
    """
    Get raw input using the correct function for the Python version.

    :param s: The prompt string to show. A space will be added to the end so
        no trailing space is required

    :param default: A default value which will be returned if the user does not
        enter a value. Displayed in square brackets following the
        prompt
    :return: The returned string value.
    """
    if default == "":
        d = " "
    else:
        d = " [" + str(default) + "] "

    if sys.version_info < (3, 0):
        x = raw_input(s + d)
    else:
        x = input(s + d)

    if x == "":
        return str(default)
    else:
        return x


def is_int(s, *args):
    """Return whether a value can be interpreted as an int."""
    try:
        int(s, *args)
        return True
    except ValueError:
        return False


@contextmanager
def ignore(*exceptions):
    """
    Ignore whichever exceptions are given as arguments.
    Taken from http://stackoverflow.com/a/15573313 (MIT license)
    """
    try:
        yield
    except exceptions:
        pass


def log_exception(logger, e):
    """
    Log an exception, complete with the stack trace.

    :param logger: The logger to write to
    :param e: The exception which was thrown
    :return:
    """
    tb = sys.exc_info()[-1]
    if tb is not None:
        logger.error("%s raised: %s (%s:%d)"
                     % (e.__class__.__name__,
                        str(e),
                        os.path.basename(
                            tb.tb_frame.f_code.co_filename),
                        tb.tb_lineno))
        del tb
    else:
        logger.error("%s raised: %s"
                     % (e.__class__.__name__,
                        str(e)))
