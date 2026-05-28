#!/bin/bash
set -euo pipefail

# setup_router.sh - Configuracion inicial del webhook-router en el VPS
# Uso: ./scripts/setup_router.sh

ROUTER_DIR="/mnt/data/webhook-router"
TEMPLATE_DIR="/mnt/data/rodrigo-bot-template"

echo "========================================"
echo "  Setup Webhook Router"
echo "========================================"
echo ""

# 1. Crear directorio
echo "[1/4] Creando directorio del router..."
mkdir -p "$ROUTER_DIR"

# 2. Copiar codigo del router
echo "[2/4] Copiando codigo..."
cp -a "${TEMPLATE_DIR}/webhook-router/." "$ROUTER_DIR/"

# 3. Configurar .env
echo "[3/4] Configurando .env..."
if [[ ! -f "${ROUTER_DIR}/.env" ]]; then
    cp "${ROUTER_DIR}/.env.example" "${ROUTER_DIR}/.env"
    echo "   [INFO] Archivo .env creado desde ejemplo. EDITAR con valores reales:"
    echo "   - META_VERIFY_TOKEN (mismo que tu App de Meta)"
    echo "   - META_APP_SECRET (mismo que tu App de Meta)"
    echo "   - ADMIN_API_KEY (generar una clave nueva)"
else
    echo "   [INFO] .env ya existe. No se sobreescribio."
fi

# 4. Levantar router
echo "[4/4] Levantando contenedores..."
cd "$ROUTER_DIR"
docker compose up -d --build

echo ""
echo "========================================"
echo "  ROUTER CONFIGURADO"
echo "========================================"
echo ""
echo "  Directorio: ${ROUTER_DIR}"
echo "  Health:     http://127.0.0.1:8100/health"
echo ""
echo "  Proximos pasos:"
echo "  1. Editar ${ROUTER_DIR}/.env con valores reales de Meta"
echo "  2. Reiniciar router: cd ${ROUTER_DIR} && docker compose restart"
echo "  3. Configurar Meta: webhook URL = https://asistentebot.com.ar/webhook"
echo "  4. Registrar bot existente (Rodrigo):"
echo "     curl -X POST http://webhook-router:8100/admin/register \\"
echo "       -H 'X-Admin-Key: TU_ROUTER_KEY' \\"
echo "       -d '{\"phone_number_id\":\"ID_DE_RODRIGO\",\"client_slug\":\"rodrigo\",\"target_url\":\"http://rodrigo-web:8000/webhook\"}'"
echo ""
echo "========================================"
