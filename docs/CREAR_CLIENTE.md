# Alta Rapida de Nuevo Cliente - AsistenteBot

> Referencia rapida para dar de alta un cliente nuevo en la plataforma.
> Leer este archivo cuando el usuario pregunte por crear un cliente, alta de cliente,
> nuevo cliente, onboarding, o cualquier cosa relacionada con `new_client.sh`.
>
> **Infraestructura base ya configurada:** Caddy, webhook-router, Docker network. Solo ejecutar el script.

---

## TL;DR - Comando Rapido

```bash
ssh -i ~/.ssh/boston_vps ubuntu@167.114.96.29
cd /mnt/data/rodrigo-bot-template
chmod +x scripts/new_client.sh

./scripts/new_client.sh \
  --name "Nombre del Negocio" \
  --slug "negocio" \
  --domain "negocio.asistentebot.com.ar" \
  --phone "+54 9 11 0000-0000" \
  --email "contacto@negocio.com" \
  --whatsapp-mode meta \
  --meta-phone-number-id "ID_DE_META"
```

> **IMPORTANTE:** El primer build de Docker puede tardar **10-15 minutos** porque descarga librerias grandes (PyTorch, ChromaDB, etc.). No interrumpir el script. Si se corta, ejecutar manualmente:
> ```bash
> cd /mnt/data/cliente-{slug} && docker compose up -d --build
> ```

---

## Requisitos Previos (tener listo ANTES de ejecutar)

| Dato | Descripcion | Ejemplo |
|------|-------------|---------|
| **name** | Nombre comercial del cliente | `"Dr. Garcia"` |
| **slug** | Identificador corto (letras minusculas, numeros, guiones) | `garcia` |
| **domain** | Subdominio de `asistentebot.com.ar` | `garcia.asistentebot.com.ar` |
| **phone** | Telefono de contacto del negocio | `+54 11 2345-6789` |
| email | Email de contacto (opcional) | `contacto@garcia.com` |
| meta-phone-number-id | ID del numero en Meta Developers (si WhatsApp real) | `123456789012345` |
| **google-calendar-id** | ID del calendario de Google (si usa turnos) | `abc123@group.calendar.google.com` |

> **Nota:** El DNS wildcard `*.asistentebot.com.ar` ya apunta al VPS. Solo hay que elegir el subdominio. |

---

## Que hace el script automaticamente

1. Crea `/mnt/data/cliente-{slug}/`
2. Copia codigo del template (`app/`, `ui/`, scripts, Dockerfile) desde `rodrigo-bot-template/`
3. Genera `.env` con valores del cliente
4. Genera `docker-compose.yml` con nombres unicos de contenedores
5. Crea documentos iniciales vacios + `system_prompt.txt`
6. Agrega bloque al Caddyfile maestro (`/mnt/data/boston-ai/Caddyfile`)
7. Levanta contenedores Docker (`{slug}-web`, `{slug}-worker`)
8. Registra el numero en el webhook-router (si se paso PHONE_NUMBER_ID)
9. Recarga Caddy

> **Nota:** El webhook-router, Caddy y la red Docker ya estan configurados. No hay que tocarlos.

---

## Checklist despues de ejecutar

- [ ] **Documentos:** Editar archivos en `/mnt/data/cliente-{slug}/data/docs/` (home, servicios, precios, faq, horarios, contacto)
- [ ] **Reindexar:** `cd /mnt/data/cliente-{slug} && docker compose exec web python scripts/index_documents.py`
- [ ] **Prompt:** Ajustar `/mnt/data/cliente-{slug}/data/system_prompt.txt` al tono del negocio
- [ ] **Meta (si modo=meta):**
  - Ir a Meta Developers > WhatsApp > Configuracion > Webhook
  - URL: `https://asistentebot.com.ar/webhook`
  - Token: `rodrigo_webhook_verify_2024`
  - Activar suscripciones: `messages`, `message_statuses`
- [ ] **Google Calendar (si usa turnos):**
  - Copiar el JSON de la cuenta de servicio al contenedor: `docker cp /mnt/data/cliente-{slug}/data/google-service-account.json {slug}-web:/app/data/`
  - Actualizar `.env` con `GOOGLE_CALENDAR_ID` y `GOOGLE_SERVICE_ACCOUNT_JSON=/app/data/google-service-account.json`
  - Reiniciar: `docker compose down && docker compose up -d`
- [ ] **Probar:** `curl https://{dominio}/health`
- [ ] **Entregar:** Chat web, panel admin, y Admin API Key al cliente

---

## Comandos utiles post-creacion

```bash
# Ver logs
cd /mnt/data/cliente-{slug} && docker compose logs -f

# Reiniciar (si se modifica .env)
cd /mnt/data/cliente-{slug} && docker compose down && docker compose up -d
# NOTA: docker compose restart NO lee cambios de .env

# Listar todos los clientes
cd /mnt/data/rodrigo-bot-template && ./scripts/list_clients.sh

# Eliminar cliente (CUIDADO)
cd /mnt/data/rodrigo-bot-template && ./scripts/remove_client.sh --slug {slug} --yes
```

> **Nota para Windows/PowerShell:** El operador `&&` no funciona en PowerShell. Usar `;` en su lugar o ejecutar comandos separados. Ejemplo:
> ```powershell
> scp archivo.txt ubuntu@167.114.96.29:/tmp/
> ssh ubuntu@167.114.96.29 "comando"
> ```

---

## Notas importantes

- **Template:** El codigo base esta en `/mnt/data/rodrigo-bot-template/`. Si se modifica codigo localmente, subirlo antes con `scp`.
- **Recursos:** Cada cliente consume ~300MB de RAM. Verificar con `./scripts/list_clients.sh`.
- **Dominio:** El DNS wildcard `*.asistentebot.com.ar` ya apunta al VPS. No hay que configurar nada en Cloudflare.
- **Router:** Los webhooks de Meta llegan a `https://asistentebot.com.ar/webhook` y el router los redirige a cada instancia.

---

## Troubleshooting

### El script se corto durante el build de Docker

Esto es normal en el primer build. Las librerias (PyTorch, ChromaDB, etc.) pesan ~2GB y tardan en descargarse.

**Solucion:**
```bash
cd /mnt/data/cliente-{slug} && docker compose up -d --build
```

### El contenedor web no inicia (ValueError: Faltan META_ACCESS_TOKEN)

Si ves este error en los logs, significa que las credenciales de Meta no se copiaron correctamente.

**Solucion:** Verificar que el template `.env` tenga las credenciales completas:
```bash
# Verificar que las claves existen (sin mostrar valores)
grep '^META_' /mnt/data/rodrigo-bot-template/.env | sed 's/=.*/=[CONFIGURADO]/'
```

### Caddy no redirige el dominio

Si el dominio no responde pero el health check local funciona:

**Solucion:** Recargar Caddy manualmente:
```bash
cd /mnt/data/boston-ai && docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

---

*Ultima actualizacion: 2026-06-12*
