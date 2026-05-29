# Setup Unico - Plataforma Multi-Cliente

> Todo lo que hay que hacer **UNA SOLA VEZ** en el VPS para tener la plataforma lista.
> Despues de esto, solo se ejecuta `new_client.sh` por cada cliente.

---

## Pre-requisitos (ya listos)

- [x] VPS con Docker y Docker Compose
- [x] Dominio `asistentebot.com.ar` delegado a Cloudflare
- [x] DNS wildcard `*.asistentebot.com.ar` apuntando al VPS (proxy GRIS)
- [x] aibrain levantado (red `boston-ai_default` existe)
- [x] Bot de Rodrigo funcionando actualmente

---

## Paso 1: Clonar el codigo

```bash
cd /mnt/data
git clone https://github.com/rodridevarg/rodrigorodriguez-bot.git rodrigo-bot-template
cd rodrigo-bot-template
```

## Paso 2: Configurar webhook-router (una sola vez)

```bash
cd /mnt/data/rodrigo-bot-template
./scripts/setup_router.sh
```

Esto hace automaticamente:
- Crea `/mnt/data/webhook-router/`
- Copia codigo
- Agrega bloque al Caddyfile
- Levanta contenedor

## Paso 3: Configurar .env del router

```bash
nano /mnt/data/webhook-router/.env
```

Editar estos valores con los de tu App de Meta:

```env
# Mismos valores que tu App de Meta actual
META_VERIFY_TOKEN=rodrigo_webhook_verify_2024
META_APP_SECRET=TU_APP_SECRET_DE_META

# Nueva clave para administrar el router
ADMIN_API_KEY=$(openssl rand -hex 24)
```

Reiniciar (down+up para que lea el .env modificado):
```bash
cd /mnt/data/webhook-router && docker compose down && docker compose up -d
```

## Paso 4: Migrar bot de Rodrigo al router

El bot de Rodrigo estaba recibiendo webhooks directamente. Ahora el router los recibe y redirige.

```bash
# 1. Desactivar validacion de firma en la instancia de Rodrigo
# (el router ya valida)
nano /mnt/data/rodrigo-bot/.env
```

Agregar/modificar:
```env
META_VALIDATE_SIGNATURE=false
```

```bash
# 2. Reiniciar Rodrigo (down+up para leer .env modificado)
cd /mnt/data/rodrigo-bot && docker compose down && docker compose up -d

# 3. Registrar en el router
ROUTER_KEY=$(grep ADMIN_API_KEY /mnt/data/webhook-router/.env | cut -d= -f2 | tr -d '"')
PHONE_ID=$(grep META_PHONE_NUMBER_ID /mnt/data/rodrigo-bot/.env | cut -d= -f2 | tr -d '"')

curl -X POST http://127.0.0.1:8100/admin/register \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: ${ROUTER_KEY}" \
  -d "{\"phone_number_id\":\"${PHONE_ID}\",\"client_slug\":\"rodrigo\",\"target_url\":\"http://rodrigo-web:8000/webhook\"}"
```

## Paso 5: Actualizar Meta Developers

1. Andá a tu App de Meta → Webhooks → WhatsApp
2. **URL de devolucion de llamada**: `https://asistentebot.com.ar/webhook`
3. **Token de verificacion**: el mismo `META_VERIFY_TOKEN` del router
4. Guardar
5. Meta envia verificacion automaticamente

## Paso 6: Verificar que todo funciona

```bash
# Router responde
curl https://asistentebot.com.ar/health

# Webhook existe (debe dar 401/403, no 404)
curl -v https://asistentebot.com.ar/webhook

# Ver rutas registradas
curl -H "X-Admin-Key: ${ROUTER_KEY}" http://127.0.0.1:8100/admin/routes
```

---

## Resultado

Ahora tenes:
- ✅ Webhook Router levantado
- ✅ Bot de Rodrigo migrado (sigue funcionando igual)
- ✅ Meta enviando webhooks al router
- ✅ Plataforma lista para crear clientes

---

## Proximo paso

Ver `docs/NUEVO_CLIENTE.md` para crear el primer cliente.

---

*Ultima actualizacion: 2026-05-28*
