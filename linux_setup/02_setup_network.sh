#!/bin/sh
# From hygen user account
# Setup USB gateway 
# (internet sharing must have been enabled from connected computer)
sudo /sbin/route add default gw 192.168.7.1

# if ping isn't working, set SUID bit
ping 8.8.8.8 || sudo chmod u+s `which ping`

# Edit the /etc/network/interfaces file to set a static IP
sudo vi /etc/network/interfaces
# Make the following changes:
# iface eth0 inet dhcp => iface eth0 inet static
# Add the following lines
# address 10.50.0.x (pick a free static IP)
# gateway 10.50.0.1
# netmask 255.255.255.0
