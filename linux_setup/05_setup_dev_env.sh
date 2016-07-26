#!/bin/sh

# install ntpdate
sudo apt-get install ntpdate

# set the system time (maybe automatic already?)
sudo ntpdate pool.ntp.org

# Install pip
sudo apt-get install python3-pip

# Install modbus_tk, pulling in pyserial, etc.
sudo pip install modbus_tk

# Install vim
sudo apt-get install vim

# Install unzip
sudo apt-get install unzip

# Install config-pin utility
cd /home/hygen
wget https://github.com/cdsteinkuehler/beaglebone-universal-io/archive/master.zip
unzip master.zip
cd beaglebone-universal-io
sudo make install_target
cd ~
rm master.zip
rm -R beaglebone-universal-io

# Install Adafruit_BBIO, 4.1+ compatible version
wget https://github.com/adafruit/adafruit-beaglebone-io-python/archive/eb0b34746320690953134ebaa024a8171232655a.zip
unzip adafruit-beaglebone-io-python-eb0b34746320690953134ebaa024a8171232655a.zip
cd adafruit-beaglebone-io-python
sudo make install
cd ..
rm adafruit-beaglebone-io-python-eb0b34746320690953134ebaa024a8171232655a.zip
rm -R adafruit-beaglebone-io-python
