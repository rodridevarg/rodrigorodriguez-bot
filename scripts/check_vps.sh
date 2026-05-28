#!/bin/bash

# Bot Multi-Cliente - Health Check y Capacidad
# Uso: ./scripts/check_vps.sh
# Solo lee estado, no modifica nada.

echo "========================================"
echo "  Health Check - VPS Multi-Cliente"
echo "========================================"
echo ""

# Recursos del sistema
echo "--- Recursos del VPS ---"
CPU_CORES=$(nproc 2>/dev/null || echo "?")
MEM_TOTAL=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}')
MEM_AVAIL=$(free -m 2>/dev/null | awk '/^Mem:/{print $7}')
DISK_USED=$(df -h /mnt/data 2>/dev/null | awk 'NR==2{print $3}')
DISK_AVAIL=$(df -h /mnt/data 2>/dev/null | awk 'NR==2{print $4}')
DISK_PCT=$(df -h /mnt/data 2>/dev/null | awk 'NR==2{print $5}')

echo "  CPU cores: ${CPU_CORES}"
if [ -n "$MEM_TOTAL" ]; then
    echo "  RAM total: ${MEM_TOTAL}MB | disponible: ${MEM_AVAIL}MB"
    # Cada instancia ~300MB
    EST_CLIENTES=$((MEM_AVAIL / 300))
    echo "  Estimado clientes nuevos (300MB c/u): ~${EST_CLIENTES}"
else
    echo "  RAM: (no disponible)"
fi
if [ -n "$DISK_AVAIL" ]; then
    echo "  Disco /mnt/data: usado ${DISK_USED} | libre ${DISK_AVAIL} (${DISK_PCT} usado)"
else
    echo "  Disco: (no disponible)"
fi
echo ""

# Contenedores de aibrain
echo "--- aibrain ---"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep "^boston" || echo "   [INFO] No hay contenedores de aibrain corriendo"

echo ""
# Contenedores de bots (todos los que no son boston)
echo "--- Bots activos ---"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -v "^boston" | grep -v "NAMES" || echo "   [INFO] No hay bots corriendo"

echo ""
# Red compartida
echo "--- Red compartida ---"
docker network inspect boston-ai_default --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}{{println}}{{end}}' 2>/dev/null || echo "   Red no encontrada o vacia"

echo ""
# Test HTTP dinamico: leer dominios de cada cliente
echo "--- Test endpoints ---"
for ENV_FILE in /mnt/data/cliente-*/.env; do
    [ -f "$ENV_FILE" ] || continue
    CLIENT_DOMAIN=$(grep "^DOMAIN=" "$ENV_FILE" | cut -d= -f2- | tr -d '"' || true)
    CLIENT_SLUG=$(basename "$(dirname "$ENV_FILE")" | sed 's/cliente-//')
    if [ -n "$CLIENT_DOMAIN" ]; then
        echo "${CLIENT_SLUG} (${CLIENT_DOMAIN}):"
        curl -s "https://${CLIENT_DOMAIN}/health" 2>/dev/null | head -c 200 || echo " [ERROR o timeout]"
        echo ""
    fi
done

echo "========================================"
echo "  NOTA: Si el disco >80% o RAM <500MB,"
echo "  considerar ampliar el VPS."
echo "========================================"
