# Troubleshooting - Errores Comunes

> Guia rapida para resolver problemas sin panico.

---

## Indice

- [Cliente no responde](#cliente-no-responde)
- [Caddy no sirve el dominio](#caddy-no-sirve-el-dominio)
- [WhatsApp no envia mensajes](#whatsapp-no-envia-mensajes)
- [Worker no procesa mensajes](#worker-no-procesa-mensajes)
- [Panel admin no carga](#panel-admin-no-carga)
- [Base de datos corrupta](#base-de-datos-corrupta)
- [ChromaDB no encuentra documentos](#chromadb-no-encuentra-documentos)
- [VPS sin espacio o RAM](#vps-sin-espacio-o-ram)

---

## Cliente no responde

### Sintoma
`curl https://dominio.com/health` devuelve error o timeout.

### Diagnostico

```bash
cd /mnt/data/cliente-{slug}

# 1. Ver si los contenedores corren
docker compose ps

# 2. Ver logs
docker compose logs --tail 50 web

# 3. Probar localmente dentro del contenedor
docker compose exec web python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"
```

### Soluciones

| Causa | Solucion |
|-------|----------|
| Contenedores detenidos | `docker compose up -d` |
| Error en `.env` (falta variable) | Revisar logs, completar `.env`, `docker compose restart` |
| Puerto en conflicto | Cambiar puerto en `docker-compose.yml` (raro con multi-cliente) |
| Caddy no redirige | Verificar que el dominio este en Caddyfile, recargar Caddy |

---

## Caddy no sirve el dominio

### Sintoma
El dominio da "404" o "502 Bad Gateway".

### Diagnostico

```bash
# Verificar que el bloque existe
cat /mnt/data/boston-ai/Caddyfile | grep -A 5 "dominio.com"

# Verificar que el contenedor esta en la red
docker network inspect boston-ai_default | grep "{slug}-web"

# Probar Caddy directamente
cd /mnt/data/boston-ai && docker compose exec caddy caddy list-modules
```

### Soluciones

```bash
# 1. Recargar Caddy
cd /mnt/data/boston-ai
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile

# 2. Si el bloque falta, agregar manualmente:
cat >> /mnt/data/boston-ai/Caddyfile <<EOF
dominio.com {
    reverse_proxy {slug}-web:8000
}
EOF
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile

# 3. Verificar DNS
nslookup dominio.com
```

---

## WhatsApp no envia mensajes

### Sintoma
El bot recibe mensajes pero no responde por WhatsApp.

### Diagnostico

```bash
# 1. Verificar modo WhatsApp
grep WHATSAPP_MODE /mnt/data/cliente-{slug}/.env

# 2. Si es modo fake: es normal, no envia mensajes reales
# 3. Si es modo meta: verificar credenciales
grep META /mnt/data/cliente-{slug}/.env

# 4. Ver logs de envio
docker compose logs --tail 50 web | grep -i "whatsapp\|send\|error"
```

### Soluciones

| Causa | Solucion |
|-------|----------|
| `WHATSAPP_MODE=fake` | Cambiar a `meta` en `.env` y reiniciar |
| Token caducado | Renovar `META_ACCESS_TOKEN` en Meta Developers |
| `META_PHONE_NUMBER_ID` vacio | Completar en `.env` |
| Webhook no registrado en Meta | Verificar en Meta Dashboard que la URL del webhook este configurada |
| Firma invalida | Si `META_VALIDATE_SIGNATURE=true`, asegurar que `META_APP_SECRET` sea correcto |

---

## Worker no procesa mensajes

### Sintoma
Los mensajes quedan en estado `pending` y no se responden.

### Diagnostico

```bash
cd /mnt/data/cliente-{slug}

# 1. Verificar que el worker corre
docker compose ps

# 2. Ver logs del worker
docker compose logs --tail 50 worker

# 3. Ver mensajes pendientes
docker compose exec web python -c "
from app.whatsapp_store import store
pending = store.get_pending_inbounds(10)
print(f'Pendientes: {len(pending)}')
for p in pending:
    print(f\"  {p['provider_message_id']}: {p['text'][:50]}...\")
"
```

### Soluciones

| Causa | Solucion |
|-------|----------|
| Worker detenido | `docker compose up -d worker` |
| Error en procesamiento | Revisar logs del worker, corregir error, reiniciar |
| `WEBHOOK_MODE=inline` | En modo inline no se usa worker (procesa el web directamente) |
| Base de datos bloqueada | `docker compose restart` |

---

## Panel admin no carga

### Sintoma
`https://dominio.com/admin` no carga o pide API key y no acepta.

### Diagnostico

```bash
# 1. Verificar que ADMIN_API_KEY esta configurada
grep ADMIN_API_KEY /mnt/data/cliente-{slug}/.env

# 2. Probar el endpoint directamente
curl -H "X-Admin-Key: TU_KEY" https://dominio.com/admin/conversations
```

### Soluciones

| Causa | Solucion |
|-------|----------|
| `ADMIN_API_KEY` vacio | Generar una key (`openssl rand -hex 24`) y agregarla al `.env` |
| Key incorrecta | Copiar la key exacta del `.env` |
| CORS / HTTPS | Asegurar que se accede por HTTPS, no HTTP |

---

## Base de datos corrupta

### Sintoma
Errores de SQLite, bot no inicia, datos perdidos.

### Solucion

```bash
cd /mnt/data/cliente-{slug}

# 1. Detener contenedores
docker compose down

# 2. Backup la DB actual (por las dudas)
cp data/app.sqlite3 data/app.sqlite3.corrupt.$(date +%s)

# 3. Intentar reparar
docker run --rm -v "$(pwd)/data:/data" keinos/sqlite3 sqlite3 /data/app.sqlite3 ".recover" | sqlite3 /data/app_recovered.sqlite3
mv data/app_recovered.sqlite3 data/app.sqlite3

# 4. Si no funciona, eliminar y recrear (se pierden datos)
rm data/app.sqlite3
# Al levantar, la app crea la DB automaticamente con las migraciones
docker compose up -d
```

---

## ChromaDB no encuentra documentos

### Sintoma
El bot responde "No encontre informacion" aunque los documentos existen.

### Diagnostico

```bash
cd /mnt/data/cliente-{slug}

# 1. Verificar que hay documentos
ls -la data/docs/

# 2. Verificar coleccion en ChromaDB
docker compose exec web python -c "
from app.vector_store import get_collection, get_client
from app.config import COLLECTION_NAME
print(f'Coleccion: {COLLECTION_NAME}')
col = get_collection()
print(f'Documentos: {col.count()}')
"
```

### Soluciones

```bash
# Reindexar documentos
docker compose exec web python scripts/index_documents.py

# Si la coleccion esta corrupta, limpiar y reindexar
docker compose exec web python -c "
from app.vector_store import clear_collection
from app.config import COLLECTION_NAME
clear_collection(COLLECTION_NAME)
"
docker compose exec web python scripts/index_documents.py
```

---

## VPS sin espacio o RAM

### Sintoma
El VPS va lento, contenedores se reinician, errores de "No space left".

### Diagnostico

```bash
# Disco
df -h /mnt/data

# RAM
free -m

# Docker usa mucho espacio?
docker system df
```

### Soluciones

```bash
# 1. Limpiar Docker
docker system prune -a -f
docker volume prune -f

# 2. Limpiar logs antiguos
find /mnt/data -name "*.log" -mtime +30 -delete

# 3. Eliminar backups viejos
find /mnt/backups -name "*.tar.gz" -mtime +60 -delete

# 4. Si sigue lleno: ampliar VPS o migrar clientes
# Ver docs/OPERADOR.md seccion "Escalar"
```

---

*Ultima actualizacion: 2026-05-28*
