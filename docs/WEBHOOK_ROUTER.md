# Webhook Router - Guia de Configuracion

> El webhook router recibe TODOS los webhooks de Meta (WhatsApp) y los redirige a la instancia correcta segun el numero de telefono.

---

## Arquitectura

```
Meta
  │
  ▼
asistentebot.com.ar/webhook  ← Caddy
  │
  ▼
webhook-router:8100
  │
  ├── Lee phone_number_id del JSON
  ├── Busca en SQLite: phone_number_id → "garcia"
  │
  ▼
POST http://garcia-web:8000/webhook
  │
  ▼
garcia-web procesa con sus propios documentos
```

---

## Setup inicial (una sola vez en el VPS)

```bash
cd /mnt/data/rodrigo-bot-template
./scripts/setup_router.sh
```

Esto crea `/mnt/data/webhook-router/` y levanta el contenedor.

## Configurar .env del router

```bash
nano /mnt/data/webhook-router/.env
```

Valores criticos:

```env
# Mismos valores que tu App de Meta
META_VERIFY_TOKEN=rodrigo_webhook_verify_2024
META_APP_SECRET=tu_app_secret_de_meta

# Clave para admin (registrar/desregistrar clientes)
ADMIN_API_KEY=$(openssl rand -hex 24)
```

Reiniciar despues de editar:
```bash
cd /mnt/data/webhook-router && docker compose restart
```

## Configurar Meta Developers

1. Andá a tu App de Meta → Webhooks → WhatsApp
2. **URL de devolucion de llamada**: `https://asistentebot.com.ar/webhook`
3. **Token de verificacion**: el mismo que `META_VERIFY_TOKEN` del router
4. Guardar

## Registrar el bot existente (Rodrigo)

```bash
ROUTER_KEY=$(grep ADMIN_API_KEY /mnt/data/webhook-router/.env | cut -d= -f2 | tr -d '"')
PHONE_ID=$(grep META_PHONE_NUMBER_ID /mnt/data/rodrigo-bot/.env | cut -d= -f2 | tr -d '"')

curl -X POST http://webhook-router:8100/admin/register \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: ${ROUTER_KEY}" \
  -d "{\"phone_number_id\":\"${PHONE_ID}\",\"client_slug\":\"rodrigo\",\"target_url\":\"http://rodrigo-web:8000/webhook\"}"
```

## Registrar un cliente nuevo

Al crear cliente con `new_client.sh`, se registra automaticamente si:
- El router esta levantado
- Se paso `--meta-phone-number-id`
- El `.env` del router existe

Para verificar:
```bash
curl -H "X-Admin-Key: ${ROUTER_KEY}" http://webhook-router:8100/admin/routes
```

## Desregistrar un cliente

Al eliminar con `remove_client.sh`, se desregistra automaticamente.

Manualmente:
```bash
curl -X POST http://webhook-router:8100/admin/unregister \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: ${ROUTER_KEY}" \
  -d '{"phone_number_id":"PHONE_NUMBER_ID_AQUI"}'
```

---

## Troubleshooting

### "no_route_found" en logs del router

El numero de telefono no esta registrado. Verificar:
```bash
curl -H "X-Admin-Key: ${ROUTER_KEY}" http://webhook-router:8100/admin/routes
```

### Meta dice "Webhook no verificado"

1. Verificar que `META_VERIFY_TOKEN` en router coincida con Meta
2. Verificar que Caddy redirige `asistentebot.com.ar/webhook` al router
3. Verificar que el router esta levantado: `docker ps | grep webhook-router`

### Instancia no recibe mensajes

1. Verificar que `META_VALIDATE_SIGNATURE=false` en el `.env` del cliente
2. Verificar que la red Docker `boston-ai_default` conecta router con la instancia
3. Verificar logs: `docker compose logs web` en el directorio del cliente

---

*Ultima actualizacion: 2026-05-28*
