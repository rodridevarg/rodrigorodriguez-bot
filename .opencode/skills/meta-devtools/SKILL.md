---
name: meta-devtools
description: Use when the user is working with Meta apps, WhatsApp Cloud API, webhooks, phone numbers, WABA, or Meta Developers configuration for this bot.
---

# Meta Developer Tools MCP

Este skill activa el uso del MCP de Meta Developer Tools para diagnosticar y gestionar la integración con Meta/WhatsApp Cloud API.

## Cuándo usar

- Configurar o revisar webhooks de WhatsApp.
- Verificar suscripciones de webhooks (`messages`, `message_statuses`).
- Diagnosticar problemas con números de teléfono o WABAs.
- Revisar configuración de la App de Meta.
- Verificar uso de la API, límites de rate o deprecaciones.
- Antes de deployar un cliente nuevo en Meta.

## Herramientas principales

| Herramienta | Uso típico |
|-------------|------------|
| `devtools_app_list` | Descubrir apps disponibles y sus app_id. |
| `devtools_app` | Revisar configuración básica, seguridad y permisos de una App. |
| `devtools_webhook_list` | Listar temas y suscripciones activas de webhooks. |
| `devtools_webhook_manage` | Crear, actualizar o eliminar suscripciones a webhooks. Requiere permiso de gestión. |
| `devtools_webhook_test` | Enviar eventos de prueba al endpoint de webhook. |
| `devtools_api_usage` | Verificar límites de frecuencia y uso de la API. |

## Flujos recomendados

### Verificar webhooks de una App

1. Usar `devtools_app_list` para obtener el `app_id`.
2. Usar `devtools_webhook_list` para ver suscripciones.
3. Si falta `messages` o `message_statuses`, usar `devtools_webhook_manage` para suscribir la App con la URL `https://asistentebot.com.ar/webhook`.

### Diagnosticar por qué no llegan mensajes

1. `devtools_webhook_list` para confirmar suscripciones.
2. `devtools_webhook_test` para enviar un evento de prueba.
3. Verificar en el VPS que el webhook-router reciba la petición:
   ```bash
   cd /mnt/data/webhook-router && docker compose logs -f
   ```

## Consideraciones

- El MCP requiere autenticación OAuth con Meta. OpenCode pedirá iniciar sesión la primera vez.
- El acceso es por App: al autenticarte, elegís a qué Apps de Meta das acceso.
- El MCP de Meta está en beta; las herramientas pueden cambiar.
- La gestión de webhooks (`devtools_webhook_manage`) requiere el scope `manage`.
