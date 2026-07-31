#!/bin/bash
set -euo pipefail

# =============================================================================
# new_client.sh - Crea un nuevo cliente en la plataforma AsistenteBot
# =============================================================================
#
# RESUMEN:
#   Este script automatiza la creacion de una instancia completa de bot
#   para un nuevo cliente. Genera contenedores Docker aislados, configura
#   el dominio, registra el webhook y deja todo listo para usar.
#
# =============================================================================
# REQUISITOS PREVIOS (tener listo ANTES de ejecutar):
# =============================================================================
#
# 1. Datos del negocio:
#    - Nombre comercial del cliente
#    - Slug corto (solo letras minusculas, numeros y guiones)
#    - Telefono de contacto del negocio
#    - Email de contacto (opcional pero recomendado)
#
# 2. Dominio:
#    - Elegir subdominio de asistentebot.com.ar
#    - Ejemplo: garcia.asistentebot.com.ar
#    - El DNS wildcard ya esta configurado en Cloudflare (no hay que tocar nada)
#
# 3. WhatsApp Business (si el cliente va a usar WhatsApp real):
#    - Obtener PHONE_NUMBER_ID desde Meta Developers
#    - El numero debe estar agregado a la WABA compartida
#    - El router central recibe los webhooks y los redirige
#
# 4. Infraestructura del VPS (debe estar levantada):
#    - Caddy maestro (boston-caddy) corriendo
#    - Webhook-router corriendo
#    - Red Docker boston-ai_default disponible
#    - Template en /mnt/data/rodrigo-bot-template/
#
# =============================================================================
# FLUJO DE USO (paso a paso):
# =============================================================================
#
# Paso 1: Conectarse al VPS
#   ssh -i ~/.ssh/boston_vps root@167.114.96.29
#   cd /mnt/data/rodrigo-bot-template
#
# Paso 2: Ejecutar este script con los datos del cliente
#   chmod +x scripts/new_client.sh
#   ./scripts/new_client.sh \
#     --name "Dr. Garcia" \
#     --slug garcia \
#     --domain "garcia.asistentebot.com.ar" \
#     --phone "+54 11 2345-6789" \
#     --email "contacto@garcia.com" \
#     --whatsapp-mode meta \
#     --meta-phone-number-id "123456789012345"
#
# Paso 3: El script hace TODO solo:
#   - Crea /mnt/data/cliente-garcia/
#   - Copia codigo del template
#   - Genera .env con valores del cliente
#   - Genera docker-compose.yml con nombres unicos
#   - Crea documentos iniciales (plantillas vacias)
#   - Agrega bloque al Caddyfile maestro
#   - Levanta contenedores (garcia-web, garcia-worker)
#   - Registra el numero en el webhook-router
#   - Recarga Caddy
#
# Paso 4: Proximos pasos manuales (el script te los muestra al final):
#   a) Editar documentos en /mnt/data/cliente-garcia/data/docs/
#   b) Reindexar: docker compose exec web python scripts/index_documents.py
#   c) Configurar webhook en Meta Developers (URL: https://asistentebot.com.ar/webhook)
#   d) Probar: curl https://garcia.asistentebot.com.ar/health
#
# =============================================================================
# NOTAS IMPORTANTES:
# =============================================================================
#
# - El template en /mnt/data/rodrigo-bot-template/ debe estar actualizado.
#   Si modificaste codigo localmente, subilo antes con scp.
#
# - Cada cliente consume aproximadamente 300MB de RAM.
#   Verificar recursos con: ./scripts/list_clients.sh
#
# - Si modificas .env despues de crear el cliente:
#   cd /mnt/data/cliente-SLUG && docker compose down && docker compose up -d
#   (docker compose restart NO lee cambios de .env)
#
# - Para eliminar un cliente: ./scripts/remove_client.sh --slug SLUG --yes
#
# =============================================================================

# ============================
# CONFIG
# ============================
TEMPLATE_DIR="/mnt/data/rodrigo-bot-template"  # ruta al codigo base (template maestro)
CLIENTS_BASE_DIR="/mnt/data"
CADDYFILE="/mnt/data/boston-ai/Caddyfile"
CADDY_NETWORK="boston-ai_default"

# ============================
# HELPERS
# ============================
function usage() {
    cat <<EOF
=============================================================================
  new_client.sh - Crea un nuevo cliente en AsistenteBot
=============================================================================

USO:
  $0 --name "Nombre" --slug <slug> --domain <dominio> --phone <tel> [opciones]

ARGUMENTOS OBLIGATORIOS:
  --name     Nombre comercial del cliente (ej: "Dr. Garcia")
  --slug     Identificador unico (ej: garcia, tienda-juan).
             Solo letras minusculas, numeros y guiones. No se puede repetir.
  --domain   Subdominio COMPLETO (ej: garcia.asistentebot.com.ar).
             El DNS wildcard *.asistentebot.com.ar ya apunta al VPS.
  --phone    Telefono de contacto del negocio (ej: +54 9 11 2345-6789)

ARGUMENTOS OPCIONALES:
  --email              Email de contacto del negocio
  --bot-name           Nombre del bot (default: "Asistente Virtual de <name>")
  --description        Descripcion del bot
  --collection         Nombre coleccion ChromaDB (default: <slug>_docs)
  --llm-key            API Key del LLM (default: la del template)
  --llm-url            URL base del LLM (default: la del template)
  --llm-model          Modelo del LLM (default: la del template)
  --whatsapp-mode      fake (simulacion) | meta (WhatsApp real). Default: fake
  --meta-phone-number-id  ID del numero en Meta Developers (obligatorio si modo=meta)
  --admin-key          API Key para panel admin (generada auto si no se pasa)

EJEMPLO COMPLETO (con WhatsApp real):
  $0 --name "Dr. Garcia" \
     --slug garcia \
     --domain "garcia.asistentebot.com.ar" \
     --phone "+54 11 2345-6789" \
     --email "contacto@garcia.com" \
     --whatsapp-mode meta \
     --meta-phone-number-id "123456789012345"

EJEMPLO MINIMO (modo fake, sin WhatsApp):
  $0 --name "Tienda Juan" --slug juan --domain "juan.asistentebot.com.ar" \
     --phone "+54 9 11 0000-0000"

REQUISITOS PREVIOS:
  1. Tener listo el PHONE_NUMBER_ID de Meta (si modo=meta)
  2. Elegir slug y dominio que no esten en uso
  3. Infraestructura VPS levantada (Caddy, router, red Docker)

=============================================================================
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

# Validar formato de slug
if [[ ! "$CLIENT_SLUG" =~ ^[a-z0-9-]+$ ]]; then
    error_exit "Slug invalido. Solo letras minusculas, numeros y guiones."
fi

# Validar dominio
if [[ ! "$CLIENT_DOMAIN" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$ ]]; then
    error_exit "Dominio invalido: '${CLIENT_DOMAIN}'"
fi

CLIENT_DIR="${CLIENTS_BASE_DIR}/cliente-${CLIENT_SLUG}"

# Verificar que no exista ya
[[ -d "$CLIENT_DIR" ]] && error_exit "El cliente '${CLIENT_SLUG}' ya existe en ${CLIENT_DIR}"

# Verificar que el dominio no este en Caddyfile
if [[ -f "$CADDYFILE" ]]; then
    if grep -Fq "${CLIENT_DOMAIN}" "$CADDYFILE"; then
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

# Inicializar variables Meta con valores vacios para evitar error con set -u
META_ACCESS_TOKEN="${META_ACCESS_TOKEN:-}"
META_WABA_ID="${META_WABA_ID:-}"
META_APP_SECRET="${META_APP_SECRET:-}"
META_VERIFY_TOKEN="${META_VERIFY_TOKEN:-}"

[[ -z "$LLM_KEY" ]] && LLM_KEY=$(get_template_val "LLM_API_KEY")
[[ -z "$LLM_URL" ]] && LLM_URL=$(get_template_val "LLM_BASE_URL")
[[ -z "$LLM_MODEL" ]] && LLM_MODEL=$(get_template_val "LLM_MODEL")

# Leer credenciales Meta del template (compartidas entre todos los clientes)
[[ -z "$META_ACCESS_TOKEN" ]] && META_ACCESS_TOKEN=$(get_template_val "META_ACCESS_TOKEN")
[[ -z "$META_WABA_ID" ]] && META_WABA_ID=$(get_template_val "META_WABA_ID")
[[ -z "$META_APP_SECRET" ]] && META_APP_SECRET=$(get_template_val "META_APP_SECRET")

cat > "${CLIENT_DIR}/.env" <<EOF
# Cliente: ${CLIENT_NAME} (${CLIENT_SLUG})
# Creado: $(date -Iseconds)

# LLM
LLM_API_KEY="${LLM_KEY}"
LLM_BASE_URL="${LLM_URL}"
LLM_MODEL="${LLM_MODEL}"

# Branding
BOT_NAME="${BOT_NAME}"
BOT_DESCRIPTION="${BOT_DESCRIPTION}"
CONTACT_PHONE="${CLIENT_PHONE}"
CONTACT_EMAIL="${CLIENT_EMAIL}"
FALLBACK_MESSAGE="No encontré información sobre eso en mi base de conocimiento. Te sugiero contactar para más detalles."

# Base de datos / Vector Store
COLLECTION_NAME="${COLLECTION_NAME}"

# WhatsApp
WHATSAPP_MODE="${WHATSAPP_MODE}"
META_PHONE_NUMBER_ID="${META_PHONE_NUMBER_ID}"
META_ACCESS_TOKEN="${META_ACCESS_TOKEN}"
META_WABA_ID="${META_WABA_ID}"
META_APP_SECRET="${META_APP_SECRET}"
# El router central valida las firmas de Meta, no la instancia individual
META_VERIFY_TOKEN="rodrigo_webhook_verify_2024"
META_GRAPH_VERSION=v23.0
META_VALIDATE_SIGNATURE=false
PUBLIC_WEBHOOK_URL="https://${CLIENT_DOMAIN}"

# Webhook
WEBHOOK_MODE=async

# Dominio
DOMAIN="${CLIENT_DOMAIN}"

# API
ASK_API_KEY="$(generate_key)"
ASK_RATE_LIMIT_REQUESTS=20
ASK_RATE_LIMIT_WINDOW_SECONDS=60

# Admin
ADMIN_API_KEY="${ADMIN_KEY}"
HANDOFF_TRANSITION_MESSAGE="Estás siendo atendido por un asesor humano. En breve te responderá."

# Memoria
CONVERSATION_MEMORY_MAX_TURNS=20
CONVERSATION_ACTIVE_CONTEXT_TURNS=8

# Google Calendar (vacío por defecto, se configura con setup_calendar.sh)
GOOGLE_CALENDAR_ID=""
GOOGLE_SERVICE_ACCOUNT_JSON=""

# Recordatorios (activable por admin)
REMINDERS_ENABLED=false
REMINDER_HOURS_BEFORE=24
REMINDER_CONFIRMATION_REQUIRED=true

# Dirección del negocio
BUSINESS_ADDRESS=""
BUSINESS_NAME="${CLIENT_NAME}"
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

# Crear configuración de servicios (template)
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

# Crear configuración de horarios (template)
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
# 4b. Validar credenciales Meta (si modo=meta)
# ============================
if [[ "$WHATSAPP_MODE" == "meta" ]]; then
    missing=()
    [[ -n "$META_PHONE_NUMBER_ID" ]] || missing+=("META_PHONE_NUMBER_ID")
    [[ -n "$META_ACCESS_TOKEN" ]] || missing+=("META_ACCESS_TOKEN")
    [[ -n "$META_VERIFY_TOKEN" ]] || missing+=("META_VERIFY_TOKEN")
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "[WARN] Faltan credenciales Meta: ${missing[*]}"
        echo "[WARN] El contenedor web puede fallar al iniciar."
        echo "[WARN] Verificar que el template .env tenga las credenciales completas."
    fi
fi

# ============================
# 5. Construir y levantar
# ============================
echo "[5/10] Construyendo y levantando contenedores..."
cd "$CLIENT_DIR"
docker compose up -d --build

# ============================
# 5b. Registrar en webhook-router
# ============================
echo "[5b/10] Registrando en webhook-router..."
ROUTER_URL="http://127.0.0.1:8100"
ROUTER_ADMIN_KEY=""
if [[ -f "/mnt/data/webhook-router/.env" ]]; then
    ROUTER_ADMIN_KEY=$(grep "^ADMIN_API_KEY=" /mnt/data/webhook-router/.env | cut -d= -f2- | tr -d '"' || true)
fi

if [[ -n "$ROUTER_ADMIN_KEY" && -n "$META_PHONE_NUMBER_ID" ]]; then
    if curl --fail --silent --show-error -X POST "${ROUTER_URL}/admin/register" \
        -H "Content-Type: application/json" \
        -H "X-Admin-Key: ${ROUTER_ADMIN_KEY}" \
        -d "{\"phone_number_id\":\"${META_PHONE_NUMBER_ID}\",\"client_slug\":\"${CLIENT_SLUG}\",\"target_url\":\"http://${CLIENT_SLUG}-web:8000/webhook\"}" >/dev/null; then
        echo "   [OK] Registrado en webhook-router."
    else
        echo "   [WARN] No se pudo registrar en webhook-router. Hacerlo manualmente:"
        echo "     curl -X POST ${ROUTER_URL}/admin/register -H 'X-Admin-Key: ...' -d '{...}'"
    fi
else
    echo "   [INFO] Router no configurado o sin PHONE_NUMBER_ID. Omitiendo registro."
fi

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
# 8. Resumen final y proximos pasos
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
echo "  Contenedores Docker:"
echo "    - ${CLIENT_SLUG}-web    (FastAPI + panel admin)"
echo "    - ${CLIENT_SLUG}-worker (procesa mensajes async)"
echo ""
echo "  URLs publicas:"
echo "    Chat Web:    https://${CLIENT_DOMAIN}/chat"
echo "    Admin:       https://${CLIENT_DOMAIN}/admin"
echo "    Health:      https://${CLIENT_DOMAIN}/health"
echo "    Webhook:     https://${CLIENT_DOMAIN}/webhook"
echo ""
echo "  API Keys (GUARDAR EN LUGAR SEGURO):"
echo "    Admin Key:   ${ADMIN_KEY}"
echo "    Ask API Key: $(grep ASK_API_KEY "${CLIENT_DIR}/.env" | cut -d= -f2)"
echo ""
echo "  NOTA IMPORTANTE:"
echo "    Si modificas .env despues de crear el cliente, usa:"
echo "      cd ${CLIENT_DIR} && docker compose down && docker compose up -d"
echo "    'docker compose restart' NO lee cambios de .env."
echo ""
echo "========================================"
echo "  CHECKLIST DE PROXIMOS PASOS MANUALES"
echo "========================================"
echo ""
echo "  [ ] 1. DOCUMENTOS DEL CLIENTE"
echo "      Editar archivos markdown en:"
echo "        ${CLIENT_DIR}/data/docs/"
echo "      Archivos sugeridos:"
echo "        - home.md        (presentacion del negocio)"
echo "        - servicios.md   (que ofrece)"
echo "        - precios.md     (tarifas)"
echo "        - faq.md         (preguntas frecuentes)"
echo "        - horarios.md    (horarios de atencion)"
echo "        - contacto.md    (como contactar)"
echo "      Luego reindexar:"
echo "        cd ${CLIENT_DIR} && docker compose exec web python scripts/index_documents.py"
echo ""
echo "  [ ] 2. CONFIGURAR GOOGLE CALENDAR (opcional)"
echo "      Si el cliente quiere agendar turnos automáticamente:"
echo "        ./scripts/setup_calendar.sh --slug ${CLIENT_SLUG}"
echo ""
echo "  [ ] 3. CONFIGURAR SERVICIOS Y HORARIOS"
echo "      Editar archivos JSON:"
echo "        ${CLIENT_DIR}/data/services.json"
echo "        ${CLIENT_DIR}/data/horarios.json"
echo ""
echo "  [ ] 4. PROMPT DEL SISTEMA"
echo "      Editar el tono y estilo del bot:"
echo "        ${CLIENT_DIR}/data/system_prompt.txt"
echo ""
if [[ "${WHATSAPP_MODE}" == "meta" && -n "${META_PHONE_NUMBER_ID}" ]]; then
  echo "  [ ] 5. WHATSAPP (Meta Developers)"
  echo "      a) Ir a Meta Developers > WhatsApp > Configuracion > Webhook"
  echo "      b) URL de devolucion de llamada:"
  echo "         https://asistentebot.com.ar/webhook"
  echo "      c) Token de verificacion: rodrigo_webhook_verify_2024"
  echo "      d) Click en 'Verificar y guardar'"
  echo "      e) En 'Gestionar suscripciones', activar:"
  echo "         - messages"
  echo "         - message_statuses"
  echo "      f) Completar en .env (si falta algo):"
  echo "         cd ${CLIENT_DIR} && nano .env"
  echo "         META_ACCESS_TOKEN=..."
  echo "         META_APP_SECRET=..."
  echo "         Luego: docker compose down && docker compose up -d"
  echo ""
else
  echo "  [ ] 5. WHATSAPP (omitiendo - modo ${WHATSAPP_MODE})"
  echo "      Si luego queres activar WhatsApp real:"
  echo "      - Editar .env: WHATSAPP_MODE=meta"
  echo "      - Agregar META_PHONE_NUMBER_ID"
  echo "      - Rehacer: docker compose down && docker compose up -d"
  echo ""
fi
echo "  [ ] 6. PROBAR"
echo "      Health check:"
echo "        curl https://${CLIENT_DOMAIN}/health"
echo "      Chat web:"
echo "        https://${CLIENT_DOMAIN}/chat"
echo "      Panel admin:"
echo "        https://${CLIENT_DOMAIN}/admin"
echo ""
echo "  [ ] 7. ENTREGAR AL CLIENTE"
echo "      - URL del chat web"
echo "      - URL del panel admin"
echo "      - Admin API Key (para acceder al panel)"
echo "      - Instrucciones de uso (ver docs/ONBOARDING_CLIENTE.md)"
echo ""
echo "========================================"
echo "  COMANDOS UTILES PARA ESTE CLIENTE"
echo "========================================"
echo ""
echo "  Ver logs:"
echo "    cd ${CLIENT_DIR} && docker compose logs -f"
echo ""
echo "  Reiniciar (si se modifica .env):"
echo "    cd ${CLIENT_DIR} && docker compose down && docker compose up -d"
echo ""
echo "  Ver estado:"
echo "    ./scripts/list_clients.sh"
echo ""
echo "  Eliminar cliente (CUIDADO):"
echo "    ./scripts/remove_client.sh --slug ${CLIENT_SLUG} --yes"
echo ""
echo "========================================"
