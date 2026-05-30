# Setup de WhatsApp (Meta) - Secretaria Virtual
# Rodrigo Rodriguez Bot

> Estado: PENDIENTE - Esperando aprobacion de verificacion de negocio en Meta
> Fecha inicio: 2026-05-26
> Fecha objetivo: 2026-05-27

---

## ✅ Lo que YA esta hecho

| Paso | Estado | Detalle |
|------|--------|---------|
| Bot deployado en VPS | ✅ | `https://rodrigo.asistentebot.com.ar` |
| Chat web funcionando | ✅ | Responde preguntas con RAG |
| App creada en Meta Developers | ✅ | Nombre: (completar) |
| WABA ID obtenido | ✅ | `947623021605631` |
| Phone Number ID obtenido | ✅ | `1176096042248467` |
| Numero real configurado | ✅ | (completar numero) |
| Verificacion de negocio enviada | ⏳ | Constancia de CUIT subida a Meta |

---

## ⏳ Lo que estamos ESPERANDO

Meta debe aprobar la verificacion del negocio. Esto puede tardar:
- 30 minutos a 4 horas (automatico)
- Hasta 48 horas (revision manual)

---

## 📋 Lo que falta hacer (cuando Meta apruebe)

### Paso 1: Obtener credenciales de la app

Ir a Meta Developers > Tu App:

| Dato | Ubicacion en Meta | Valor actual | Estado |
|------|-------------------|--------------|--------|
| Access Token | WhatsApp > Configuracion de la API > Token de acceso | `__________` | ❌ Falta |
| App Secret | Configuracion > Basico > Clave secreta de la app (click "Mostrar") | `__________` | ❌ Falta |

> **Nota:** El token puede ser temporal (caduca cada 24hs) o permanente.

### Paso 2: Configurar Webhook en Meta

Ir a WhatsApp > Configuracion > Webhook:

- **URL de devolucion de llamada**: `https://asistentebot.com.ar/webhook` (ruta central del router)
- **Token de verificacion**: `rodrigo_webhook_verify_2024`
- Click en **Verificar y guardar**

Luego, en **Gestionar suscripciones**, activar:
- ✅ `messages`
- ✅ `message_statuses`

### Paso 3: Configurar VPS (OpenCode ejecuta esto)

Una vez que se tengan Access Token y App Secret, ejecutar en el VPS:

```bash
ssh -i ~/.ssh/boston_vps root@167.114.96.29

cd /mnt/data/rodrigo-bot

# 1. Editar .env
nano .env
```

Cambiar estas lineas:
```env
WHATSAPP_MODE=meta
META_ACCESS_TOKEN=EAAX... (token real)
META_PHONE_NUMBER_ID=1176096042248467
META_WABA_ID=947623021605631
META_APP_SECRET=a1b2c3... (app secret real)
META_VERIFY_TOKEN=rodrigo_webhook_verify_2024
META_GRAPH_VERSION=v23.0
META_VALIDATE_SIGNATURE=true
PUBLIC_WEBHOOK_URL=https://rodrigo.asistentebot.com.ar
WEBHOOK_MODE=async
```

Guardar y salir (Ctrl+X, Y, Enter).

```bash
# 2. Reconstruir y reiniciar contenedores
docker compose up -d --build

# 3. Verificar estado
docker compose ps
docker compose logs -f web
docker compose logs -f worker
```

### Paso 4: Probar mensaje real

1. Abrir WhatsApp en tu celular
2. Escribir al numero de prueba/real configurado en Meta
3. Enviar: `Hola`
4. Verificar logs en VPS:
   ```bash
   docker compose logs -f worker
   ```

Deberia aparecer:
```
[WORKER] 1 mensajes pendientes encontrados
[WORKER] Procesando mensaje wamid.XXX...
[WORKER] Respuesta enviada: wamid.YYY...
```

---

## 🆘 Troubleshooting

### "No se pudo verificar la URL del webhook"
- Verificar que el bot este online: `curl https://rodrigo.asistentebot.com.ar/health`
- Verificar que `META_VERIFY_TOKEN` en `.env` sea EXACTAMENTE igual al de Meta
- Probar: `curl -v "https://asistentebot.com.ar/webhook?hub.mode=subscribe&hub.verify_token=rodrigo_webhook_verify_2024&hub.challenge=test123"`

### "Token invalido" o "Error al enviar"
- El token temporal caduco. Generar nuevo en Meta Developers.

### "No llega mensaje al VPS"
- Verificar suscripciones de eventos activadas
- Verificar que se escribio al numero correcto
- Verificar que el numero siga como destinatario de prueba

---

## 📁 Archivos relacionados

- `docs/VPS_DEPLOY.md` - Guia completa de deploy
- `scripts/deploy.sh` - Script de deploy rapido
- `scripts/check_vps.sh` - Health check de ambos bots
- `app/config.py` - Variables de entorno
- `.env` - Credenciales (NO versionar)

---

## 📞 Contacto / Soporte

- WhatsApp personal: +54 9 2477 614405
- Email: rodrigo@rodrigorodriguez.com.ar

---

*Creado: 2026-05-26*
*Proxima accion: Esperar aprobacion de Meta, luego obtener Access Token + App Secret*
