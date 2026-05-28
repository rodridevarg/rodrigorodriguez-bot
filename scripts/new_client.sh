#!/bin/bash
set -euo pipefail

# new_client.sh - Crea un nuevo cliente desde cero
# Uso: ./scripts/new_client.sh --name "Dr. Garcia" --slug medico --domain garcia.asistente.ai --phone "+54 11 1234-5678"

# ============================
# CONFIG
# ============================
TEMPLATE_DIR="/mnt/data/rodrigo-bot-template"  # ruta al codigo base (este repo)
CLIENTS_BASE_DIR="/mnt/data"
CADDYFILE="/mnt/data/boston-ai/Caddyfile"
CADDY_NETWORK="boston-ai_default"

# ============================
# HELPERS
# ============================
function usage() {
    cat <<EOF
Uso: $0 --name "Nombre del Cliente" --slug <slug> --domain <dominio> --phone <telefono> [opciones]

Obligatorios:
  --name     Nombre del cliente (ej: "Dr. Garcia")
  --slug     Identificador unico (ej: medico, tienda-juan). Solo letras, numeros, guiones.
  --domain   Subdominio completo (ej: garcia.asistente.ai)
  --phone    Telefono de contacto del negocio (ej: +54 11 1234-5678)

Opcionales:
  --email    Email de contacto
  --bot-name Nombre del bot (default: "Asistente Virtual de <name>")
  --description Descripcion del bot (default: "Asistente automatizado por WhatsApp")
  --collection Nombre de coleccion ChromaDB (default: <slug>_docs)
  --llm-key  API Key del LLM (default: del template .env)
  --llm-url  URL base del LLM (default: del template .env)
  --llm-model Modelo del LLM (default: del template .env)
  --whatsapp-mode Modo WhatsApp: fake o meta (default: fake)
  --meta-phone-number-id ID del numero de telefono en Meta (si modo=meta)
  --admin-key API Key para el panel de admin (generada aleatoriamente si no se especifica)

Ejemplo:
  $0 --name "Dr. Garcia" --slug medico --domain garcia.asistente.ai --phone "+54 11 1234-5678"
EOF
    exit 1
}

function error_exit() {
    echo "[ERROR] $1" >&2
    exit 1
}

function slugify() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-'
}

function generate_key() {
    openssl rand -hex 24 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 48
}

# ============================
# PARSE ARGS
# ============================
CLIENT_NAME=""
CLIENT_SLUG=""
CLIENT_DOMAIN=""
CLIENT_PHONE=""
CLIENT_EMAIL=""
BOT_NAME=""
BOT_DESCRIPTION=""
COLLECTION_NAME=""
LLM_KEY=""
LLM_URL=""
LLM_MODEL=""
WHATSAPP_MODE="fake"
META_PHONE_NUMBER_ID=""
ADMIN_KEY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --name) CLIENT_NAME="$2"; shift 2 ;;
        --slug) CLIENT_SLUG="$2"; shift 2 ;;
        --domain) CLIENT_DOMAIN="$2"; shift 2 ;;
        --phone) CLIENT_PHONE="$2"; shift 2 ;;
        --email) CLIENT_EMAIL="$2"; shift 2 ;;
        --bot-name) BOT_NAME="$2"; shift 2 ;;
        --description) BOT_DESCRIPTION="$2"; shift 2 ;;
        --collection) COLLECTION_NAME="$2"; shift 2 ;;
        --llm-key) LLM_KEY="$2"; shift 2 ;;
        --llm-url) LLM_URL="$2"; shift 2 ;;
        --llm-model) LLM_MODEL="$2"; shift 2 ;;
        --whatsapp-mode) WHATSAPP_MODE="$2"; shift 2 ;;
        --meta-phone-number-id) META_PHONE_NUMBER_ID="$2"; shift 2 ;;
        --admin-key) ADMIN_KEY="$2"; shift 2 ;;
        -h|--help) usage ;;
        *) error_exit "Parametro desconocido: $1" ;;
    esac
done

# ============================
# VALIDATE
# ============================
[[ -z "$CLIENT_NAME" ]] && error_exit "Falta --name"
[[ -z "$CLIENT_SLUG" ]] && error_exit "Falta --slug"
[[ -z "$CLIENT_DOMAIN" ]] && error_exit "Falta --domain"
[[ -z "$CLIENT_PHONE" ]] && error_exit "Falta --phone"

# Normalizar slug
CLIENT_SLUG=$(slugify "$CLIENT_SLUG")
[[ -z "$CLIENT_SLUG" ]] && error_exit "Slug invalido"

CLIENT_DIR="${CLIENTS_BASE_DIR}/cliente-${CLIENT_SLUG}"

# Verificar que no exista ya
[[ -d "$CLIENT_DIR" ]] && error_exit "El cliente '${CLIENT_SLUG}' ya existe en ${CLIENT_DIR}"

# Verificar que el dominio no este en Caddyfile
if [[ -f "$CADDYFILE" ]]; then
    if grep -q "${CLIENT_DOMAIN}" "$CADDYFILE"; then
        error_exit "El dominio '${CLIENT_DOMAIN}' ya existe en ${CADDYFILE}"
    fi
fi

# Verificar que la red Docker exista
if ! docker network inspect "$CADDY_NETWORK" >/dev/null 2>&1; then
    error_exit "La red Docker '${CADDY_NETWORK}' no existe. Asegurate de que aibrain este levantado."
fi

# Defaults
[[ -z "$BOT_NAME" ]] && BOT_NAME="Asistente Virtual de ${CLIENT_NAME}"
[[ -z "$BOT_DESCRIPTION" ]] && BOT_DESCRIPTION="Asistente automatizado por WhatsApp para ${CLIENT_NAME}"
[[ -z "$COLLECTION_NAME" ]] && COLLECTION_NAME="${CLIENT_SLUG}_docs"
[[ -z "$ADMIN_KEY" ]] && ADMIN_KEY=$(generate_key)

# ============================
# 1. Copiar template
# ============================
echo "[1/10] Creando cliente '${CLIENT_SLUG}' en ${CLIENT_DIR}..."
mkdir -p "$CLIENT_DIR"

# Copiar codigo base
cp -r "${TEMPLATE_DIR}/app" "$CLIENT_DIR/"
cp -r "${TEMPLATE_DIR}/ui" "$CLIENT_DIR/"
cp -r "${TEMPLATE_DIR}/scripts" "$CLIENT_DIR/"
cp "${TEMPLATE_DIR}/Dockerfile" "$CLIENT_DIR/"
cp "${TEMPLATE_DIR}/requirements.txt" "$CLIENT_DIR/"

# Generar docker-compose.yml desde template
sed -e "s/{{SLUG}}/${CLIENT_SLUG}/g" "${TEMPLATE_DIR}/docker-compose.template.yml" > "${CLIENT_DIR}/docker-compose.yml"

# ============================
# 2. Generar .env
# ============================
echo "[2/10] Generando .env..."

# Leer valores por defecto del template si no se pasaron
if [[ -f "${TEMPLATE_DIR}/.env" ]]; then
    TEMPLATE_ENV="${TEMPLATE_DIR}/.env"
elif [[ -f "${TEMPLATE_DIR}/.env.example" ]]; then
    TEMPLATE_ENV="${TEMPLATE_DIR}/.env.example"
else
    TEMPLATE_ENV=""
fi

function get_template_val() {
    local key="$1"
    if [[ -n "$TEMPLATE_ENV" ]]; then
        grep "^${key}=" "$TEMPLATE_ENV" | cut -d= -f2- | head -1 || true
    fi
}

[[ -z "$LLM_KEY" ]] && LLM_KEY=$(get_template_val "LLM_API_KEY")
[[ -z "$LLM_URL" ]] && LLM_URL=$(get_template_val "LLM_BASE_URL")
[[ -z "$LLM_MODEL" ]] && LLM_MODEL=$(get_template_val "LLM_MODEL")

cat > "${CLIENT_DIR}/.env" <<EOF
# Cliente: ${CLIENT_NAME} (${CLIENT_SLUG})
# Creado: $(date -Iseconds)

# LLM
LLM_API_KEY=${LLM_KEY}
LLM_BASE_URL=${LLM_URL}
LLM_MODEL=${LLM_MODEL}

# Branding
BOT_NAME=${BOT_NAME}
BOT_DESCRIPTION=${BOT_DESCRIPTION}
CONTACT_PHONE=${CLIENT_PHONE}
CONTACT_EMAIL=${CLIENT_EMAIL}
FALLBACK_MESSAGE=No encontré información sobre eso en mi base de conocimiento. Te sugiero contactar para más detalles.

# Base de datos / Vector Store
COLLECTION_NAME=${COLLECTION_NAME}

# WhatsApp
WHATSAPP_MODE=${WHATSAPP_MODE}
META_PHONE_NUMBER_ID=${META_PHONE_NUMBER_ID}
META_ACCESS_TOKEN=
META_WABA_ID=
META_APP_SECRET=
META_VERIFY_TOKEN=${CLIENT_SLUG}_webhook_verify_$(date +%s)
META_GRAPH_VERSION=v23.0
META_VALIDATE_SIGNATURE=false
PUBLIC_WEBHOOK_URL=https://${CLIENT_DOMAIN}

# Webhook
WEBHOOK_MODE=async

# Dominio
DOMAIN=${CLIENT_DOMAIN}

# API
ASK_API_KEY=$(generate_key)
ASK_RATE_LIMIT_REQUESTS=20
ASK_RATE_LIMIT_WINDOW_SECONDS=60

# Admin
ADMIN_API_KEY=${ADMIN_KEY}
HANDOFF_TRANSITION_MESSAGE=Estás siendo atendido por un asesor humano. En breve te responderá.

# Memoria
CONVERSATION_MEMORY_MAX_TURNS=20
CONVERSATION_ACTIVE_CONTEXT_TURNS=8
EOF

# ============================
# 3. Crear estructura de datos
# ============================
echo "[3/10] Creando estructura de datos..."
mkdir -p "${CLIENT_DIR}/data/docs"
mkdir -p "${CLIENT_DIR}/data/chroma"

# Crear prompt generico
cat > "${CLIENT_DIR}/data/system_prompt.txt" <<EOF
Sos el asistente virtual de ${CLIENT_NAME}.
Ayudás a responder consultas de clientes de manera clara y profesional.

Respondé usando ÚNICAMENTE la información proporcionada en el contexto.
Si no encontrás la respuesta en el contexto, decí claramente que no lo sabés.
Sé cercano, profesional y entusiasta. Respondé en español.
No inventes precios ni promesas que no estén en el contexto.
EOF

# Crear docs iniciales vacios con plantilla
for doc in home servicios precios faq horarios contacto proceso; do
    touch "${CLIENT_DIR}/data/docs/${doc}.md"
done

cat > "${CLIENT_DIR}/data/docs/home.md" <<EOF
# ${CLIENT_NAME}

Bienvenido al asistente virtual de ${CLIENT_NAME}.

## Sobre nosotros

(Editar este archivo con la informacion del negocio)

## Servicios principales

- Servicio 1
- Servicio 2
- Servicio 3

## Contacto

- WhatsApp: ${CLIENT_PHONE}
- Email: ${CLIENT_EMAIL}
EOF

# ============================
# 4. Agregar a Caddyfile
# ============================
echo "[4/10] Agregando bloque a Caddyfile..."
if [[ -f "$CADDYFILE" ]]; then
    cat >> "$CADDYFILE" <<EOF

# ${CLIENT_DOMAIN} (cliente-${CLIENT_SLUG})
${CLIENT_DOMAIN} {
    reverse_proxy ${CLIENT_SLUG}-web:8000
    log {
        output file /data/caddy/access-${CLIENT_SLUG}.log
    }
}
EOF
    echo "   [OK] Bloque agregado."
else
    echo "   [WARN] Caddyfile no encontrado en ${CADDYFILE}. Agregar manualmente:"
    cat <<EOF
${CLIENT_DOMAIN} {
    reverse_proxy ${CLIENT_SLUG}-web:8000
}
EOF
fi

# ============================
# 5. Construir y levantar
# ============================
echo "[5/10] Construyendo y levantando contenedores..."
cd "$CLIENT_DIR"
docker compose up -d --build

# ============================
# 6. Indexar documentos vacios
# ============================
echo "[6/10] Indexando documentos iniciales..."
docker compose exec -T web python scripts/index_documents.py || echo "   [WARN] Indexacion fallo (posiblemente sin documentos aun). Se reintentara al agregar docs."

# ============================
# 7. Recargar Caddy
# ============================
echo "[7/10] Recargando Caddy..."
cd /mnt/data/boston-ai && docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile 2>/dev/null || echo "   [WARN] No se pudo recargar Caddy automaticamente. Hacerlo manualmente."

# ============================
# 8. Resumen
# ============================
echo ""
echo "========================================"
echo "  CLIENTE CREADO EXITOSAMENTE"
echo "========================================"
echo ""
echo "  Slug:        ${CLIENT_SLUG}"
echo "  Nombre:      ${CLIENT_NAME}"
echo "  Dominio:     https://${CLIENT_DOMAIN}"
echo "  Directorio:  ${CLIENT_DIR}"
echo ""
echo "  Contenedores:"
echo "    - ${CLIENT_SLUG}-web"
echo "    - ${CLIENT_SLUG}-worker"
echo ""
echo "  URLs:"
echo "    Chat Web:    https://${CLIENT_DOMAIN}/chat"
echo "    Admin:       https://${CLIENT_DOMAIN}/admin"
echo "    Health:      https://${CLIENT_DOMAIN}/health"
echo "    Webhook:     https://${CLIENT_DOMAIN}/webhook"
echo ""
echo "  API Keys (guardar en lugar seguro):"
echo "    Admin Key:   ${ADMIN_KEY}"
echo "    Ask API Key: $(grep ASK_API_KEY "${CLIENT_DIR}/.env" | cut -d= -f2)"
echo ""
echo "  Proximos pasos:"
echo "    1. Editar documentos en ${CLIENT_DIR}/data/docs/"
echo "    2. Reindexar: docker compose -f ${CLIENT_DIR}/docker-compose.yml exec web python scripts/index_documents.py"
echo "    3. Configurar WhatsApp (si modo=meta) en Meta Developers"
echo "    4. Probar: curl https://${CLIENT_DOMAIN}/health"
echo ""
echo "========================================"
