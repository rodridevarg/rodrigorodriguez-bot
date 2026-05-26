#!/bin/bash
set -e

# Rodrigo Rodriguez Bot - Setup inicial en VPS
# Uso: Ejecutar UNA SOLA VEZ. Se auto-elimina al finalizar.
# IMPORTANTE: Verificar que aibrain este funcionando antes de ejecutar.

PROJECT_DIR="/mnt/data/rodrigo-bot"
BOSTON_DIR="/mnt/data/boston-ai"
VPS_IP="167.114.96.29"
THIS_SCRIPT="$0"

echo "========================================"
echo "  Setup Inicial - Secretaria Virtual"
echo "  Rodrigo Rodriguez"
echo "========================================"
echo ""
echo "ADVERTENCIA: Este script se ejecuta UNA SOLA VEZ."
echo "Se auto-eliminara al finalizar."
echo ""

# ========================================
# 1. Verificar que aibrain esta sano
# ========================================
echo "[1/8] Verificando que aibrain esta funcionando..."
if ! docker ps --format '{{.Names}}' | grep -q "^boston-caddy$"; then
    echo "ERROR: boston-caddy no esta corriendo. Abortando."
    exit 1
fi
if ! docker ps --format '{{.Names}}' | grep -q "^boston-web$"; then
    echo "ERROR: boston-web no esta corriendo. Abortando."
    exit 1
fi
echo "   [OK] aibrain esta saludable."

# ========================================
# 2. Verificar que el directorio no existe
# ========================================
echo "[2/8] Verificando directorio del proyecto..."
if [ -d "$PROJECT_DIR" ]; then
    echo "ERROR: $PROJECT_DIR ya existe. Si necesitas reinstalar, elimina el directorio primero."
    exit 1
fi

# ========================================
# 3. Clonar repositorio
# ========================================
echo "[3/8] Clonando repositorio..."
cd /mnt/data
git clone <TU-REPO-URL> rodrigo-bot || {
    echo "ERROR: No se pudo clonar el repositorio."
    exit 1
}

# ========================================
# 4. Configurar .env
# ========================================
echo "[4/8] Configurando .env..."
cd "$PROJECT_DIR"
if [ ! -f ".env.example" ]; then
    echo "ERROR: No se encontro .env.example"
    exit 1
fi
cp .env.example .env
echo "   [INFO] Edita .env manualmente con tus credenciales reales:"
echo "          nano $PROJECT_DIR/.env"
echo "   Presiona ENTER cuando hayas editado .env..."
read -r

# ========================================
# 5. Verificar DNS
# ========================================
echo "[5/8] Verificando DNS..."
echo "   IMPORTANTE: Asegurate de tener el registro A en Cloudflare:"
echo "   Nombre: bot"
echo "   Valor: $VPS_IP"
echo ""
nslookup bot.rodrigorodriguez.com.ar || echo "   [WARN] DNS aun no propagado."

# ========================================
# 6. Agregar bloque de rodrigo al Caddyfile de aibrain
# ========================================
echo "[6/8] Configurando Caddy maestro (aibrain)..."
cd "$BOSTON_DIR"
if grep -q "bot.rodrigorodriguez.com.ar" Caddyfile; then
    echo "   [INFO] Bloque de rodrigo ya existe en Caddyfile."
else
    echo "" >> Caddyfile
    echo "# ========================================" >> Caddyfile
    echo "# bot.rodrigorodriguez.com.ar (rodrigo-bot)" >> Caddyfile
    echo "# ========================================" >> Caddyfile
    echo "bot.rodrigorodriguez.com.ar {" >> Caddyfile
    echo "    header {" >> Caddyfile
    echo "        X-Content-Type-Options nosniff" >> Caddyfile
    echo "        X-Frame-Options DENY" >> Caddyfile
    echo "        Referrer-Policy strict-origin-when-cross-origin" >> Caddyfile
    echo "    }" >> Caddyfile
    echo "" >> Caddyfile
    echo "    encode gzip" >> Caddyfile
    echo "" >> Caddyfile
    echo "    handle /health {" >> Caddyfile
    echo "        reverse_proxy rodrigo-web:8000" >> Caddyfile
    echo "    }" >> Caddyfile
    echo "" >> Caddyfile
    echo "    handle /webhook {" >> Caddyfile
    echo "        reverse_proxy rodrigo-web:8000" >> Caddyfile
    echo "    }" >> Caddyfile
    echo "" >> Caddyfile
    echo "    handle {" >> Caddyfile
    echo "        reverse_proxy rodrigo-web:8000" >> Caddyfile
    echo "    }" >> Caddyfile
    echo "" >> Caddyfile
    echo "    log {" >> Caddyfile
    echo "        output file /data/caddy/access-rodrigo.log" >> Caddyfile
    echo "        format json" >> Caddyfile
    echo "    }" >> Caddyfile
    echo "}" >> Caddyfile
    echo "   [OK] Bloque agregado al Caddyfile."
fi

# ========================================
# 7. Agregar red compartida al docker-compose de aibrain
# ========================================
echo "[7/8] Configurando red compartida en aibrain..."
if grep -q "boston-ai_default" "$BOSTON_DIR/docker-compose.yml"; then
    echo "   [INFO] Red compartida ya configurada en aibrain."
else
    # Agregar networks al final del docker-compose de aibrain
    echo "" >> "$BOSTON_DIR/docker-compose.yml"
    echo "networks:" >> "$BOSTON_DIR/docker-compose.yml"
    echo "  boston-ai_default:" >> "$BOSTON_DIR/docker-compose.yml"
    echo "    name: boston-ai_default" >> "$BOSTON_DIR/docker-compose.yml"
    echo "    driver: bridge" >> "$BOSTON_DIR/docker-compose.yml"
    echo "    external: true" >> "$BOSTON_DIR/docker-compose.yml"
    echo "   [OK] Red compartida agregada."
fi

# ========================================
# 8. Levantar rodrigo-bot
# ========================================
echo "[8/8] Levantando rodrigo-bot..."
cd "$PROJECT_DIR"
docker compose up -d --build

# Verificar estado
echo ""
echo "========================================"
echo "  Verificando estado..."
echo "========================================"
sleep 5
docker compose ps

echo ""
echo "========================================"
echo "  Setup completado!"
echo "========================================"
echo "  URL:     https://bot.rodrigorodriguez.com.ar"
echo "  Health:  https://bot.rodrigorodriguez.com.ar/health"
echo "  Chat:    https://bot.rodrigorodriguez.com.ar/chat"
echo "========================================"
echo ""

# ========================================
# AUTO-ELIMINACION
# ========================================
echo "[INFO] Auto-eliminando setup_vps.sh para evitar ejecuciones accidentales..."
rm -f "$THIS_SCRIPT"
echo "[OK] Script eliminado. Usa ./scripts/deploy.sh para deploys posteriores."
