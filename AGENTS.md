# AsistenteBot - Plataforma Multi-Cliente WhatsApp

> Plataforma de bots de WhatsApp basados en RAG para emprendedores y profesionales.
> Comparte VPS con Boston AI (aibrain) en el mismo servidor.
> Caddy maestro gestiona HTTPS para todos los bots.

---

## INSTRUCCION RAPIDA PARA EL AGENTE (OpenCode)

> **IMPORTANTE:** Si el usuario pregunta por "crear cliente", "nuevo cliente",
> "alta de cliente", "onboarding", "como agrego un bot", o cualquier tema
> relacionado con `new_client.sh`, **LEER INMEDIATAMENTE** `docs/CREAR_CLIENTE.md`
> y responder con los pasos rapidos de ese documento.
> No inventar pasos ni rutas. Usar SIEMPRE los datos de `docs/CREAR_CLIENTE.md`.

---

## Proposito

Plataforma de bots de WhatsApp basados en RAG. Cada cliente tiene su propia instancia aislada con documentos, prompt y numero de telefono propios. Atiende clientes 24/7, responde preguntas frecuentes y ayuda a cerrar ventas.

## Tech Stack

- Python 3.11 + FastAPI
- ChromaDB + sentence-transformers (embeddings)
- OpenAI-compatible LLM (OpenCode GO / Kimi)
- SQLite (WAL mode)
- Docker + Docker Compose
- Caddy (reverse proxy compartido con aibrain en VPS)
- Server-Sent Events (SSE) para panel admin en tiempo real

## Estructura

```
app/                # Codigo Python
  main.py           # FastAPI (endpoints, middleware, admin API)
  config.py         # Variables de entorno
  db.py             # SQLite connection
  db_migrations.py  # Schema migrations
  documents.py      # Carga docs markdown
  embedder.py       # Embeddings (sentence-transformers)
  llm_client.py     # Cliente LLM
  rag_service.py    # Pipeline RAG
  retriever.py      # Busqueda semantica
  vector_store.py   # ChromaDB wrapper
  whatsapp_*.py     # Integracion WhatsApp (Meta API)
  whatsapp_store.py # SQLite store para mensajes
  whatsapp_service.py # Logica de procesamiento + human handoff
  worker.py         # Background worker (procesa cola async)
  sse_manager.py    # Server-Sent Events para panel admin
  chat_local.py     # Chat por consola (testing)

data/docs/          # Base de conocimientos (markdown)
scripts/            # Utilitarios
  index_documents.py
  run_worker.py
  deploy.sh         # Deploy rapido (no toca aibrain)
  setup_vps.sh      # Setup inicial en VPS (UNA SOLA VEZ, se auto-elimina)
  check_vps.sh      # Health check de ambos bots
  start.ps1         # Levantar FastAPI (Windows local)
  stop.ps1          # Detener FastAPI (Windows local)
  status.ps1        # Ver estado (Windows local)
  run_chat.ps1      # Chat por consola (Windows local)
ui/                 # Chat web estatico
  index.html
  admin/
    index.html      # Panel de administracion (human handoff)
docs/
  VPS_DEPLOY.md     # Guia completa de deploy en VPS
```

## Running Local (Windows)

1. Activar entorno virtual:
   ```powershell
   .venv\Scripts\activate
   ```

2. Chat por consola:
   ```powershell
   .\run_chat.bat
   # o
   .\scripts\run_chat.ps1
   ```

3. Levantar FastAPI:
   ```powershell
   .\start.bat
   # o
   .\scripts\start.ps1
   ```

4. Ver estado:
   ```powershell
   .\scripts\status.ps1
   ```

5. Detener:
   ```powershell
   .\stop.bat
   # o
   .\scripts\stop.ps1
   ```

6. URLs locales:
   - Chat Web: http://127.0.0.1:8000/chat
   - Panel Admin: http://127.0.0.1:8000/admin
   - Health: http://127.0.0.1:8000/health
   - Webhook: http://127.0.0.1:8000/webhook

## Docker

```bash
docker compose up -d --build
```

## Deploy en VPS

> **IMPORTANTE:** El VPS actualmente no tiene `git` instalado por falta de espacio en disco.
> Los deploys se hacen manualmente con `scp` + `docker compose up -d --build`.

### Deploy manual (actual)

Desde tu PC local:

```bash
# Subir archivos modificados al VPS
scp -i ~/.ssh/boston_vps app/*.py .env root@167.114.96.29:/mnt/data/rodrigo-bot/app/
scp -i ~/.ssh/boston_vps -r ui/admin root@167.114.96.29:/mnt/data/rodrigo-bot/ui/

# Reconstruir contenedores en el VPS
ssh -i ~/.ssh/boston_vps root@167.114.96.29 "cd /mnt/data/rodrigo-bot && docker compose up -d --build"
```

> Este proceso **no modifica aibrain ni el Caddy maestro.**

### Setup inicial (UNA SOLA VEZ) - DEPRECADO

```bash
cd /mnt/data/rodrigo-bot
chmod +x scripts/setup_vps.sh
./scripts/setup_vps.sh
```

> **ADVERTENCIA:** Este script se auto-elimina al finalizar para evitar ejecuciones accidentales.
> Requiere `git` instalado en el VPS.

### Verificar estado de ambos bots

```bash
cd /mnt/data/rodrigo-bot
chmod +x scripts/check_vps.sh
./scripts/check_vps.sh
```

Ver guia completa en `docs/VPS_DEPLOY.md`.

Nota: Este bot comparte el Caddy reverse proxy con Boston Uniformes en el mismo VPS.
El Caddy maestro esta en `/mnt/data/boston-ai/` y sirve ambos dominios via Docker network compartida.

## Variables clave

- `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`
- `WHATSAPP_MODE` (fake | meta)
- `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`, `META_WABA_ID`, `META_APP_SECRET`, `META_VERIFY_TOKEN`
- `META_VALIDATE_SIGNATURE` (true para produccion)
- `DOMAIN=rodrigo.asistentebot.com.ar` (configurable por cliente)
- `WEBHOOK_MODE` (inline | async)
- `ADMIN_API_KEY` (para panel de administracion)
- `HANDOFF_TRANSITION_MESSAGE` (mensaje al pasar a humano)

## Panel de Administracion (Human Handoff)

URL: `https://rodrigo.asistentebot.com.ar/admin` (por cliente)

### Funcionalidades

- **Ver conversaciones en tiempo real** — lista de clientes, ultimo mensaje, estado
- **Tomar control humano** — el bot deja de responder automaticamente
- **Responder manualmente** — enviar mensajes como si fueras el bot
- **Liberar conversacion** — el bot vuelve a responder solo
- **Historial completo** — inbound y outbound en una sola vista
- **Notificaciones con sonido** — cuando llega mensaje nuevo (requiere interaccion con la pagina)

### Flujo de Human Handoff

1. Cliente manda mensaje → Bot responde automaticamente (badge "Bot")
2. Admin hace clic en "Tomar control" → Badge cambia a "Humano"
3. Cliente manda otro mensaje → Bot envia mensaje de transicion y se calla
4. Admin responde manualmente desde el panel
5. Admin hace clic en "Liberar" → Bot vuelve a responder solo

### API de Admin (endpoints protegidos con `X-Admin-Key`)

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `GET` | `/admin/events` | SSE — actualizaciones en tiempo real |
| `GET` | `/admin/conversations` | Lista de conversaciones |
| `GET` | `/admin/conversations/{phone}` | Historial completo |
| `POST` | `/admin/conversations/{phone}/claim` | Tomar control humano |
| `POST` | `/admin/conversations/{phone}/release` | Liberar al bot |
| `POST` | `/admin/conversations/{phone}/reply` | Enviar mensaje manual |

## Notas tecnicas

### Arquitectura de procesamiento

El bot usa **webhook async** para produccion:

1. Meta envia webhook al servidor
2. El servidor guarda el mensaje en SQLite como `pending`
3. Responde "OK" a Meta inmediatamente (evita timeouts)
4. El worker lee mensajes `pending` cada 2 segundos
5. El worker procesa con IA, envia respuesta por WhatsApp, marca como `done`
6. El panel admin se entera via SSE cuando llega mensaje nuevo

### Base de datos

Tablas principales:
- `inbound_messages` — mensajes recibidos de clientes
- `outbound_messages` — respuestas del bot o mensajes manuales
- `conversation_claims` — control de human handoff
- `message_status_events` — eventos de entrega de WhatsApp

### Problemas conocidos

- **Disco del VPS casi lleno** — no se puede instalar `git`, deploys manuales con `scp`
- **AudioContext bloqueado** — Chrome requiere interaccion del usuario antes de reproducir sonidos
- **Panel admin requiere F5** — para ver respuestas del bot despues de que el worker termina
  (el worker corre en un contenedor separado y no puede notificar al web directamente)

---

*Ultima actualizacion: 2026-05-27*