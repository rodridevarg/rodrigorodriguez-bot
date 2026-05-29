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

# 4. Agregar bloque a Caddyfile
echo "[4/5] Configurando Caddyfile..."
CADDYFILE="/mnt/data/boston-ai/Caddyfile"
if [[ -f "$CADDYFILE" ]]; then
    if ! grep -q "asistentebot.com.ar" "$CADDYFILE"; then
        cat >> "$CADDYFILE" <<EOF

# asistentebot.com.ar (webhook router)
asistentebot.com.ar {
    handle /webhook* {
        reverse_proxy webhook-router:8100
    }
    handle {
        respond "Asistente Bot - Multi-Cliente WhatsApp"
    }
    log {
        output file /data/caddy/access-router.log
    }
}
EOF
        echo "   [OK] Bloque agregado a Caddyfile."
    else
        echo "   [INFO] Bloque de asistentebot.com.ar ya existe en Caddyfile."
    fi
else
    echo "   [WARN] Caddyfile no encontrado en ${CADDYFILE}. Agregar manualmente:"
    cat <<EOF
asistentebot.com.ar {
    handle /webhook* {
        reverse_proxy webhook-router:8100
    }
    handle {
        respond "Asistente Bot - Multi-Cliente WhatsApp"
    }
}
EOF
fi

# 5. Levantar router
echo "[5/5] Levantando contenedores..."
cd "$ROUTER_DIR"
docker compose up -d --build

# Recargar Caddy
echo ""
echo "Recargando Caddy..."
cd /mnt/data/boston-ai && docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile 2>/dev/null || echo "[WARN] No se pudo recargar Caddy automaticamente."

echo ""
echo "========================================"
echo "  ROUTER CONFIGURADO Y LISTO"
echo "========================================"
echo ""
echo "  Directorio: ${ROUTER_DIR}"
echo "  Health:     http://127.0.0.1:8100/health"
echo "  Webhook:    https://asistentebot.com.ar/webhook"
echo ""
echo "  Proximos pasos:"
echo "  1. Editar ${ROUTER_DIR}/.env con valores reales de Meta"
echo "  2. Reiniciar router: cd ${ROUTER_DIR} && docker compose down && docker compose up -d"
echo "     IMPORTANTE: 'docker compose restart' NO lee cambios de .env."
echo "  3. Configurar Meta: webhook URL = https://asistentebot.com.ar/webhook"
echo "  4. Actualizar bot de Rodrigo: poner META_VALIDATE_SIGNATURE=false en su .env"
echo "  5. Registrar bot existente (Rodrigo) en el router"
echo "  6. Probar: curl https://asistentebot.com.ar/webhook (debe dar 401/403, no 404)"
echo ""
echo "  Para crear un cliente nuevo:"
echo "    ./scripts/new_client.sh --name 'Nombre' --slug slug --domain dominio.asistentebot.com.ar --phone '+54...' --meta-phone-number-id ID_META"
echo ""
echo "========================================"
