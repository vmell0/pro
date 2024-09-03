#!/bin/bash

CONFIG_FILE="/etc/ssh/sshd_config"
TEMP_FILE="/tmp/sshd"

modify_sshd_config() {
    local search="$1"
    local replace="$2"
    if grep -q "$search" "$CONFIG_FILE"; then
        sed -i "s/$search/$replace/g" "$CONFIG_FILE"
    fi
}

# Modificar o arquivo de configuração do SSH
modify_sshd_config "prohibit-password" "yes"
modify_sshd_config "without-password" "yes"
modify_sshd_config "#PermitRootLogin" "PermitRootLogin"

# Remover entradas de configuração específicas
for setting in "PasswordAuthentication" "X11Forwarding" "ClientAliveInterval" "ClientAliveCountMax" "MaxStartups"; do
    if grep -q "$setting" "$CONFIG_FILE"; then
        grep -v "^${setting}[[:space:]]" "$CONFIG_FILE" > "$TEMP_FILE" && cat "$TEMP_FILE" > "$CONFIG_FILE"
        grep -v "^#${setting}[[:space:]]" "$CONFIG_FILE" > "$TEMP_FILE" && cat "$TEMP_FILE" > "$CONFIG_FILE"
    fi
done

# Adicionar configurações desejadas
echo 'PasswordAuthentication yes' >> "$CONFIG_FILE"
echo 'X11Forwarding no' >> "$CONFIG_FILE"
echo 'ClientAliveInterval 60' >> "$CONFIG_FILE"
echo 'ClientAliveCountMax 3' >> "$CONFIG_FILE"
echo 'MaxStartups 100:10:1000' >> "$CONFIG_FILE"

# Remover o script gestor_swap.sh
rm -f gestor_swap.sh

# Função para verificar e instalar o bc se necessário
verificar_bc() {
    if ! command -v bc &> /dev/null; then
        apt-get update &> /dev/null
        apt-get install -y bc &> /dev/null
        if [ $? -ne 0 ]; then
            echo "Erro ao instalar 'bc'. Verifique sua conexão com a internet ou instale manualmente."
            exit 1
        fi
    fi
}

# Variáveis de cores para o terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Verificar a presença do bc
verificar_bc

# Função para executar comandos com barra de progresso
executar_comando() {
    local comando="$1"
    local mensagem="$2"
    local delay=0.1
    local percent=0
    local bar=""

    echo -e "${BLUE}${mensagem:0:50}...${NC}"
    echo -n ' '
    
    eval "$comando" & local cmd_pid=$!
    
    while kill -0 $cmd_pid 2>/dev/null; do
        percent=$((percent + 1))
        if [ $percent -ge 100 ]; then
            percent=100
        fi
        echo -ne "\r[${bar:0:$((percent / 5))}] $percent%"
        sleep $delay
        bar=$(printf "%-20s" | tr ' ' '=')
    done

    wait $cmd_pid
    if [ $? -eq 0 ]; then
        percent=100
        echo -ne "\r[${bar:0:20}] $percent%${NC}\n"
    else
        echo -e "\r${RED}Erro ao executar o comando.${NC}"
    fi
    
    echo
    sleep 1
}

# Limpeza inicial
clear
echo -e "${YELLOW}======================================${NC}"
echo -e "${YELLOW}              GESTOR-SWAP${NC}"
echo -e "${YELLOW}======================================${NC}"
echo

executar_comando "apt-get clean &> /dev/null && apt-get autoclean &> /dev/null && apt-get autoremove -y &> /dev/null" "Limpando cache de pacotes"
executar_comando "find /var/log -type f \( -name '*.gz' -o -name '*.[0-9]' \) -exec rm -f {} + &> /dev/null && find /var/log -type f -exec truncate -s 0 {} + &> /dev/null" "Limpando logs antigos"
executar_comando "rm -rf /tmp/* &> /dev/null" "Limpando arquivos temporários"
executar_comando "sync; echo 3 > /proc/sys/vm/drop_caches &> /dev/null" "Limpando cache do sistema"

echo -e "${GREEN}Limpeza inicial concluída.${NC}"
echo

executar_comando "echo 1 > /proc/sys/vm/drop_caches &> /dev/null" "Limpando a memória RAM"
echo -e "${GREEN}Memória RAM limpa.${NC}"
echo

# Desativar qualquer swap existente
executar_comando "swapoff -a &> /dev/null && rm -f /swapfile /bin/ram.img &> /dev/null" "Desativando qualquer swap existente"

# Calcular tamanho da swap
echo -e "${BLUE}Calculando tamanho da swap...${NC}"
disk=$(lsblk -o KNAME,TYPE | grep 'disk' | awk '{print $1}')
if [ -z "$disk" ]; then
    echo "Não foi possível encontrar o disco principal."
    exit 1
fi

total_size=$(lsblk -b -d -o SIZE "/dev/$disk" | tail -n1)
total_size_mb=$((total_size / (1024 * 1024)))

swap_size=$(echo "$total_size_mb * 0.20 / 1" | bc)
swap_size_rounded=$(( ((swap_size + 1023) / 1024) * 1024 ))

echo
echo -e "${YELLOW}Tamanho da swap: ${swap_size_rounded} MB (${swap_size_rounded} MB / $(echo "$swap_size_rounded / 1024" | bc) GB)${NC}"
echo

# Criar e ativar swap
executar_comando "dd if=/dev/zero of=/bin/ram.img bs=1M count=$swap_size_rounded &> /dev/null && chmod 600 /bin/ram.img &> /dev/null && mkswap /bin/ram.img &> /dev/null && swapon /bin/ram.img &> /dev/null" "Criando e ativando swap"
executar_comando "sed -i '/\/bin\/ram.img/d' /etc/fstab &> /dev/null && echo '/bin/ram.img none swap sw 0 0' >> /etc/fstab" "Configurando swap"

echo -e "${GREEN}Swap criada e ativada com sucesso!${NC}"
echo

# Script de limpeza automático
cat << 'EOF' > /opt/limpeza.sh
#!/bin/bash

LOG_DIR="/root/limpeza"
mkdir -p "$LOG_DIR"
current_date=$(date +%Y%m%d)
max_days=7

cleanup_old_logs() {
    for logfile in "$LOG_DIR"/*.txt; do
        log_date=$(basename "$logfile" .txt | cut -c1-8)
        days_diff=$(( (current_date - log_date) / 10000 ))
        if [ "$days_diff" -gt "$max_days" ]; then
            rm "$logfile"
        fi
    done
}

cleanup_old_logs

LOG_FILE="$LOG_DIR/$(date +%Y%m%d).txt"
current_time=$(date '+%d/%m/%Y %H:%M:%S')
apt-get clean &> /dev/null
apt-get autoclean &> /dev/null
apt-get autoremove -y &> /dev/null
find /var/log -type f \( -name '*.gz' -o -name '*.[0-9]' \) -exec rm -f {} + &> /dev/null && find /var/log -type f -exec truncate -s 0 {} + &> /dev/null
rm -rf /tmp/* &> /dev/null
sync; echo 3 > /proc/sys/vm/drop_caches &> /dev/null
pm2 flush &> /dev/null
echo "$current_time - Script de limpeza executado" >> "$LOG_FILE"

exit 0
EOF

chmod +x /opt/limpeza.sh

# Serviço systemd para o script de limpeza
cat << 'EOF' > /etc/systemd/system/limpeza.service
[Unit]
Description=Script de limpeza do sistema
After=network.target

[Service]
Type=oneshot
ExecStart=/bin/bash /opt/limpeza.sh

[Install]
WantedBy=multi-user.target
EOF

executar_comando "systemctl daemon-reload &> /dev/null && systemctl enable limpeza.service &> /dev/null && systemctl start limpeza.service &> /dev/null" "Configurando script de limpeza"

# Reiniciar o serviço SSH
/etc/init.d/ssh restart &> /dev/null
echo -e "${GREEN}Configuração concluída.${NC}"

exit 0
