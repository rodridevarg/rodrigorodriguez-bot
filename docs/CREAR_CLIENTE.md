# Alta Rapida de Nuevo Cliente - AsistenteBot

> Referencia rapida para dar de alta un cliente nuevo en la plataforma.
> Leer este archivo cuando el usuario pregunte por crear un cliente, alta de cliente,
> nuevo cliente, onboarding, o cualquier cosa relacionada con `new_client.sh`.

---

## TL;DR - Comando Rapido

```bash
ssh -i ~/.ssh/boston_vps root@167.114.96.29
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

---

## Que hace el script automaticamente

1. Crea `/mnt/data/cliente-{slug}/`
2. Copia codigo del template (`app/`, `ui/`, scripts, Dockerfile)
3. Genera `.env` con valores del cliente
4. Genera `docker-compose.yml` con nombres unicos de contenedores
5. Crea documentos iniciales vacios + `system_prompt.txt`
6. Agrega bloque al Caddyfile maestro
7. Levanta contenedores Docker (`{slug}-web`, `{slug}-worker`)
8. Registra el numero en el webhook-router (si se paso PHONE_NUMBER_ID)
9. Recarga Caddy

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

---

## Notas importantes

- **Template:** El codigo base esta en `/mnt/data/rodrigo-bot-template/`. Si se modifica codigo localmente, subirlo antes con `scp`.
- **Recursos:** Cada cliente consume ~300MB de RAM. Verificar con `./scripts/list_clients.sh`.
- **Dominio:** El DNS wildcard `*.asistentebot.com.ar` ya apunta al VPS. No hay que configurar nada en Cloudflare.
- **Router:** Los webhooks de Meta llegan a `https://asistentebot.com.ar/webhook` y el router los redirige a cada instancia.

---

*Ultima actualizacion: 2026-05-30*
