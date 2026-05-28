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
# 2. Detener y eliminar contenedores
# ============================
echo "[1/5] Deteniendo contenedores..."
cd "$CLIENT_DIR"
docker compose down 2>/dev/null || true

# Eliminar volumen explicitamente
echo "[2/5] Eliminando volumen..."
docker volume rm "${SLUG}-data" 2>/dev/null || echo "   [INFO] Volumen ya no existia o no encontrado."

# ============================
# 3. Eliminar directorio
# ============================
echo "[3/5] Eliminando directorio..."
rm -rf "$CLIENT_DIR"
echo "   [OK] ${CLIENT_DIR} eliminado."

# ============================
# 4. Limpiar Caddyfile
# ============================
echo "[4/5] Limpiando Caddyfile..."
if [[ -f "$CADDYFILE" ]]; then
    # Crear backup del Caddyfile
    cp "$CADDYFILE" "${CADDYFILE}.backup-$(date +%Y%m%d-%H%M%S)"
    
    # Eliminar bloque del cliente (desde el comentario hasta la siguiente linea en blanco o fin)
    # Usar sed para borrar desde "# .* (cliente-SLUG)" hasta la siguiente linea que empieza con # o fin de archivo
    python3 -c "
import re
with open('$CADDYFILE', 'r') as f:
    content = f.read()
# Patron: desde comentario con cliente-SLUG hasta antes del siguiente bloque comentado o fin
pattern = r'\n#\s+.*\(cliente-${SLUG}\)\n.*?\n(?=\n#|\Z)'
new_content = re.sub(pattern, '\n', content, flags=re.DOTALL)
# Tambien limpiar multiples saltos de linea
new_content = re.sub(r'\n{3,}', '\n\n', new_content)
with open('$CADDYFILE', 'w') as f:
    f.write(new_content)
" 2>/dev/null || echo "   [WARN] No se pudo limpiar Caddyfile automaticamente. Editar manualmente."
    
    echo "   [OK] Caddyfile actualizado."
else
    echo "   [WARN] Caddyfile no encontrado."
fi

# ============================
# 5. Recargar Caddy
# ============================
echo "[5/5] Recargando Caddy..."
cd /mnt/data/boston-ai && docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile 2>/dev/null || echo "   [WARN] No se pudo recargar Caddy automaticamente."

echo ""
echo "========================================"
echo "  CLIENTE '${SLUG}' ELIMINADO"
echo "========================================"
