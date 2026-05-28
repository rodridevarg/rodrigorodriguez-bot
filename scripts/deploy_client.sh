#!/bin/bash
set -euo pipefail

# deploy_client.sh - Actualiza codigo de un cliente existente (nueva version del template)
# Uso: ./scripts/deploy_client.sh --slug medico [--no-backup]

TEMPLATE_DIR="/mnt/data/rodrigo-bot-template"
CLIENTS_BASE_DIR="/mnt/data"

function usage() {
    cat <<EOF
Uso: $0 --slug <slug> [opciones]

Obligatorios:
  --slug     Slug del cliente a actualizar

Opcionales:
  --no-backup  No hacer backup antes de actualizar

Ejemplo:
  $0 --slug medico
EOF
    exit 1
}

function error_exit() {
    echo "[ERROR] $1" >&2
    exit 1
}

SLUG=""
NO_BACKUP=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --slug) SLUG="$2"; shift 2 ;;
        --no-backup) NO_BACKUP=true; shift ;;
        -h|--help) usage ;;
        *) error_exit "Parametro desconocido: $1" ;;
    esac
done

[[ -z "$SLUG" ]] && error_exit "Falta --slug"

CLIENT_DIR="${CLIENTS_BASE_DIR}/cliente-${SLUG}"
[[ -d "$CLIENT_DIR" ]] || error_exit "Cliente '${SLUG}' no encontrado en ${CLIENT_DIR}"

BACKUP_DIR=""
if [[ "$NO_BACKUP" == false ]]; then
    BACKUP_DIR="${CLIENT_DIR}/.backup-$(date +%Y%m%d-%H%M%S)"
    echo "[1/6] Haciendo backup en ${BACKUP_DIR}..."
    mkdir -p "$BACKUP_DIR"
    cp "${CLIENT_DIR}/.env" "${BACKUP_DIR}/"
    cp -r "${CLIENT_DIR}/data" "${BACKUP_DIR}/"
    echo "   [OK] Backup completo."
else
    echo "[1/6] Backup omitido (--no-backup)."
fi

# ============================
# 2. Copiar codigo actualizado
# ============================
echo "[2/6] Copiando archivos actualizados del template..."
cp -r "${TEMPLATE_DIR}/app" "$CLIENT_DIR/"
cp -r "${TEMPLATE_DIR}/ui" "$CLIENT_DIR/"
cp -r "${TEMPLATE_DIR}/scripts" "$CLIENT_DIR/"
cp "${TEMPLATE_DIR}/Dockerfile" "$CLIENT_DIR/"
cp "${TEMPLATE_DIR}/requirements.txt" "$CLIENT_DIR/"

# Actualizar docker-compose desde template
sed -e "s/{{SLUG}}/${SLUG}/g" "${TEMPLATE_DIR}/docker-compose.template.yml" > "${CLIENT_DIR}/docker-compose.yml"

echo "   [OK] Codigo actualizado."

# ============================
# 3. Restaurar configuracion
# ============================
if [[ -n "$BACKUP_DIR" && -f "${BACKUP_DIR}/.env" ]]; then
    echo "[3/6] Restaurando .env desde backup..."
    cp "${BACKUP_DIR}/.env" "${CLIENT_DIR}/.env"
else
    echo "[3/6] Manteniendo .env actual."
fi

echo "   [OK] Configuracion restaurada."

# ============================
# 4. Reconstruir contenedores
# ============================
echo "[4/6] Reconstruyendo contenedores..."
cd "$CLIENT_DIR"
docker compose down
docker compose up -d --build

# ============================
# 5. Verificar health
# ============================
echo "[5/6] Verificando health..."
sleep 3
HEALTH_URL="http://localhost:8000/health"
# Intentar desde el contenedor mismo
if docker compose exec -T web python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null; then
    echo "   [OK] Health check paso."
else
    echo "   [WARN] Health check fallo (puede estar iniciando aun). Verificar manualmente."
fi

# ============================
# 6. Resumen
# ============================
echo ""
echo "========================================"
echo "  DEPLOY COMPLETADO"
echo "========================================"
echo ""
echo "  Cliente:     ${SLUG}"
echo "  Directorio:  ${CLIENT_DIR}"
if [[ -n "$BACKUP_DIR" ]]; then
    echo "  Backup:      ${BACKUP_DIR}"
fi
echo ""
echo "  Comandos utiles:"
echo "    Logs:     docker compose -f ${CLIENT_DIR}/docker-compose.yml logs -f"
echo "    Restart:  docker compose -f ${CLIENT_DIR}/docker-compose.yml restart"
echo ""
echo "========================================"
