#!/bin/bash
vermelho="\e[31m"
verde="\e[32m"
amarelo="\e[33m"
azul="\e[34m"
roxo="\e[38;2;128;0;128m"
reset="\e[0m"

rm -rf /root/CheckUser/
rm -f /usr/local/bin/CheckUser
pkill -9 -f "/root/CheckUser/checkuser.py"

apt update && apt upgrade -y && apt install python3 git -y
wget https://raw.githubusercontent.com/vmell0/pro/main/script/CheckUser.zip
unzip CheckUser.zip
rm CheckUser.zip
chmod +x /root/CheckUser/checkuserMenu.sh
ln -s /root/CheckUser/checkuserMenu.sh /usr/local/bin/CheckUser

clear
echo -e "PARA INICIAR O MENU DIGITE: ${verde}CheckUser${reset}"
