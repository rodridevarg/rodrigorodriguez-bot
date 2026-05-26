#!/bin/bash

# Rodrigo Rodriguez Bot - Health Check
# Uso: ./scripts/check_vps.sh
# Solo lee estado, no modifica nada.

echo "========================================"
echo "  Health Check - VPS"
echo "========================================"
echo ""

# Contenedores de aibrain
echo "--- aibrain ---"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep "^boston" || echo "   [INFO] No hay contenedores de aibrain corriendo"

echo ""
# Contenedores de rodrigo
echo "--- rodrigo-bot ---"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep "^rodrigo" || echo "   [INFO] No hay contenedores de rodrigo-bot corriendo"

echo ""
# Red compartida
echo "--- Red compartida ---"
docker network inspect boston-ai_default --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}{{println}}{{end}}' 2>/dev/null || echo "   Red no encontrada o vacia"

echo ""
# Test HTTP
echo "--- Test endpoints ---"
echo "aibrain health:"
curl -s https://bot.bostonuniformes.com.ar/health 2>/dev/null | head -c 200 || echo " [ERROR o timeout]"
echo ""
echo "rodrigo health:"
curl -s https://bot.rodrigorodriguez.com.ar/health 2>/dev/null | head -c 200 || echo " [ERROR o timeout]"

echo ""
echo "========================================"
