#!/bin/bash
clear
apt update -y
dpkg --configure -a
apt upgrade -y
apt install wget -y
[[ -e Plus ]] && rm Plus
wget https://raw.githubusercontent.com/vmell0/pro/main/Plus
chmod 777 Plus
./Plus