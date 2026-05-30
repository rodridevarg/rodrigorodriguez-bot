#!/bin/bash
set -e

# Bot Template - Deploy rapido
# Uso: ./scripts/deploy.sh
# Solo toca el bot especifico. No modifica aibrain ni Caddy.

PROJECT_DIR="/mnt/data/rodrigo-bot"

echo "========================================"
echo "  Deploy - Asistente Virtual"
echo "========================================"

# Verificar directorio
if [ ! -d "$PROJECT_DIR" ]; then
    echo "ERROR: $PROJECT_DIR no existe. Ejecuta setup_vps.sh primero."
    exit 1
fi

cd "$PROJECT_DIR"

# 1. Pull de cambios
echo "[1/3] Actualizando codigo..."
git pull origin main || git pull origin master || echo "No se pudo hacer pull, continuando..."

# 2. Reconstruir
echo "[2/3] Reconstruyendo contenedores..."
docker compose up -d --build

# 3. Verificar
echo "[3/3] Verificando estado..."
sleep 3
docker compose ps

echo ""
echo "========================================"
echo "  Deploy completado!"
echo "========================================"
echo "  URL:    https://rodrigo.asistentebot.com.ar"
echo "========================================"
