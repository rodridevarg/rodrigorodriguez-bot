#!/bin/bash
set -euo pipefail

# =============================================================================
# deploy_content.sh - Sube documentos y contenido al VPS para un cliente
# =============================================================================
#
# USO:
#   ./scripts/deploy_content.sh --slug <slug> --docs-dir <dir> [opciones]
#
# ARGUMENTOS OBLIGATORIOS:
#   --slug       Slug del cliente (ej: nspa, garcia)
#   --docs-dir   Directorio local con los archivos .md (home.md, servicios.md, etc.)
#
# ARGUMENTOS OPCIONALES:
#   --prompt-file   Archivo system_prompt.txt personalizado
#   --app-dir       Directorio con codigo Python a actualizar (opcional)
#   --reindex       Reindexar documentos despues de subir (default: true)
#   --restart       Reiniciar contenedores si se sube codigo (default: false)
#
# EJEMPLOS:
#   # Subir solo documentos y reindexar
#   ./scripts/deploy_content.sh --slug nspa --docs-dir ./docs-nspa
#
#   # Subir documentos + prompt personalizado
#   ./scripts/deploy_content.sh --slug nspa --docs-dir ./docs-nspa --prompt-file ./prompt-nspa.txt
#
#   # Subir documentos + codigo + reiniciar
#   ./scripts/deploy_content.sh --slug nspa --docs-dir ./docs-nspa --app-dir ./app-nspa --restart
#
# =============================================================================

VPS_HOST="root@167.114.96.29"
CLIENTS_BASE="/mnt/data"

function usage() {
    cat <<EOF
Uso: $0 --slug <slug> --docs-dir <dir> [opciones]

Obligatorios:
  --slug        Slug del cliente
  --docs-dir    Directorio con archivos .md

Opcionales:
  --prompt-file   system_prompt.txt personalizado
  --app-dir       Directorio con codigo Python a actualizar
  --no-reindex    No reindexar despues de subir
  --restart       Reiniciar contenedores si se sube codigo

Ejemplo:
  $0 --slug nspa --docs-dir ./docs-nspa
EOF
    exit 1
}

function error_exit() {
    echo "[ERROR] $1" >&2
    exit 1
}

SLUG=""
DOCS_DIR=""
PROMPT_FILE=""
APP_DIR=""
REINDEX=true
RESTART=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --slug) SLUG="$2"; shift 2 ;;
        --docs-dir) DOCS_DIR="$2"; shift 2 ;;
        --prompt-file) PROMPT_FILE="$2"; shift 2 ;;
        --app-dir) APP_DIR="$2"; shift 2 ;;
        --no-reindex) REINDEX=false; shift ;;
        --restart) RESTART=true; shift ;;
        -h|--help) usage ;;
        *) error_exit "Parametro desconocido: $1" ;;
    esac
done

[[ -z "$SLUG" ]] && error_exit "Falta --slug"
[[ "$SLUG" =~ ^[a-z0-9-]+$ ]] || error_exit "Slug invalido. Solo letras minusculas, numeros y guiones."
[[ -z "$DOCS_DIR" ]] && error_exit "Falta --docs-dir"
[[ -d "$DOCS_DIR" ]] || error_exit "Directorio no encontrado: $DOCS_DIR"

CLIENT_DIR="${CLIENTS_BASE}/cliente-${SLUG}"

echo "========================================"
echo "  Deploy de contenido para: ${SLUG}"
echo "========================================"
echo ""

# 1. Validar y subir documentos
echo "[1/4] Subiendo documentos..."
shopt -s nullglob
files=("${DOCS_DIR}"/*.md)
[[ ${#files[@]} -gt 0 ]] || error_exit "No hay archivos .md en ${DOCS_DIR}"
scp -r "${DOCS_DIR}"/* "${VPS_HOST}:${CLIENT_DIR}/data/docs/"
echo "   [OK] Documentos subidos (${#files[@]} archivos .md)"

# 2. Subir prompt si se especifico
if [[ -n "$PROMPT_FILE" ]]; then
    echo "[2/4] Subiendo system_prompt.txt..."
    if [[ -f "$PROMPT_FILE" ]]; then
        scp "$PROMPT_FILE" "${VPS_HOST}:${CLIENT_DIR}/data/system_prompt.txt"
        echo "   [OK] Prompt actualizado"
    else
        echo "   [WARN] Archivo no encontrado: $PROMPT_FILE"
    fi
else
    echo "[2/4] Saltando prompt (no se especifico --prompt-file)"
fi

# 3. Copiar al contenedor Docker
echo "[3/4] Copiando a contenedores Docker..."
ssh "${VPS_HOST}" "docker cp ${CLIENT_DIR}/data/docs/. ${SLUG}-web:/app/data/docs/ && docker cp ${CLIENT_DIR}/data/docs/. ${SLUG}-worker:/app/data/docs/"

if [[ -n "$PROMPT_FILE" ]]; then
    ssh "${VPS_HOST}" "docker cp ${CLIENT_DIR}/data/system_prompt.txt ${SLUG}-web:/app/data/system_prompt.txt && docker cp ${CLIENT_DIR}/data/system_prompt.txt ${SLUG}-worker:/app/data/system_prompt.txt"
fi

# 4. Subir codigo si se especifico
if [[ -n "$APP_DIR" ]]; then
    echo "[3b/4] Subiendo codigo Python..."
    if [[ -d "$APP_DIR" ]]; then
        scp -r "${APP_DIR}"/* "${VPS_HOST}:${CLIENT_DIR}/app/"
        echo "   [OK] Codigo subido"
        
        if [[ "$RESTART" == true ]]; then
            echo "[3c/4] Reiniciando contenedores con rebuild..."
            ssh "${VPS_HOST}" "cd ${CLIENT_DIR} && docker compose down && docker compose up -d --build"
            echo "   [OK] Contenedores reiniciados con codigo actualizado"
        fi
    else
        echo "   [WARN] Directorio no encontrado: $APP_DIR"
    fi
fi

# 5. Reindexar
echo "[4/4] Reindexando documentos..."
if [[ "$REINDEX" == true ]]; then
    ssh "${VPS_HOST}" "docker exec ${SLUG}-web python scripts/index_documents.py"
    echo "   [OK] Reindexacion completa"
else
    echo "   [SKIP] --no-reindex especificado"
fi

echo ""
echo "========================================"
echo "  DEPLOY COMPLETADO"
echo "========================================"
echo ""
echo "  Cliente: ${SLUG}"
echo "  Documentos: ${DOCS_DIR}"
[[ -n "$PROMPT_FILE" ]] && echo "  Prompt: ${PROMPT_FILE}"
[[ -n "$APP_DIR" ]] && echo "  Codigo: ${APP_DIR}"
echo ""
echo "  Proximos pasos:"
echo "    - Verificar: curl https://${SLUG}.asistentebot.com.ar/health"
echo "    - Probar chat: https://${SLUG}.asistentebot.com.ar/chat"
echo ""
