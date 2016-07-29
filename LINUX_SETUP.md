# Linux setup

A Beaglebone image will be used to flash every BeagleBone. This image is
pre-configured. However, this README will document the steps required to
recreate the image, for the sake of future maintainers. The current
at the time of this document is Debian 8.5, with the kernel 
`4.4.15-bone11`.

## Preparing MicroSD card

The image should be obtained from [this site](https://debian.beagleboard.org/images/rcn-ee.net/rootfs/bb.org/testing/), which is the repository holding the latest builds of Debian 8, Jessie. Choose the image under `[date]/console/bone-debian-[...].img.xz`. The image is downloaded as a `.img.xz` file, and can be uncompressed with [7-Zip](http://www.7-zip.org/) or another  decompression program to obtain a `.img` file. This file should be burned to a MicroSD card using [Win32DiskImager](https://sourceforge.net/projects/win32diskimager/) or [Etcher](http://www.etcher.io/). This MicroSD should then be inserted into a BeagleBone Black Industrial to complete the setup process (either an  Element14 or an Arrow board will work).

My experience has been that with the MicroSD inserted, the BeagleBone will automatically boot from the MicroSD. If it does not, powering on while holding the *boot* button (the button on the opposite end from the ethernet port) will force boot from MicroSD. The easiest way to connect to the device is via the header pins and a USB-serial adapter. To do this, download [Putty](http://www.putty.org/). The connection will involve the following settings:

- Connection type: Serial
- Speed: 115200
- Serial line: Look in Device Manager to discover what COM device to use.

Open the Putty session, plug in the BeagleBone, login as root (no password)  and begin the configuration process.

## Add User
_maybe we don't actually need to create a different user_ 
The first task is creating a user. Use the `adduser` command to do so, and add the user to the sudo (administrators) group.

```bash
adduser hygen
# Enter password for the hygen account. Currently Power16
adduser hygen sudo
```

`sudo`, short for substitute user, allows a user to run commands as a different user. The default user to run commands is `root`, the master  administrator account on Linux. We want to ensure that the sudo group can use the sudo command. We're going to disable login as root for security, so it's crucial that we can still use other accounts to perform administrative tasks.

```bash
visudo
# This opens up an editor (probably nano) with the /etc/sudoers file.
```

We want to make sure that this file has the following line:

```
# Allow members of group sudo to execute any command
%sudo   ALL=(ALL:ALL)
```

If the line is commented out, uncomment it. Then we want to test that the `hygen` user can in fact use sudo to execute commands as root. Log out with  `exit` and log back in as hygen. Then execute following command:

```bash
sudo whoami
```

It should prompt for hygen's password, then print `root`. This confirms that sudo has been enabled. Next we will setup the network (remember to stay logged in as hygen).

## Network Setup

Plug the BeagleBone into the office ethernet. It may automatically acquire an IP address and connect to the internet. Check this by testing `ping`.

```bash
ping 8.8.8.8
```

If this returns an error with `ping: icmp open socket: Operation not permitted`, the `ping` application does not have the SUID bit set. The SUID bit is a permission which lets anyone run a given application as the owner of that file. In the case of ping (use `which ping` to find where it lives), that is `root`, which is a good thing, since it needs `root` permission to open a network socket. We'll set the SUID bit on that file using the following command.

```bash
sudo chmod +s $(which ping)
```

Now test our change by trying `ping 8.8.8.8` again. Don't worry if it gives an error, we'll configure the network in a second. Just ensure that it doesn't give the same `ping: icmp open socket: Operation not permitted` error.

Now we want to configure the network. This is done using the interfaces file. In Debian, this lives at `/etc/network/interfaces`. You can use whichever editor you prefer to edit this file. There are basically only two choices on the system at this point: `vi` and `nano`. `vi` is a modal editor, with a fairly steep learning curve, but ultimately more efficient. `nano` is a very simple editor, probably simpler if you've never used `vi`. This file is a system configuration file, owned by `root`, so you must use sudo to open it.

```bash
sudo nano /etc/network/interfaces
```

Now we want to configure the `eth0` interface. Find the section starting with `iface eth0`. If this hygen is being used in the office, assign it a free IP address (the list is at X:\Static_IPs.xlsx as of 2016-07-26). If it is going out to a site, we'll eventually want to turn the IP back to DHCP, but for now we'll assign it a static IP for continuing setup.

```
auto eth0
iface eth0 inet static
address 10.50.0.x
gateway 10.50.0.1
netmask 255.255.255.0
```

Replace *x* with the chosen IP address. This will configure the BeagleBone for use on Planetary Power's ethernet. Reboot the system to apply the changes.

```bash
sudo reboot
```

Test the network connection again.

```bash
ping 8.8.8.8
```

This should now show ping responses. If not, the network is not properly configured, and that must be solved before continuing.

## Setup SSH

We now want to switch to SSH for logging in, as it's both faster and more convenient than the header pins. Also, once the interface PCB board is attached, the pins will be inaccessible. The simplest way to use SSH from Windows is the [Chrome App](https://chrome.google.com/webstore/detail/secure-shell/pnhechapfaindjhompbnflcldabbghjo). Enter the static IP address we chose as the IP address and `hygen` as the username. Accept the warning about the unknown signature.

Since we've connected the BeagleBone to the network, we need to disable root login from SSH, as it currently is permitted with no password. SSH configuration is found in `/etc/ssh/sshd_config`. Use your editor of choice to edit the file (using `sudo`). In the `Authentication` section, make sure there is the following line:

```
PermitRootLogin no
```

Also change this:
```
PermitEmptyPasswords no
```

If you want, you can also setup a banner to show when logging in via SSH. This can be done with the following two steps:

```
# /etc/ssh/sshd_config
Banner /etc/banner
```

```bash
sudo nano /etc/banner
```

Suggested banner:
```
 _    _                        _                                 
| |  | |                      | |                                
| |__| |_   _  __ _  ___ _ __ | |     ___   __ _  __ _  ___ _ __ 
|  __  | | | |/ _` |/ _ \ '_ \| |    / _ \ / _` |/ _` |/ _ \ '__|
| |  | | |_| | (_| |  __/ | | | |___| (_) | (_| | (_| |  __/ |   
|_|  |_|\__, |\__, |\___|_| |_|______\___/ \__, |\__, |\___|_|   
         __/ | __/ |                        __/ | __/ |          
        |___/ |___/                        |___/ |___/           
```

## Update System Packages

If you've chosen a recent image, there shouldn't be much to do in a system update, but we'll do one anyway, since we're going to be installing packages, and installing onto an out-of-date system is not recommended. We'll update the package indexes first, then upgrade out-of-date packages, and finally clean downloaded packages and autoclean any packages we haven't asked for.

```bash
sudo apt-get update
sudo apt-get upgrade
sudo apt-get clean
sudo apt-get autoclean
```


## Grow Root Partition

We chose to install the console image, because it has very minimal software installed. However, the image is also only a 2 GB image, so we're not using our entire MicroSD, so we won't be using the entire EMMC when we flash it. We'll use `fdisk` to fix this. `fdisk` is an interactive program, so comments in the Bash below will narrate what actions to take inside it.

```bash
# Start by listing all the drives and partitions
lsblk
# mmcblk0 should have only one partition on it (mmcblk0p1). This is
# the uSD card.
sudo fdisk /dev/mmcblk0
# Delete the existing partition with 'd'
# New primary partition with 'n', then 'p', '1', 'ENTER', 'ENTER'
# Write out the new partition table with 'w'

# Reboot to apply the new partition table.
sudo reboot
```

After we've expanded the partition, we need to resize the filesystem to fill the whole partition. We'll do that using the `resize2fs` command.

```bash
sudo resize2fs /dev/mmcblk0p1
```

Notice that while in the previous section we were acting on the disk itself (at `/dev/mmcblk0`), with this command we're acting on the partition (`/dev/mmcblk0p1`).

Now check to make sure we've succeeded in using the full disk using `df`, which reports on disk filesystem space usage.

```bash
df -h
```

`df` ought to report that `/dev/mmcblk0p1` is 3.7G now, with about 25% usage.

## Install Necessary Libraries

We'll be using Python 3, so we need to install that package. We'll actually just install `pip`, Python's package manager, and it will pull in Python as a dependency.

```bash
sudo apt-get install python3-pip
```

Now that we've got `pip`, we'll use that to grab modbus_tk. This will pull in `pyserial` as a dependency. We're not going to pull in `Adafruit_BBIO` from `pip`, since the version on there is not compatible with kernels newer than 3.8.

```bash
sudo pip3 install modbus_tk
sudo pip3 install recordclass
```

We'll install the Adafruit_BBIO library from a commit which is known to work, directly from their Github repository. In order to do that, we'll need the `unzip` package to deal with the zip archive from Github.

```bash
sudo apt-get install unzip
cd ~
wget https://github.com/adafruit/adafruit-beaglebone-io-python/archive/eb0b34746320690953134ebaa024a8171232655a.zip
unzip adafruit*
rm *.zip
cd adafruit*
sudo make install
cd ..
rm -R adafruit*
```

We also use the `config-pin` utility from the [Beaglebone Universal IO](https://github.com/cdsteinkuehler/beaglebone-universal-io) library. This utility is included in most base images for the BeagleBone, but the console image we used left it out to save space. We'll install it (just the utility) from the Github repositories. The device tree overlays in that repository are already installed in kernel 4.1+ and some 3.8 images.

```bash
cd ~
wget https://github.com/cdsteinkuehler/beaglebone-universal-io/archive/master.zip
unzip master.zip
rm master.zip
cd beaglebone-universal-io
sudo make install_target  # This installs the utility but not the DTOs
```

## Setup USB Automounting

Linux uses a system called `udev` to manage and respond to kernel events, such as the insertion or removal of hardware. This system allows the addition of rules files for implementing our own functionality. In our case, we'd like to automatically mount any USB device that is inserted, in order to write log files. We'll create a new `automount.rules` file in `/etc/udev/rules.d/`. Remember to open the file using `sudo` and whatever editor your want.

```
# /etc/udev/rules.d/automount.rules
# Last changed:
# 2016-07-15
# Reference:
# http://unix.stackexchange.com/a/134903
# Purpose:
# Automount USB flash drives when plugged in.
# On the BeagleBone, flash drives plugged into the USB show up on /dev/sda.
# For most flash drives, the partition will appear on /dev/sda1. For some,
# however, the main partition appears on /dev/sda.
# pmount mounts the USB drive partitions on /media/sda*.
ACTION=="add", KERNEL=="sd?*", RUN+="/usr/bin/pmount --umask=000 %k"
```

This will automount any inserted USB drive so that it is readable for any user. There are two things left to do: first, `pmount` is not installed, so we need to add that. Second, we need to reload the udev rules in order for our new rule to take effect.

```bash
sudo apt-get install pmount
sudo udevadm control --reload-rules
```

Now USB drives will mount automatically.

## Hygen Software

It's finally time to add our software to the mix. *Note to self: the way we add our software may change if we install our software to some native linux directory rather than in hygen's home directory.* We'll do this by cloning from our private GitHub repository.

```bash
cd ~
sudo apt-get install git
git clone https://github.com/BillMarty/HyGenCMS.git
```

We need to change the file mode to make the primary program file executable.

```bash
cd ~/HyGenCMS
chmod +x cms
```

## Auto-starting Service

To make the service start on boot, we create a service description file. Debian 8 just switched to a new init system called systemd. The init system is the mechanism which starts the Linux system. It is the first process to run on boot, and is responsible for starting all the other processes. Since it starts all other processes, it also is responsible for managing the other processes, and can ensure they continue to run. We will use this functionality to restart our Python program if it crashes.

The HyGenCMS repository contains two `.service` files which provide systemd services. We just need to load them up. This can be done using the `systemctl` command.

```bash
cd
sudo systemctl enable ~/HygenCMS/linux_setup/configure_outputs.service
sudo systemctl enable ~/HyGenCMS/linux_setup/hygencms.service
```
