# Clientes Activos - AsistenteBot

> Estado actual de los clientes desplegados en el VPS.
> Actualizar este archivo cada vez que se cree, modifique o elimine un cliente.

---

## Tabla de clientes

| Slug | Negocio | Dominio | Tipo | WhatsApp | PHONE_NUMBER_ID |
|------|---------|---------|------|----------|-----------------|
| `nspa` | NSPA / Herminda (bot de ejemplo) | nspa.asistentebot.com.ar | Demo | meta | 1221255001061606 |
| `boston` | Boston Uniformes | boston.asistentebot.com.ar | Produccion | meta | 1225894883938438 |
| `micita-info` | MiCita (bot comercial de la plataforma) | micita.asistentebot.com.ar | Produccion | meta | 1276174972238647 |

---

## Detalle por cliente

### nspa (bot de ejemplo)

- **Proposito:** demo del producto (centro de estetica y spa ficticio "NSPA", bot "Herminda").
- **Directorio VPS:** `/mnt/data/cliente-nspa/`
- **Contenedores:** `nspa-web`, `nspa-worker`
- **WABA:** "belleza" (ID 3961279004177016), numero +54 223 15-355-0746
- **Nota:** Tiene Google Calendar configurado (`google-service-account.json` en data/).

### boston

- **Proposito:** cliente real (uniformes).
- **Directorio VPS:** `/mnt/data/cliente-boston/`
- **Contenedores:** `boston-web`, `boston-worker`
- **WABA:** "Boston" (ID 845835888393601), numero +54 2477 15-51-7124
- **Nota:** El Caddy maestro vive en `/mnt/data/boston-ai/` (directorio historico separado).

### micita-info (MiCita)

- **Proposito:** bot comercial que VENDE el servicio MiCita (https://micita.com.ar).
  Responde consultas sobre el servicio y deriva interesados con Rodrigo.
- **Directorio VPS:** `/mnt/data/cliente-micita-info/`
- **Contenedores:** `micita-info-web`, `micita-info-worker`
- **WABA:** "MiCita" (ID 1932995767399091), numero +54 223 15-355-0738
- **Precio comunicado por el bot:** Plan Base $50.000 ARS/mes (placeholder editable en `data/docs/precios.md`).
- **Derivacion humana:** https://wa.me/5492477614405 (Rodrigo)
- **Google Calendar:** pendiente de configurar (por ahora deriva reuniones a WhatsApp).
- **Nota:** El slug quedo `micita-info` pero el dominio publico es `micita.asistentebot.com.ar`.
  El dominio viejo `micita-info.asistentebot.com.ar` fue eliminado del Caddyfile.

---

## Infraestructura compartida

| Componente | Ubicacion | Detalle |
|-----------|-----------|---------|
| Imagen base | `asistentebot-base:latest` | Ver `docs/ARQUITECTURA_DOCKER.md` |
| Template | `/mnt/data/rodrigo-bot-template/` | Codigo fuente para nuevos clientes |
| Caddy maestro | `/mnt/data/boston-ai/` (Caddyfile) | HTTPS para todos los dominios |
| Webhook router | `/mnt/data/webhook-router/` (puerto 8100) | Redirige webhooks de Meta por phone_number_id |
| Red Docker | `boston-ai_default` | Conecta todo |

## Rutas del webhook router (estado actual)

| PHONE_NUMBER_ID | Destino |
|-----------------|---------|
| 1225894883938438 (boston) | http://boston-web:8000/webhook |
| 1276174972238647 (MiCita) | http://micita-info-web:8000/webhook |
| 1221255001061606 (nspa/belleza) | http://nspa-web:8000/webhook |

Verificar en vivo:
```bash
ROUTER_KEY=$(grep ADMIN_API_KEY /mnt/data/webhook-router/.env | cut -d= -f2 | tr -d '"')
curl -s -H "X-Admin-Key: $ROUTER_KEY" http://127.0.0.1:8100/admin/routes
```

---

*Ultima actualizacion: 2026-07-31*
