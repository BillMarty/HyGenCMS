# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential

from subprocess import call

from .pins import modes


def setup_io():
    """
    Setup the pinmuxing correctly, using the ``config-pin`` utility.
    """
    # Load overlays that we need
    call(["config-pin", "overlay", "univ-emmc"])
    call(["config-pin", "overlay", "BB-ADC"])

    for key, mode in modes.items():
        call(['config-pin', key, mode])


def universal_cape_present():
    """
    Return whether there is a cape loaded capable of functioning as a
    universal cape.

    :return: :const:`True` or :const:`False`
    """
    with open('/sys/devices/platform/bone_capemgr/slots', 'r') as f:
        capes = f.read()
        if 'univ' in capes:
            return True
        else:
            return False
