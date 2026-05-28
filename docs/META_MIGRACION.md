# Migracion de Meta Apps - Rodrigo y Boston

> Guia paso a paso para cambiar las URLs de webhook en las Apps de Meta.
> Despues de esto, ambos bots recibiran webhooks a traves de asistentebot.com.ar

---

## Resumen del cambio

| Bot | URL anterior | URL nueva |
|-----|-------------|-----------|
| **Rodrigo** | `https://bot.rodrigorodriguez.com.ar/webhook` | `https://asistentebot.com.ar/webhook` |
| **Boston** | `https://bot.bostonuniformes.com.ar/webhook` | `https://asistentebot.com.ar/webhook` |

**Importante**: Ambos bots ahora usan **la misma URL** de webhook. El router decide a donde va cada mensaje segun el numero de telefono.

---

## Paso 1: App de Rodrigo

1. Andá a **Meta Developers** (developers.facebook.com)
2. Seleccioná la App de **Rodrigo Rodriguez**
3. Del menu lateral: **WhatsApp → Configuracion**
4. Buscá la seccion **Webhooks**
5. Click en **Editar** al lado de la URL de devolucion de llamada
6. Reemplazá la URL:
   ```
   URL anterior: https://bot.rodrigorodriguez.com.ar/webhook
   URL nueva:    https://asistentebot.com.ar/webhook
   ```
7. **Token de verificacion**: `rodrigo_webhook_verify_2024` (NO cambiar)
8. Click en **Verificar y guardar**
9. Meta enviara una peticion de verificacion automaticamente

---

## Paso 2: App de Boston

1. Andá a **Meta Developers** (developers.facebook.com)
2. Seleccioná la App de **Boston Uniformes** (o el nombre que tenga)
3. Del menu lateral: **WhatsApp → Configuracion**
4. Buscá la seccion **Webhooks**
5. Click en **Editar** al lado de la URL de devolucion de llamada
6. Reemplazá la URL:
   ```
   URL anterior: https://bot.bostonuniformes.com.ar/webhook
   URL nueva:    https://asistentebot.com.ar/webhook
   ```
7. **Token de verificacion**: `boston_webhook_verify_2024` (NO cambiar)
8. Click en **Verificar y guardar**
9. Meta enviara una peticion de verificacion automaticamente

---

## Paso 3: Verificar que funciona

Esperá 1-2 minutos despues de guardar, y probá desde tu celular:

### Probar Rodrigo
1. Escribile un mensaje de prueba al numero de Rodrigo (+54 9 2477 614405)
2. El bot deberia responder normalmente
3. Si no responde, revisá los logs del router:
   ```bash
   cd /mnt/data/webhook-router && docker compose logs -f
   ```

### Probar Boston
1. Escribile un mensaje de prueba al numero de Boston
2. El bot deberia responder normalmente
3. Revisá logs si hay problemas:
   ```bash
   cd /mnt/data/boston-ai && docker compose logs -f
   ```

---

## Solucion de problemas

### "URL de devolucion de llamada no verificada" en Meta

1. Verificar que el router esta levantado:
   ```bash
   curl https://asistentebot.com.ar/webhook
   # Debe devolver algo (401/403/400), no 404 ni timeout
   ```

2. Verificar que el token coincide:
   ```bash
   cat /mnt/data/webhook-router/.env | grep META_VERIFY_TOKEN
   ```

3. Si falla, reiniciar Caddy:
   ```bash
   cd /mnt/data/boston-ai && docker compose restart caddy
   ```

### Un bot responde y el otro no

1. Verificar rutas del router:
   ```bash
   ROUTER_KEY=$(grep ADMIN_API_KEY /mnt/data/webhook-router/.env | cut -d= -f2)
   curl -H "X-Admin-Key: $ROUTER_KEY" http://127.0.0.1:8100/admin/routes
   ```

2. Asegurarse de que ambos PHONE_NUMBER_ID esten registrados:
   - Rodrigo: 1176096042248467
   - Boston: 1060892013781922

3. Si falta uno, registrarlo manualmente:
   ```bash
   # Ejemplo para Boston si faltara:
   curl -X POST http://127.0.0.1:8100/admin/register \
     -H "Content-Type: application/json" \
     -H "X-Admin-Key: $ROUTER_KEY" \
     -d '{"phone_number_id":"1060892013781922","client_slug":"boston","target_url":"http://boston-web:8000/webhook"}'
   ```

---

## URLs finales de cada bot (para referencia)

| Bot | Chat web | Panel admin | Health | Webhook |
|-----|----------|-------------|--------|---------|
| Rodrigo | https://rodrigo.asistentebot.com.ar/chat | https://rodrigo.asistentebot.com.ar/admin | https://rodrigo.asistentebot.com.ar/health | Via router |
| Boston | https://boston.asistentebot.com.ar/chat | https://boston.asistentebot.com.ar/admin | https://boston.asistentebot.com.ar/health | Via router |

---

*Ultima actualizacion: 2026-05-28*
