# Sistema de Botones Interactivos en WhatsApp

> Guía completa para implementar botones interactivos (Reply Buttons y List Messages) en el bot de WhatsApp usando la API oficial de Meta.
> **Proyecto de referencia:** Centro Médico Demostración (Dr. Juan Pérez - Clínica general)

---

## Índice

1. [Qué es esto](#qué-es-esto)
2. [Tipos de botones soportados](#tipos-de-botones-soportados)
3. [Arquitectura](#arquitectura)
4. [Cómo funciona el flujo](#cómo-funciona-el-flujo)
5. [Implementación paso a paso](#implementación-paso-a-paso)
6. [Anti-loop: cómo evitar bucles infinitos](#anti-loop-cómo-evitar-bucles-infinitos)
7. [Agregar botones para un nuevo cliente](#agregar-botones-para-un-nuevo-cliente)
8. [Limitaciones de la API de Meta](#limitaciones-de-la-api-de-meta)
9. [Testing](#testing)
10. [Troubleshooting](#troubleshooting)

---

## Qué es esto

Este sistema permite que el bot de WhatsApp envíe **mensajes interactivos** con botones en lugar de solo texto plano. Esto mejora drásticamente la experiencia del usuario porque:

- Reduce errores de tipeo
- Guía al usuario por opciones predefinidas
- Se ve más profesional
- Aumenta la tasa de conversación

### Ejemplo visual

**Antes (solo texto):**
```
Bot: ¿En qué puedo ayudarte?
     Escribí: turno, precios, obras sociales...
```

**Después (con botones):**
```
Bot: ¡Hola! ¿En qué puedo ayudarte?
     [🗓️ Sacar turno] [💳 Obras sociales] [💰 Precios]
```

---

## Tipos de botones soportados

### 1. Reply Buttons (Botones inline)

- **Máximo:** 3 botones por mensaje
- **Vista:** Botones horizontales debajo del mensaje
- **Uso ideal:** Opciones principales de bienvenida
- **Formato de respuesta:** `[btn_id] Título del botón`

```python
buttons = [
    {"reply": {"id": "btn_turno", "title": "🗓️ Sacar turno"}},
    {"reply": {"id": "btn_obras", "title": "💳 Obras sociales"}},
    {"reply": {"id": "btn_precios", "title": "💰 Precios"}},
]
```

### 2. List Messages (Menú desplegable)

- **Máximo:** 10 opciones totales (divididas en secciones)
- **Vista:** Un botón que abre un menú desplegable tipo "Ver opciones"
- **Uso ideal:** Catálogos extensos (obras sociales, servicios, productos)
- **Formato de respuesta:** `[row_id] Título de la fila`

```python
sections = [
    {
        "title": "Prepagas principales",
        "rows": [
            {"id": "os_osde", "title": "OSDE", "description": "210/310 sin copago"},
            {"id": "os_swiss", "title": "Swiss Medical", "description": "SMG sin copago"},
        ],
    },
]
```

---

## Arquitectura

### Archivos involucrados

| Archivo | Rol |
|---------|-----|
| `app/whatsapp_sender.py` | Envía mensajes a la API de Meta. Tiene `send_interactive_buttons()` y `send_interactive_list()` |
| `app/whatsapp_service.py` | Lógica de negocio. Decide QUÉ enviar (botones, lista, RAG) según el mensaje del usuario |
| `app/whatsapp_parser.py` | Parsea los webhooks entrantes. Detecta clicks de botones (`interactive` type) |
| `app/whatsapp_models.py` | Modelos de datos (InboundTextMessage, etc.) |

### Diagrama de flujo

```
Usuario envía mensaje
        ↓
[whatsapp_parser.py] Detecta tipo: text | interactive (click de botón)
        ↓
[whatsapp_service.py] Procesa el mensaje:
        ↓
        ├─ ¿Es click de botón? → Buscar respuesta específica (RAG o lista)
        ├─ ¿Es saludo? → Enviar botones de bienvenida
        ├─ ¿Es intención genérica? → Enviar lista interactiva (solo si no se envió antes)
        └─ Cualquier otra cosa → RAG normal
        ↓
[whatsapp_sender.py] Envía por API de Meta
```

---

## Cómo funciona el flujo

### Flujo 1: Bienvenida con botones

```
Usuario: "Hola"
    → Bot: "¡Hola! ¿En qué puedo ayudarte?"
      [🗓️ Sacar turno] [💳 Obras sociales] [💰 Precios]
```

**Código:**
```python
if _is_greeting(text):
    return self._send_greeting_with_buttons(...)
```

### Flujo 2: Click en botón de bienvenida

```
Usuario toca: "💳 Obras sociales"
    → Llega al backend: "[btn_obras] 💳 Obras sociales"
    → Bot: "Estas son las obras sociales..."
      [Ver obras sociales] ← abre menú desplegable
```

**Código:**
```python
button_id, button_title = _parse_button_click(text)
if button_id == "btn_obras":
    return self._send_insurance_list(...)
```

### Flujo 3: Click en item de lista

```
Usuario toca: "OSDE" (dentro de la lista)
    → Llega al backend: "[os_osde] OSDE"
    → Bot: "¡Claro! Con OSDE los copagos son: 210/310 sin copago..."
```

**Código:**
```python
if button_id.startswith("os_"):
    query = _rag_query_for_button(button_id, button_title)
    return self._send_rag_answer(..., query)
```

**Importante:** La respuesta va por **RAG** (IA leyendo documentos), no es texto fijo. Esto permite que sea más humana y flexible.

---

## Implementación paso a paso

### Paso 1: Definir los botones

En `whatsapp_service.py`, crear las funciones que envían botones:

```python
def _send_greeting_with_buttons(self, inbound_id, to_number, provider):
    body = "¡Hola! ¿En qué puedo ayudarte?"
    buttons = [
        {"reply": {"id": "btn_turno", "title": "🗓️ Sacar turno"}},
        {"reply": {"id": "btn_obras", "title": "💳 Obras sociales"}},
        {"reply": {"id": "btn_precios", "title": "💰 Precios"}},
    ]
    return self._send_interactive_buttons(inbound_id, to_number, body, buttons, provider)
```

### Paso 2: Mapear IDs de botón a queries de RAG

En `_rag_query_for_button()`, definir qué pregunta le hace el bot a la IA:

```python
def _rag_query_for_button(button_id, button_title):
    queries = {
        "btn_turno": "Quiero sacar un turno médico, ¿cómo hago?",
        "os_osde": "Tengo OSDE, ¿qué copago tengo que pagar?",
        "srv_lab": "Quiero información sobre estudios de laboratorio. ¿necesito ayuno?",
    }
    return queries.get(button_id, button_title)
```

### Paso 3: Detectar clicks en el flujo principal

En `process_inbound_by_id()`, detectar PRIMERO si es un click de botón:

```python
# 1. DETECTAR CLICK DE BOTÓN (formato: [id] Título)
button_id, button_title = _parse_button_click(text)

if button_id:
    if button_id == "btn_obras":
        return self._send_insurance_list(...)
    if button_id.startswith("os_"):
        query = _rag_query_for_button(button_id, button_title)
        return self._send_rag_answer(..., query)
```

### Paso 4: Parsear clicks de botón

En `whatsapp_parser.py`, el webhook de Meta envía clicks de botón como:

```json
{
  "type": "interactive",
  "interactive": {
    "type": "button_reply",
    "button_reply": {
      "id": "os_osde",
      "title": "OSDE"
    }
  }
}
```

El parser lo convierte en texto: `[os_osde] OSDE`

---

## Anti-loop: cómo evitar bucles infinitos

### El problema

Sin anti-loop, esto sucede:

```
Usuario: "Hola" → Botones
Usuario: "Obras sociales" → Lista
Usuario: "OSDE" → ???
```

Si no detectamos que "OSDE" es un click de botón específico, el detector genérico `_is_about_insurance("OSDE")` devuelve `True` y **reenvía la lista entera** → el usuario toca OSDE otra vez → loop infinito.

### La solución

**Regla de oro:** Detectar clicks de botón **ANTES** que intenciones genéricas.

```python
# ORDEN CORRECTO:
1. ¿Es click de botón? → Respuesta específica (RAG o lista)
2. ¿Es saludo? → Botones de bienvenida
3. ¿Es intención genérica? → Lista (PERO verificar que no se envió recientemente)
4. Cualquier otra cosa → RAG normal
```

### Implementación del anti-loop

```python
def _was_last_outbound_a_list(self, from_number, list_type):
    """Verifica si ya enviamos una lista recientemente."""
    history = store.get_conversation_history(from_number, limit=1)
    if not history:
        return False
    last_answer = history[0].get("answer", "")
    
    if list_type == "insurance":
        return "obras sociales" in last_answer.lower() and "seleccioná" in last_answer.lower()
    
    return False

# Uso:
if _is_about_insurance(text):
    if not self._was_last_outbound_a_list(from_number, "insurance"):
        return self._send_insurance_list(...)  # Primera vez → lista
    else:
        return self._send_rag_answer(...)  # Ya envió lista → RAG directo
```

---

## Agregar botones para un nuevo cliente

### Checklist

- [ ] Definir los 3 botones de bienvenida (Reply Buttons)
- [ ] Definir las listas desplegables (List Messages) si aplica
- [ ] Crear `_rag_query_for_button()` con queries específicas para cada ID
- [ ] En `process_inbound_by_id()`, agregar los nuevos IDs en la sección de "Detectar click de botón"
- [ ] Verificar que los IDs no se solapen (ej: `btn_` para botones, `os_` para obras sociales)
- [ ] Actualizar `_is_about_insurance()`, `_is_about_services()`, etc. para el nuevo dominio
- [ ] Ejecutar `scripts/test_conversation_flows.py` y verificar 8/8 tests
- [ ] Probar en WhatsApp real con el número de prueba

### Ejemplo: Adaptar para una tienda de ropa

```python
# Botones de bienvenida
def _send_greeting_with_buttons(self, ...):
    buttons = [
        {"reply": {"id": "btn_catalogo", "title": "🛍️ Ver catálogo"}},
        {"reply": {"id": "btn_envios", "title": "🚚 Envíos"}},
        {"reply": {"id": "btn_talles", "title": "📏 Guía de talles"}},
    ]

# Queries de RAG
def _rag_query_for_button(button_id, button_title):
    queries = {
        "btn_catalogo": "Quiero ver los productos disponibles y precios",
        "btn_envios": "¿Hacen envíos? ¿Cuánto tarda y cuánto cuesta?",
        "btn_talles": "¿Cómo sé mi talle? ¿Tienen guía de medidas?",
        "cat_remeras": "Quiero ver remeras disponibles",
        "cat_pantalones": "Quiero ver pantalones disponibles",
    }
    return queries.get(button_id, button_title)
```

---

## Limitaciones de la API de Meta

| Limitación | Detalle |
|------------|---------|
| **Ventana de 24 horas** | Los botones solo funcionan si el usuario inició la conversación en las últimas 24h |
| **Máximo 3 reply buttons** | Por mensaje |
| **Máximo 10 list rows** | En total entre todas las secciones |
| **Título máximo** | 20 caracteres para botones, 24 para filas de lista |
| **Descripción máxima** | 72 caracteres para filas de lista |
| **No se pueden mezclar** | Botones con ciertos tipos de mensajes (templates, etc.) |
| **Fallback automático** | Si el envío de botones falla, el sistema cae a texto plano |

---

## Testing

### Script de testing automático

```bash
python scripts/test_conversation_flows.py
```

### Qué testea

- **8 flujos de conversación** completos simulados
- **Anti-loop:** Verifica que no haya respuestas repetidas >2 veces
- **Identidad:** Verifica que la respuesta mantenga la identidad del cliente
- **Progresión:** Cada paso debe aportar información nueva
- **No diagnósticos:** Si hay síntomas, redirige al médico/urgencias

### Resultado esperado

```
📈 RESULTADO: 8/8 tests pasaron | 0 fallos
```

---

## Troubleshooting

### "Los botones no aparecen en WhatsApp"

- Verificar que `WHATSAPP_MODE=meta` en `.env`
- Verificar que el número de teléfono tenga la API de WhatsApp Business activada
- Verificar que la conversación esté dentro de la ventana de 24 horas

### "Al tocar un botón, el bot responde con el menú otra vez"

- Verificar que `_parse_button_click()` detecta el formato `[id] Título`
- Verificar que el `button_id` está mapeado en `process_inbound_by_id()` ANTES de los detectores genéricos
- Verificar el orden: clicks → saludo → intenciones genéricas → RAG

### "El test da 'duplicado ignorado'"

- Los IDs de mensaje deben ser únicos. En producción, Meta genera IDs únicos.
- En tests, usar `uuid.uuid4()` o contadores globales.

### "La respuesta del RAG es lenta"

- Los botones por RAG tardan 1-3 segundos porque consultan la IA.
- Para respuestas instantáneas, usar texto hardcodeado (Opción A en lugar de RAG).

---

## Referencias

- [Meta WhatsApp Cloud API - Interactive Messages](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages#interactive-messages)
- `app/whatsapp_sender.py` - Implementación de envío
- `app/whatsapp_service.py` - Lógica de flujo
- `app/whatsapp_parser.py` - Parseo de webhooks
- `scripts/test_conversation_flows.py` - Tests automáticos

---

*Última actualización: 2026-06-01*
