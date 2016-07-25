import sys
from contextlib import contextmanager

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3


def get_input(s, default=""):
    """
    Get raw input using the correct version for the Python version.

    s:
        The prompt string to show. A space will be added to the end so
        no trailing space is required

    default:
        A default value which will be returned if the user does not
        enter a value. Displayed in square brackets following the
        prompt
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
    "Return whether a value can be interpreted as an int."
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
