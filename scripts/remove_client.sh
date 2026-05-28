#!/bin/bash
set -euo pipefail

# remove_client.sh - Elimina un cliente completamente
# Uso: ./scripts/remove_client.sh --slug medico [--yes]

CLIENTS_BASE_DIR="/mnt/data"
CADDYFILE="/mnt/data/boston-ai/Caddyfile"

function usage() {
    cat <<EOF
Uso: $0 --slug <slug> [opciones]

Obligatorios:
  --slug     Slug del cliente a eliminar

Opcionales:
  --yes      Confirmar eliminacion sin preguntar

Ejemplo:
  $0 --slug medico --yes
EOF
    exit 1
}

function error_exit() {
    echo "[ERROR] $1" >&2
    exit 1
}

SLUG=""
CONFIRM=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --slug) SLUG="$2"; shift 2 ;;
        --yes) CONFIRM=true; shift ;;
        -h|--help) usage ;;
        *) error_exit "Parametro desconocido: $1" ;;
    esac
done

[[ -z "$SLUG" ]] && error_exit "Falta --slug"

# Validar formato de slug
if [[ ! "$SLUG" =~ ^[a-z0-9-]+$ ]]; then
    error_exit "Slug invalido. Solo letras minusculas, numeros y guiones."
fi

CLIENT_DIR="${CLIENTS_BASE_DIR}/cliente-${SLUG}"
[[ -d "$CLIENT_DIR" ]] || error_exit "Cliente '${SLUG}' no encontrado en ${CLIENT_DIR}"

# ============================
# 1. Confirmacion
# ============================
if [[ "$CONFIRM" == false ]]; then
    echo "[ADVERTENCIA] Esto ELIMINARA permanentemente:"
    echo "  - Directorio: ${CLIENT_DIR}"
    echo "  - Contenedores: ${SLUG}-web, ${SLUG}-worker"
    echo "  - Volumen Docker: ${SLUG}-data"
    echo "  - Entrada en Caddyfile (si existe)"
    echo ""
    read -p "Escribe el slug '${SLUG}' para confirmar: " CONFIRM_INPUT
    [[ "$CONFIRM_INPUT" != "$SLUG" ]] && error_exit "Confirmacion cancelada."
fi

# ============================
# 2. Desregistrar de webhook-router
# ============================
echo "[1/5] Desregistrando de webhook-router..."
META_PHONE_NUMBER_ID=""
if [[ -f "${CLIENT_DIR}/.env" ]]; then
    META_PHONE_NUMBER_ID=$(grep "^META_PHONE_NUMBER_ID=" "${CLIENT_DIR}/.env" | cut -d= -f2- | tr -d '"' || true)
fi

ROUTER_ADMIN_KEY=""
if [[ -f "/mnt/data/webhook-router/.env" ]]; then
    ROUTER_ADMIN_KEY=$(grep "^ADMIN_API_KEY=" /mnt/data/webhook-router/.env | cut -d= -f2- | tr -d '"' || true)
fi

if [[ -n "$ROUTER_ADMIN_KEY" && -n "$META_PHONE_NUMBER_ID" ]]; then
    curl -s -X POST http://webhook-router:8100/admin/unregister \
        -H "Content-Type: application/json" \
        -H "X-Admin-Key: ${ROUTER_ADMIN_KEY}" \
        -d "{\"phone_number_id\":\"${META_PHONE_NUMBER_ID}\"}" \
        >/dev/null && echo "   [OK] Desregistrado del webhook-router." || echo "   [WARN] No se pudo desregistrar del webhook-router."
else
    echo "   [INFO] Router no configurado o sin PHONE_NUMBER_ID. Omitiendo desregistro."
fi

# ============================
# 3. Detener y eliminar contenedores + volumen
# ============================
echo "[2/5] Deteniendo contenedores y eliminando volumen..."
cd "$CLIENT_DIR"
docker compose down -v 2>/dev/null || true

# ============================
# 4. Eliminar directorio
# ============================
echo "[3/5] Eliminando directorio..."
rm -rf "$CLIENT_DIR"
echo "   [OK] ${CLIENT_DIR} eliminado."

# ============================
# 5. Limpiar Caddyfile
# ============================
echo "[4/5] Limpiando Caddyfile..."
if [[ -f "$CADDYFILE" ]]; then
    # Crear backup del Caddyfile
    cp "$CADDYFILE" "${CADDYFILE}.backup-$(date +%Y%m%d-%H%M%S)"

    # Usar awk para eliminar bloque entre comentario del cliente y siguiente comentario/fin
    awk -v slug="$SLUG" '
    BEGIN { skip=0 }
    /^# .* \(cliente-/ {
        if (skip) skip=0
        if ($0 ~ "\(cliente-" slug "\)") { skip=1; next }
    }
    skip && /^#/ { skip=0 }
    !skip { print }
    ' "$CADDYFILE" > "${CADDYFILE}.tmp" && mv "${CADDYFILE}.tmp" "$CADDYFILE"

    # Limpiar lineas en blanco multiples
    awk 'NF || printed { printed=1; print }' "$CADDYFILE" > "${CADDYFILE}.tmp" && mv "${CADDYFILE}.tmp" "$CADDYFILE"

    echo "   [OK] Caddyfile actualizado."
else
    echo "   [WARN] Caddyfile no encontrado."
fi

# ============================
# 6. Recargar Caddy
# ============================
echo "[5/5] Recargando Caddy..."
cd /mnt/data/boston-ai && docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile 2>/dev/null || echo "   [WARN] No se pudo recargar Caddy automaticamente."

# ============================
# 7. Resumen
# ============================
echo ""
echo "========================================"
echo "  CLIENTE '${SLUG}' ELIMINADO"
echo "========================================"
