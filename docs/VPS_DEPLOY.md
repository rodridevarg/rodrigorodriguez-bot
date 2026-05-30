# Guia de Deploy en VPS - AsistenteBot Multi-Cliente

> Plataforma de bots de WhatsApp basados en RAG.
> Comparte VPS con Boston AI (aibrain). Caddy maestro gestiona HTTPS para todos los bots.

---

## Requisitos

- VPS ya configurado (compartido con aibrain)
- IP: `167.114.96.29`
- Docker y Docker Compose instalados
- Dominio `*.asistentebot.com.ar` apuntando al VPS (DNS wildcard, proxy gris)

---

## Estructura en el VPS

```
/mnt/data/
├── boston-ai/          # Proyecto aibrain (ya existe)
│   ├── docker-compose.yml
│   ├── Caddyfile       # Caddy maestro (servira ambos bots)
│   └── ...
├── rodrigo-bot/        # Este proyecto (nuevo)
│   ├── docker-compose.yml
│   ├── .env
│   ├── Dockerfile
│   ├── app/
│   ├── scripts/
│   │   ├── setup_vps.sh   # Setup inicial (UNA SOLA VEZ)
│   │   ├── deploy.sh      # Deploys posteriores
│   │   └── check_vps.sh   # Health check
│   ├── data/
│   └── docs/
└── docker/             # Docker data root
```

---

## Paso 1: Clonar el proyecto

```bash
cd /mnt/data
git clone <tu-repo> rodrigo-bot
cd rodrigo-bot
```

---

## Paso 2: Configurar variables de entorno

```bash
cp .env.example .env
nano .env
```

Editar estos valores criticos:

```env
# LLM
LLM_API_KEY=sk-...
LLM_BASE_URL=https://opencode.ai/zen/go/v1
LLM_MODEL=kimi-k2.6

# WhatsApp (modo real para produccion)
WHATSAPP_MODE=meta
META_ACCESS_TOKEN=EAAX... (token temporal de Meta)
META_PHONE_NUMBER_ID=... (ID del numero de prueba)
META_WABA_ID=...
META_APP_SECRET=tu_app_secret
META_VERIFY_TOKEN=rodrigo_webhook_verify_2024
META_GRAPH_VERSION=v23.0
META_VALIDATE_SIGNATURE=true
PUBLIC_WEBHOOK_URL=https://rodrigo.asistentebot.com.ar

# Webhook (async recomendado para produccion)
WEBHOOK_MODE=async

# Dominio
DOMAIN=rodrigo.asistentebot.com.ar

# API REST
ASK_API_KEY=tu_clave_secreta_para_api
ASK_RATE_LIMIT_REQUESTS=20
ASK_RATE_LIMIT_WINDOW_SECONDS=60

# Memoria
CONVERSATION_MEMORY_MAX_TURNS=20
CONVERSATION_ACTIVE_CONTEXT_TURNS=8
```

---

## Paso 3: Setup inicial (UNA SOLA VEZ)

```bash
cd /mnt/data/rodrigo-bot
chmod +x scripts/setup_vps.sh
./scripts/setup_vps.sh
```

Este script:
1. Verifica que aibrain este funcionando
2. Clona el repo (si no existe)
3. Configura `.env`
4. Verifica DNS
5. Agrega bloque de rodrigo al Caddyfile de aibrain
6. Levanta rodrigo-bot conectado a la red compartida
7. **Se auto-elimina** para evitar ejecuciones accidentales

> **ADVERTENCIA:** Este script se ejecuta UNA SOLA VEZ. Se auto-elimina al finalizar.

---

## Paso 4: Deploys posteriores

Para actualizaciones futuras (git pull + rebuild):

```bash
cd /mnt/data/rodrigo-bot
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

Este script solo toca rodrigo-bot. **No modifica aibrain ni el Caddy maestro.**

---

## Paso 5: Verificar funcionamiento

```bash
# Health check
curl https://rodrigo.asistentebot.com.ar/health

# Probar chat via API
curl -X POST https://rodrigo.asistentebot.com.ar/ask-public \
  -H "Content-Type: application/json" \
  -d '{"question": "Que es la Secretaria Virtual?"}'

# Ver logs del worker
docker compose logs -f worker
```

---

## Comandos utiles

```bash
# Ver estado de ambos bots
./scripts/check_vps.sh

# Ver logs en tiempo real
docker compose logs -f

# Reiniciar servicios (down+up para leer .env modificado)
docker compose down && docker compose up -d

# Entrar al contenedor web
docker compose exec web bash

# Backup de la base de datos
docker compose exec web cat /app/data/app.sqlite3 > backup_$(date +%Y%m%d).sqlite3

# Ver estado de la red compartida
docker network inspect boston-ai_default
```

---

## Troubleshooting

### Caddy no responde para rodrigo-bot
- Verificar que el bloque de rodrigo este en el Caddyfile de aibrain:
  ```bash
  cat /mnt/data/boston-ai/Caddyfile | grep -A 20 "rodrigorodriguez"
  ```
- Verificar que la red `boston-ai_default` existe:
  ```bash
  docker network ls | grep boston
  ```
- Verificar que rodrigo-web esta en la red:
  ```bash
  docker network inspect boston-ai_default
  ```
- Reiniciar Caddy:
  ```bash
  cd /mnt/data/boston-ai && docker compose restart caddy
  ```

### Puerto 8001 ya esta en uso
- Verificar si otro proceso usa el puerto:
  ```bash
  ss -tlnp | grep 8001
  ```
- Si es otro proceso, cambiar el puerto en docker-compose.yml de rodrigo-bot

### Bot no responde en WhatsApp
- Verificar `WHATSAPP_MODE=meta`
- Verificar token de Meta no caducado
- Verificar webhook URL en Meta Dashboard:
  `https://asistentebot.com.ar/webhook` (ruta central del webhook-router)
- Ver logs:
  ```bash
  docker compose logs web
  ```

### Worker no procesa mensajes
- Verificar que `WEBHOOK_MODE=async`
- Ver logs:
  ```bash
  docker compose logs worker
  ```
- Verificar mensajes pendientes:
  ```bash
  docker compose exec web python -c "from app.whatsapp_store import store; print(store.get_pending_inbounds(10))"
  ```

---

## Estructura de red Docker

```
boston-ai_default (bridge network)
|
+-- boston-caddy (172.18.0.3)
|   Puertos: 80, 443 (del host)
|   Reverse proxy -> boston-web:8000 (bot.bostonuniformes.com.ar)
|   Reverse proxy -> rodrigo-web:8000 (rodrigo.asistentebot.com.ar)
|
+-- boston-web (172.18.0.2)
|   Puerto interno: 8000
|   Puerto host: 127.0.0.1:8000
|
+-- boston-worker
|
+-- rodrigo-web (nuevo)
|   Puerto interno: 8000
|   Puerto host: 127.0.0.1:8001
|
+-- rodrigo-worker (nuevo)
```

---

## Escalabilidad y Multi-Cliente

### Capacidad por VPS

Cada instancia del bot consume aproximadamente:
- **RAM**: ~300MB (web + worker + SQLite + ChromaDB)
- **Disco**: ~500MB base + documentos + embeddings

| VPS (ejemplo) | RAM | Clientes estimados |
|---------------|-----|-------------------|
| 2 vCPU / 4GB RAM | ~3GB disponible | ~8-10 clientes |
| 4 vCPU / 8GB RAM | ~7GB disponible | ~18-20 clientes |

### Plan de escalado

1. **Monitoreo**: ejecutar `./scripts/check_vps.sh` semanalmente.
2. **Umbrales de alerta**:
   - Disco > 80% → limpiar logs o migrar clientes
   - RAM disponible < 500MB → ampliar VPS o migrar clientes
3. **Migrar un cliente a otro VPS**:
   - Copiar carpeta `cliente-{slug}/` al nuevo VPS
   - Actualizar DNS del subdominio
   - Levantar con `docker compose up -d`
   - Eliminar del VPS anterior

### Agregar un nuevo cliente (multi-cliente)

Ver `docs/PLAN_MULTI_CLIENTE.md` para el proceso completo.

Resumen rápido:
1. Elegir subdominio: `{slug}.asistentebot.com.ar`
2. Crear carpeta `/mnt/data/cliente-{slug}/`
3. Copiar template (app/, ui/, docker-compose.yml)
4. Generar `.env` con `BOT_NAME`, `COLLECTION_NAME`, `CONTACT_PHONE`, etc.
5. Agregar bloque al Caddyfile de aibrain
6. Levantar contenedores

---

## Checklist post-deploy

- [ ] Registro A de `bot` en Cloudflare apunta a `167.114.96.29`
- [ ] `.env` configurado con credenciales reales
- [ ] `setup_vps.sh` ejecutado (una sola vez)
- [ ] `scripts/setup_vps.sh` se auto-elimino correctamente
- [ ] Bloque de rodrigo agregado al Caddyfile de aibrain
- [ ] Contenedores `rodrigo-web` y `rodrigo-worker` corriendo
- [ ] Health check responde en `https://rodrigo.asistentebot.com.ar/health`
- [ ] Chat web carga en `https://rodrigo.asistentebot.com.ar/chat`

---

*Ultima actualizacion: 2026-05-28*
