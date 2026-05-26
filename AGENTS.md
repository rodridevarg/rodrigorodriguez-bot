# Rodrigo Rodriguez Bot - Secretaria Virtual

> Bot de WhatsApp basado en RAG para emprendedores y profesionales.
> Comparte VPS con Boston AI (aibrain) en el mismo servidor.
> Caddy maestro gestiona HTTPS para ambos bots.

---

## Proposito

Bot de WhatsApp basado en RAG que responde consultas sobre la Secretaria Virtual de Rodrigo Rodriguez. Atiende clientes 24/7, responde preguntas frecuentes y ayuda a cerrar ventas.

## Tech Stack

- Python 3.11 + FastAPI
- ChromaDB + sentence-transformers (embeddings)
- OpenAI-compatible LLM (OpenCode GO / Kimi)
- SQLite (WAL mode)
- Docker + Docker Compose
- Caddy (reverse proxy compartido con aibrain en VPS)

## Estructura

```
app/                # Codigo Python
  main.py           # FastAPI (endpoints, middleware)
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
  worker.py         # Background worker
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
   - Health: http://127.0.0.1:8000/health
   - Webhook: http://127.0.0.1:8000/webhook

## Docker

```bash
docker compose up -d --build
```

## Deploy en VPS

### Setup inicial (UNA SOLA VEZ)

```bash
cd /mnt/data/rodrigo-bot
chmod +x scripts/setup_vps.sh
./scripts/setup_vps.sh
```

> **ADVERTENCIA:** Este script se auto-elimina al finalizar para evitar ejecuciones accidentales.

### Deploys posteriores (solo toca rodrigo-bot)

```bash
cd /mnt/data/rodrigo-bot
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

> Este script **no modifica aibrain ni el Caddy maestro.**

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
- `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`, `META_VERIFY_TOKEN`
- `DOMAIN=bot.rodrigorodriguez.com.ar`
- `WEBHOOK_MODE` (inline | async)
