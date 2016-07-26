#!/bin/sh

# Update package lists & upgrade
sudo apt-get update
sudo apt-get upgrade
sudo apt-get dist-upgrade

# Clean up downloaded packages
sudo apt-get clean
sudo apt-get autoclean