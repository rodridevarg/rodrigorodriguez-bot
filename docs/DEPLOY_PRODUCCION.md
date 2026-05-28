# Checklist de Deploy a Produccion

> Lista completa para dejar el sistema listo en el VPS.
> Despues de esto, lo unico que falta es crear clientes.

---

## Pre-requisitos

- [ ] Dominio `asistentebot.com.ar` comprado y delegado a Cloudflare
- [ ] DNS wildcard `*.asistentebot.com.ar` → IP del VPS (proxy GRIS)
- [ ] Acceso SSH al VPS
- [ ] Docker y Docker Compose instalados
- [ ] aibrain levantado (red `boston-ai_default` existe)
- [ ] Bot de Rodrigo funcionando (para migrarlo al router)

---

## Paso 1: Actualizar codigo en el VPS

```bash
cd /mnt/data/rodrigo-bot-template
git pull origin master
```

## Paso 2: Configurar webhook-router

```bash
cd /mnt/data/rodrigo-bot-template
./scripts/setup_router.sh
```

Este script:
1. Crea `/mnt/data/webhook-router/`
2. Copia codigo del router
3. Crea `.env` desde ejemplo
4. Agrega bloque al Caddyfile
5. Levanta contenedores
6. Recarga Caddy

## Paso 3: Configurar .env del router

```bash
nano /mnt/data/webhook-router/.env
```

Valores a completar:

```env
META_VERIFY_TOKEN=rodrigo_webhook_verify_2024
META_APP_SECRET=TU_APP_SECRET_DE_META
ADMIN_API_KEY=$(openssl rand -hex 24)
```

Reiniciar:
```bash
cd /mnt/data/webhook-router && docker compose restart
```

## Paso 4: Actualizar bot de Rodrigo

El bot de Rodrigo debe dejar de validar firmas (el router ya las valida):

```bash
nano /mnt/data/rodrigo-bot/.env
```

Agregar/modificar:
```env
META_VALIDATE_SIGNATURE=false
```

Reiniciar:
```bash
cd /mnt/data/rodrigo-bot && docker compose restart
```

## Paso 5: Configurar Meta Developers

1. Andá a tu App de Meta → Webhooks → WhatsApp
2. **URL de devolucion de llamada**: `https://asistentebot.com.ar/webhook`
3. **Token de verificacion**: el mismo que `META_VERIFY_TOKEN` del router
4. Guardar
5. Verificar (Meta envia una peticion de verificacion)

## Paso 6: Registrar bot existente (Rodrigo)

```bash
ROUTER_KEY=$(grep ADMIN_API_KEY /mnt/data/webhook-router/.env | cut -d= -f2 | tr -d '"')
PHONE_ID=$(grep META_PHONE_NUMBER_ID /mnt/data/rodrigo-bot/.env | cut -d= -f2 | tr -d '"')

curl -X POST http://127.0.0.1:8100/admin/register \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: ${ROUTER_KEY}" \
  -d "{\"phone_number_id\":\"${PHONE_ID}\",\"client_slug\":\"rodrigo\",\"target_url\":\"http://rodrigo-web:8000/webhook\"}"
```

## Paso 7: Verificar que todo funciona

```bash
# Router responde
curl https://asistentebot.com.ar/health

# Webhook existe (debe dar error de auth, no 404)
curl -v https://asistentebot.com.ar/webhook

# Ver rutas registradas
curl -H "X-Admin-Key: ${ROUTER_KEY}" http://127.0.0.1:8100/admin/routes

# Bot de Rodrigo sigue respondiendo por WhatsApp
```

---

## Despues de esto: crear clientes

### Paso unico por cliente

```bash
cd /mnt/data/rodrigo-bot-template

./scripts/new_client.sh \
  --name "Dr. Garcia" \
  --slug garcia \
  --domain "garcia.asistentebot.com.ar" \
  --phone "+54 11 1234-5678" \
  --email "contacto@drgarcia.com" \
  --meta-phone-number-id "ID_DEL_NUMERO_EN_META"
```

### Lo que hace el script automaticamente

- [x] Crea carpeta `/mnt/data/cliente-garcia/`
- [x] Genera `.env` con branding del cliente
- [x] Genera `docker-compose.yml` con nombres unicos
- [x] Crea documentos iniciales vacios
- [x] Agrega bloque al Caddyfile
- [x] Levanta contenedores
- [x] Registra en webhook-router
- [x] Recarga Caddy

### Lo que hay que hacer manualmente

1. **Agregar numero en Meta**
   - Meta Business Manager → tu WABA → Agregar numero
   - Verificar con SMS
   - Obtener `PHONE_NUMBER_ID`

2. **Subir documentos del cliente**
   ```bash
   scp ./docs_del_cliente/*.md root@vps:/mnt/data/cliente-garcia/data/docs/
   cd /mnt/data/cliente-garcia && docker compose exec web python scripts/index_documents.py
   ```

3. **Editar prompt si es necesario**
   ```bash
   nano /mnt/data/cliente-garcia/data/system_prompt.txt
   cd /mnt/data/cliente-garcia && docker compose restart
   ```

4. **Probar**
   ```bash
   curl -X POST https://garcia.asistentebot.com.ar/ask-public \
     -H "Content-Type: application/json" \
     -d '{"question": "Hola, que servicios ofrecen?"}'
   ```

---

*Ultima actualizacion: 2026-05-28*
