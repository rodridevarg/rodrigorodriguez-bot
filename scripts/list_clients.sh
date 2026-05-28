#!/bin/bash
set -euo pipefail

# list_clients.sh - Lista todos los clientes activos con estado
# Uso: ./scripts/list_clients.sh

CLIENTS_BASE_DIR="/mnt/data"
CADDYFILE="/mnt/data/boston-ai/Caddyfile"

echo "========================================"
echo "  CLIENTES ACTIVOS"
echo "========================================"
echo ""

# Verificar si hay clientes
CLIENTS=$(find "$CLIENTS_BASE_DIR" -maxdepth 1 -type d -name "cliente-*" | sort)

if [[ -z "$CLIENTS" ]]; then
    echo "  No hay clientes activos."
    echo ""
    echo "  Crear uno con: ./scripts/new_client.sh --name 'Nombre' --slug slug --domain dominio --phone '+54...'"
    echo "========================================"
    exit 0
fi

# Encabezado
printf "  %-15s %-25s %-20s %-15s\n" "SLUG" "DOMINIO" "ESTADO" "CONTENEDORES"
printf "  %-15s %-25s %-20s %-15s\n" "---------------" "-------------------------" "--------------------" "---------------"

for CLIENT_DIR in $CLIENTS; do
    SLUG=$(basename "$CLIENT_DIR" | sed 's/cliente-//')
    
    # Leer dominio del .env
    DOMAIN=""
    if [[ -f "${CLIENT_DIR}/.env" ]]; then
        DOMAIN=$(grep "^DOMAIN=" "${CLIENT_DIR}/.env" | cut -d= -f2 || true)
    fi
    [[ -z "$DOMAIN" ]] && DOMAIN="(sin dominio)"
    
    # Estado de contenedores
    WEB_STATUS=$(docker inspect --format='{{.State.Status}}' "${SLUG}-web" 2>/dev/null || echo "no_existe")
    WORKER_STATUS=$(docker inspect --format='{{.State.Status}}' "${SLUG}-worker" 2>/dev/null || echo "no_existe")
    
    if [[ "$WEB_STATUS" == "running" && "$WORKER_STATUS" == "running" ]]; then
        ESTADO="ok"
        COLOR="\033[32m"
    elif [[ "$WEB_STATUS" == "no_existe" && "$WORKER_STATUS" == "no_existe" ]]; then
        ESTADO="detenido"
        COLOR="\033[31m"
    else
        ESTADO="parcial"
        COLOR="\033[33m"
    fi
    
    CONTENEDORES=""
    [[ "$WEB_STATUS" == "running" ]] && CONTENEDORES="web "
    [[ "$WORKER_STATUS" == "running" ]] && CONTENEDORES="${CONTENEDORES}worker"
    [[ -z "$CONTENEDORES" ]] && CONTENEDORES="ninguno"
    
    printf "  %-15s %-25s ${COLOR}%-20s\033[0m %-15s\n" "$SLUG" "$DOMAIN" "$ESTADO" "$CONTENEDORES"
done

echo ""

# Recursos totales
echo "--- Recursos del VPS ---"
MEM_TOTAL=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}')
MEM_AVAIL=$(free -m 2>/dev/null | awk '/^Mem:/{print $7}')
DISK_PCT=$(df -h /mnt/data 2>/dev/null | awk 'NR==2{print $5}')

if [[ -n "$MEM_TOTAL" ]]; then
    EST_CLIENTES=$((MEM_AVAIL / 300))
    echo "  RAM disponible: ${MEM_AVAIL}MB / ${MEM_TOTAL}MB | Clientes nuevos posibles: ~${EST_CLIENTES}"
fi
[[ -n "$DISK_PCT" ]] && echo "  Disco usado: ${DISK_PCT}"

echo ""
echo "========================================"
