import subprocess
from subprocess import check_call, CalledProcessError, STDOUT, check_output
import time
import os.path as path
import os


def mount_plugged():
    """
    Mount whichever USB drive is plugged in.

    :return:
        True if a drive is mounted, else False
    """
    p = plugged()
    if p:
        return mount(p)
    else:
        return False


def unmount_mounted():
    """
    Unmount whichever USB drive is mounted.

    :return:
        True if a drive unmounted, else False
    """
    m = mounted()
    if m:
        return unmount(m)
    else:
        return False


def mount_point():
    """
    Return the path to whatever usb drive is mounted, or None

    :return:
        '/media/[drive]' or None
    """
    try:
        mount_list = subprocess.check_output(['mount']).decode('utf-8')
    except CalledProcessError:
        return None

    position = mount_list.find('/dev/sd')
    if position == -1:
        return None

    line = mount_list[position:].splitlines()[0]
    position = line.find("/media/sd")
    if position == -1:
        return None

    drive_path = line[position:].split()[0]

    return drive_path


def mounted():
    """
    Return the device file of a mounted USB

    :return:
        The device file '/dev/sd??'
    """
    try:
        mount_list = subprocess.check_output(['mount']).decode('utf-8')
    except CalledProcessError:
        return None

    position = mount_list.find('/dev/sd')
    if position == -1:
        return None

    return mount_list[position:].split()[0]


def plugged():
    """
    Return any USB drive plugged in

    :return:
        The device file '/dev/sd??' or None
    """
    lines = check_output(['lsblk']).decode('utf-8').splitlines()

    device_file = None
    for line in lines:
        sd_position = line.find('sd')
        if sd_position == -1:
            continue

        part_position = line[sd_position:].find('part')
        if part_position == -1:
            continue

        device_file = line[sd_position:].split()[0]
        break  # assuming there's only ever one

    if device_file:
        drive = '/dev/' + device_file
        if os.path.exists(drive):
            return drive

    return None


def unmount(device):
    """
    Unmount the given device using the ``pumount`` command

    :param device:
        The device file of a mounted partition to unmount.

    :return:
        True if success, else False
    """
    device = path.basename(device)
    m = mounted()
    if m and path.basename(m) != device:
        return True  # That device isn't mounted

    # Try to unmount
    tries = 0
    while drive_mounted and tries < 100:
        try:
            check_call(["pumount", device], stderr=STDOUT)
        except CalledProcessError:
            tries += 1
        else:
            drive_mounted = False
        time.sleep(0.01)

    return not drive_mounted


def mount(device):
    """
    Mount the given device using the ``pmount`` command.
    If another USB device is mounted, unmount it and mount
    this one instead.

    :param device:
        The device file of a partition.
        Either '/dev/sda1' form or 'sda1' form is acceptable.

    :return:
        True if success, else False
    """
    device = path.basename(device)
    m = mounted()
    if m:
        if path.basename(m) == device:
            return True  # Already mounted
        else:
            unmount(m)

    if not path.basename(plugged()) == path.basename(device):
        return False  # Device not present

    # Try to mount
    tries = 0
    drive_mounted = False
    while not drive_mounted and tries < 100:
        try:
            check_call(['pmount', device], stderr=STDOUT)
        except CalledProcessError:
            tries += 1
        else:
            drive_mounted = True
        time.sleep(0.01)

    return drive_mounted
