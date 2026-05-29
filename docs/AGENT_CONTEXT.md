# AGENT CONTEXT - Plataforma Multi-Cliente WhatsApp

> Este documento es para referencia interna del agente (yo, OpenCode).
> Contiene todos los datos operativos del sistema para poder actuar rapido sin tener que preguntar.

---

## Infraestructura

| Recurso | Valor |
|---------|-------|
| VPS IP | 167.114.96.29 |
| Dominio principal | asistentebot.com.ar |
| DNS | Cloudflare, proxy GRIS (DNS only) |
| Wildcard | *.asistentebot.com.ar → 167.114.96.29 |
| SSH key local | C:\Users\rodri\.ssh\boston_vps |
| SSH user | root |

---

## Estructura en VPS

```
/mnt/data/
├── boston-ai/              # Caddy maestro + aibrain (Boston)
│   ├── Caddyfile
│   ├── docker-compose.yml
│   └── .env
│
├── rodrigo-bot/            # Bot original de Rodrigo
│   ├── docker-compose.yml
│   ├── .env
│   └── app/
│
├── webhook-router/         # Router central de webhooks (NEW)
│   ├── docker-compose.yml
│   ├── .env
│   └── app/
│
└── rodrigo-bot-template/   # Codigo fuente del template (git repo)
```

---

## Servicios Docker Activos

| Nombre | Tipo | Estado | URL interna |
|--------|------|--------|-------------|
| webhook-router | Router central | Healthy | http://webhook-router:8100 |
| rodrigo-web | Bot Rodrigo | Healthy | http://rodrigo-web:8000 |
| rodrigo-worker | Worker Rodrigo | Up | - |
| boston-web | Bot Boston | Healthy | http://boston-web:8000 |
| boston-worker | Worker Boston | Up | - |
| boston-caddy | Reverse proxy | Up | 80, 443 |

---

## Dominios configurados en Caddyfile

| Dominio | Destino | Proposito |
|---------|---------|-----------|
| bot.bostonuniformes.com.ar | boston-web:8000 | Legacy Boston (mantener) |
| bot.rodrigorodriguez.com.ar | rodrigo-web:8000 | Legacy Rodrigo (mantener) |
| asistentebot.com.ar/webhook* | webhook-router:8100 | Webhook central para Meta |
| boston.asistentebot.com.ar | boston-web:8000 | **NUEVO** Boston |
| rodrigo.asistentebot.com.ar | rodrigo-web:8000 | **NUEVO** Rodrigo |

---

## Webhook Router

### .env del router
- META_VERIFY_TOKEN: rodrigo_webhook_verify_2024
- META_VALIDATE_SIGNATURE: true (el router valida firmas)
- ADMIN_API_KEY: (ver /mnt/data/webhook-router/.env)
- Puerto: 8100
- Red: boston-ai_default

### Rutas registradas
| phone_number_id | client_slug | target_url |
|-----------------|-------------|------------|
| 1176096042248467 | rodrigo | http://rodrigo-web:8000/webhook |
| 1060892013781922 | boston | http://boston-web:8000/webhook |

### Endpoints
- GET/POST /webhook → Recibe de Meta, redirige a instancia
- GET /health → Status
- POST /admin/register → Registrar numero
- POST /admin/unregister → Desregistrar numero
- GET /admin/routes → Listar rutas

---

## Bots existentes (configuracion clave)

### Rodrigo
- PHONE_NUMBER_ID: 1176096042248467
- WABA_ID: 947623021605631
- META_VERIFY_TOKEN: rodrigo_webhook_verify_2024
- META_VALIDATE_SIGNATURE: false (router valida por el)
- DOMAIN: rodrigo.asistentebot.com.ar
- PUBLIC_WEBHOOK_URL: https://rodrigo.asistentebot.com.ar
- Ubicacion: /mnt/data/rodrigo-bot/

### Boston
- PHONE_NUMBER_ID: 1060892013781922
- WABA_ID: 1521218512920068
- META_VERIFY_TOKEN: boston_webhook_verify_2024
- META_VALIDATE_SIGNATURE: false (router valida por el)
- DOMAIN: boston.asistentebot.com.ar
- PUBLIC_WEBHOOK_URL: https://boston.asistentebot.com.ar
- Ubicacion: /mnt/data/boston-ai/

---

## Scripts clave

| Script | Ubicacion | Uso |
|--------|-----------|-----|
| setup_router.sh | rodrigo-bot-template/scripts/ | Setup inicial del router (1 vez) |
| new_client.sh | rodrigo-bot-template/scripts/ | Crear cliente nuevo |
| remove_client.sh | rodrigo-bot-template/scripts/ | Eliminar cliente |
| deploy_client.sh | rodrigo-bot-template/scripts/ | Actualizar codigo de cliente |
| list_clients.sh | rodrigo-bot-template/scripts/ | Listar clientes activos |

---

## Problemas conocidos del VPS

1. **Disco raiz (/) lleno** - 2.9GB total, 100% usado
   - Solucion: Docker data esta en /var/lib/docker (raiz)
   - No mover Docker data a /mnt/data sin copiar todo primero
   - Liberar /tmp y /var/log si es necesario

2. **No hay git** en el VPS
   - Deploys via SCP + tar
   - Repo local en C:\Users\rodri\desarrollos\rodrigorodriguez-bot

3. **Docker compose** version antigua (usa `docker compose` sin guion)

---

## Comandos utiles rapidos

```bash
# Ver estado de todo
docker ps

# Ver rutas del router
curl -H "X-Admin-Key: KEY" http://127.0.0.1:8100/admin/routes

# Logs router
cd /mnt/data/webhook-router && docker compose logs -f

# Logs Rodrigo
cd /mnt/data/rodrigo-bot && docker compose logs -f

# Logs Boston
cd /mnt/data/boston-ai && docker compose logs -f

# Recargar Caddy
cd /mnt/data/boston-ai && docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile

# Reiniciar todo (down+up para leer .env modificado)
cd /mnt/data/webhook-router && docker compose down && docker compose up -d
cd /mnt/data/rodrigo-bot && docker compose down && docker compose up -d
cd /mnt/data/boston-ai && docker compose down && docker compose up -d
```

---

## Decisiones arquitectonicas

- **Router unico**: asistentebot.com.ar/webhook recibe TODO de Meta
- **Instancias NO validan firma**: META_VALIDATE_SIGNATURE=false
- **Router SI valida**: META_VALIDATE_SIGNATURE=true en router
- **Coleccion por defecto**: rodrigo_docs (backwards compat)
- **WhatsApp mode**: meta (produccion)
- **Webhook mode**: async (worker procesa)
- **Meta App**: Solo UNA App en Meta (la de Rodrigo). Ambos numeros estan en la misma WABA.
- **Token de verificacion**: rodrigo_webhook_verify_2024 (el mismo para ambos bots)

## Notas operativas importantes

1. **Cambiar .env no basta**: Si se modifica META_VALIDATE_SIGNATURE (o cualquier variable) en el .env, hay que hacer `docker compose down && docker compose up -d` para que el contenedor la lea. `docker compose restart` NO funciona.

2. **Deploys**: El VPS no tiene git. Usar `scp -r webhook-router root@vps:/mnt/data/` o tarball para actualizar codigo.

3. **Espacio en disco**: El disco raiz (/) esta al 100%. Si hay problemas de build, limpiar cache: `docker system prune -f`

---

*Ultima actualizacion: 2026-05-28*
*Creado para referencia rapida del agente*
