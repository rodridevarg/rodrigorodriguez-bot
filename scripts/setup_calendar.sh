#!/bin/bash
# =============================================================================
# setup_calendar.sh - Configura Google Calendar para un cliente existente
# =============================================================================
#
# USO:
#   ./scripts/setup_calendar.sh --slug nspa
#
# REQUISITOS:
#   - El cliente ya debe haber creado un calendario en Google Calendar
#   - El cliente debe compartir el calendario con la cuenta de servicio:
#     nspa-865@guild-f42e3.iam.gserviceaccount.com
#   - El cliente debe proporcionar el ID del calendario
#
# =============================================================================

set -euo pipefail

CLIENTS_BASE_DIR="/mnt/data"
TEMPLATE_DIR="/mnt/data/rodrigo-bot-template"

# ============================
# HELPERS
# ============================
function error_exit() {
    echo "[ERROR] $1" >&2
    exit 1
}

# ============================
# PARSE ARGS
# ============================
SLUG=""
CALENDAR_ID=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --slug) SLUG="$2"; shift 2 ;;
        --calendar-id) CALENDAR_ID="$2"; shift 2 ;;
        -h|--help) 
            echo "Uso: $0 --slug <slug> [--calendar-id <id>]"
            echo ""
            echo "Si no pasas --calendar-id, el script te preguntará."
            exit 0
            ;;
        *) error_exit "Parámetro desconocido: $1" ;;
    esac
done

[[ -z "$SLUG" ]] && error_exit "Falta --slug"

CLIENT_DIR="${CLIENTS_BASE_DIR}/cliente-${SLUG}"
[[ -d "$CLIENT_DIR" ]] || error_exit "Cliente no encontrado: ${CLIENT_DIR}"

# ============================
# INSTRUCCIONES
# ============================
echo "========================================"
echo "  CONFIGURACIÓN DE GOOGLE CALENDAR"
echo "========================================"
echo ""
echo "Paso 1: Pedile al cliente que cree un calendario nuevo en Google Calendar"
echo ""
echo "Paso 2: Compartir el calendario con permisos de 'Hacer cambios y gestionar'"
echo "         a: nspa-865@guild-f42e3.iam.gserviceaccount.com"
echo ""
echo "Paso 3: Obtener el ID del calendario:"
echo "         - Ir a Configuración del calendario"
echo "         - Copiar el ID (formato: xxxxx@group.calendar.google.com)"
echo ""

if [[ -z "$CALENDAR_ID" ]]; then
    read -p "Ingresá el ID del calendario: " CALENDAR_ID
fi

[[ -z "$CALENDAR_ID" ]] && error_exit "ID de calendario requerido"

# ============================
# ACTUALIZAR .ENV
# ============================
echo ""
echo "[1/3] Actualizando .env..."

# Leer el GOOGLE_SERVICE_ACCOUNT_JSON del template
SERVICE_ACCOUNT_JSON=$(grep "^GOOGLE_SERVICE_ACCOUNT_JSON=" "${TEMPLATE_DIR}/.env" | cut -d= -f2- | head -1 || true)

# Agregar variables al .env del cliente
if ! grep -q "GOOGLE_CALENDAR_ID" "${CLIENT_DIR}/.env"; then
    echo "" >> "${CLIENT_DIR}/.env"
    echo "# Google Calendar" >> "${CLIENT_DIR}/.env"
    echo "GOOGLE_CALENDAR_ID=\"${CALENDAR_ID}\"" >> "${CLIENT_DIR}/.env"
    echo "GOOGLE_SERVICE_ACCOUNT_JSON=${SERVICE_ACCOUNT_JSON}" >> "${CLIENT_DIR}/.env"
    echo "   [OK] Variables agregadas al .env"
else
    # Actualizar el ID existente
    sed -i "s|GOOGLE_CALENDAR_ID=.*|GOOGLE_CALENDAR_ID=\"${CALENDAR_ID}\"|" "${CLIENT_DIR}/.env"
    echo "   [OK] GOOGLE_CALENDAR_ID actualizado"
fi

# ============================
# AGREGAR CONFIGURACIÓN DE SERVICIOS
# ============================
echo ""
echo "[2/3] Creando configuración de servicios y horarios..."

# Crear services.json si no existe
if [[ ! -f "${CLIENT_DIR}/data/services.json" ]]; then
    cat > "${CLIENT_DIR}/data/services.json" <<'EOF'
{
  "servicios": [
    {
      "id": "servicio_ejemplo",
      "nombre": "Servicio de Ejemplo",
      "categoria": "General",
      "duracion_minutos": 60,
      "precio": 10000,
      "keywords": ["ejemplo", "general", "servicio"]
    }
  ]
}
EOF
    echo "   [OK] services.json creado (template)"
fi

# Crear horarios.json si no existe
if [[ ! -f "${CLIENT_DIR}/data/horarios.json" ]]; then
    cat > "${CLIENT_DIR}/data/horarios.json" <<'EOF'
{
  "zona_horaria": "America/Argentina/Buenos_Aires",
  "dias": {
    "lunes": {"apertura": "09:00", "cierre": "18:00", "abierto": true},
    "martes": {"apertura": "09:00", "cierre": "18:00", "abierto": true},
    "miercoles": {"apertura": "09:00", "cierre": "18:00", "abierto": true},
    "jueves": {"apertura": "09:00", "cierre": "18:00", "abierto": true},
    "viernes": {"apertura": "09:00", "cierre": "18:00", "abierto": true},
    "sabado": {"abierto": false},
    "domingo": {"abierto": false}
  },
  "duracion_turno_default": 60,
  "intervalo_minutos": 30,
  "feriados": []
}
EOF
    echo "   [OK] horarios.json creado (template)"
fi

# ============================
# REINICIAR CONTENEDORES
# ============================
echo ""
echo "[3/3] Reiniciando contenedores..."
cd "$CLIENT_DIR"
docker compose down && docker compose up -d

echo ""
echo "========================================"
echo "  CONFIGURACIÓN COMPLETADA"
echo "========================================"
echo ""
echo "  Cliente: ${SLUG}"
echo "  Calendario: ${CALENDAR_ID}"
echo ""
echo "  Próximos pasos:"
echo "  1. Editar servicios: ${CLIENT_DIR}/data/services.json"
echo "  2. Editar horarios: ${CLIENT_DIR}/data/horarios.json"
echo "  3. Probar: curl https://${SLUG}.asistentebot.com.ar/health"
echo ""
