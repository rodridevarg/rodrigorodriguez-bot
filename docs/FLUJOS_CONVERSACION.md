# Flujos de Conversación y Anti-Loop

> Documentación técnica de los flujos de conversación del bot médico y el sistema anti-loop.

---

## Flujos de conversación implementados

### Diagrama de estados

```
[INICIO]
   │
   ├─ "Hola" / saludo ──────→ [BOTONES DE BIENVENIDA]
   │                              ├─ 🗓️ Sacar turno
   │                              ├─ 💳 Obras sociales
   │                              └─ 💰 Precios
   │
   ├─ "Atienden por OSDE?" ─→ [LISTA DE OBRAS SOCIALES]
   │                              ├─ OSDE
   │                              ├─ Swiss Medical
   │                              ├─ Galeno
   │                              └─ ...
   │
   ├─ "Qué servicios?" ─────→ [LISTA DE SERVICIOS]
   │                              ├─ Consulta general
   │                              ├─ Laboratorio
   │                              ├─ Ecografía
   │                              └─ ...
   │
   └─ Cualquier otra cosa ──→ [RAG NORMAL]
   │                              └─ IA responde con documentos
   │
[CLICK EN BOTÓN/LISTA]
   │
   ├─ btn_turno ────────────→ [RAG: "Quiero sacar un turno"]
   ├─ btn_precios ──────────→ [RAG: "Cuánto cuestan las consultas"]
   ├─ btn_obras ────────────→ [LISTA DE OBRAS SOCIALES]
   ├─ os_osde ──────────────→ [RAG: "Información sobre OSDE"]
   ├─ os_swiss ─────────────→ [RAG: "Información sobre Swiss Medical"]
   ├─ srv_lab ──────────────→ [RAG: "Información sobre laboratorio"]
   └─ Cualquier otro ID ────→ [RAG: query por defecto]
```

---

## Sistema Anti-Loop

### Problema identificado

**Escenario del bug:**
```
Usuario: "Hola"
Bot: [BOTONES: Turno | Obras | Precios]

Usuario: toca "Obras sociales"
Bot: [LISTA: OSDE | Swiss | Galeno | ...]

Usuario: toca "OSDE"
Bot: [LISTA: OSDE | Swiss | Galeno | ...]  ← ¡LOOP! Reenvió la lista

Usuario: toca "OSDE"
Bot: [LISTA: OSDE | Swiss | Galeno | ...]  ← ¡LOOP INFINITO!
```

### Causa raíz

El detector `_is_about_insurance("OSDE")` devolvía `True` porque "OSDE" está en la lista de keywords. Como el código ejecutaba los detectores genéricos DESPUÉS de los botones pero ANTES del RAG, no distinguía entre:

- "¿Qué obras sociales tienen?" → mostrar lista ✅
- "OSDE" (click de botón) → info específica de OSDE ✅

### Solución implementada

**Regla de oro:** Detectar clicks de botón **ANTES** que intenciones genéricas.

**Orden correcto en `process_inbound_by_id()`:**

```python
# 1. CLICKS DE BOTÓN (más específico)
if button_id:
    if button_id == "btn_obras":
        return send_insurance_list()
    if button_id.startswith("os_"):
        return send_rag_answer(query_specific)

# 2. SALUDO EXPLÍCITO
if _is_greeting(text):
    return send_greeting_with_buttons()

# 3. INTENCIONES GENÉRICAS (con anti-loop)
if _is_about_insurance(text):
    if not _was_last_outbound_a_list(from_number, "insurance"):
        return send_insurance_list()  # Solo si no se envió antes
    else:
        return send_rag_answer(query_fallBack)  # Ya envió lista

# 4. RAG NORMAL (cualquier otra cosa)
return send_rag_answer(text)
```

### Anti-loop por historial

```python
def _was_last_outbound_a_list(self, from_number, list_type):
    """Verifica si el último mensaje del bot fue una lista interactiva.
    
    Esto evita reenviar la misma lista si el usuario repite la intención
    o toca un botón que activaría el mismo detector.
    """
    history = store.get_conversation_history(from_number, limit=1)
    if not history:
        return False
    
    last_answer = history[0].get("answer", "")
    
    if list_type == "insurance":
        return "obras sociales" in last_answer.lower() and "seleccioná" in last_answer.lower()
    elif list_type == "services":
        return "servicios" in last_answer.lower() and "seleccioná" in last_answer.lower()
    
    return False
```

---

## Mapeo de IDs de botón a queries de RAG

Cada ID de botón se mapea a una query específica que se le pasa al RAG:

| ID del botón | Query enviada al RAG |
|--------------|---------------------|
| `btn_turno` | "Quiero sacar un turno médico, ¿cómo hago?" |
| `btn_precios` | "¿Cuánto cuestan las consultas y estudios? Precios particulares y con obra social." |
| `btn_obras` | (No usa RAG, envía lista) |
| `os_osde` | "Tengo OSDE, ¿qué copago tengo que pagar? ¿cómo atienden con OSDE?" |
| `os_swiss` | "Tengo Swiss Medical, ¿qué copago tengo? ¿cómo atienden con Swiss Medical?" |
| `os_galeno` | "Tengo Galeno, ¿qué copago tengo? ¿cómo atienden con Galeno?" |
| `os_medicus` | "Tengo Medicus, ¿qué copago tengo? ¿cómo atienden con Medicus?" |
| `os_omint` | "Tengo Omint, ¿qué copago tengo? ¿cómo atienden con Omint?" |
| `os_pami` | "Tengo PAMI, ¿cómo puedo atenderme? ¿necesito autorización?" |
| `os_ioma` | "Tengo IOMA, ¿cómo puedo atenderme? ¿necesito orden médica?" |
| `srv_consulta` | "Quiero información sobre la consulta médica general de primera vez." |
| `srv_control` | "Quiero información sobre la consulta de control o seguimiento." |
| `srv_checkup` | "Quiero información sobre el check-up anual completo." |
| `srv_online` | "Quiero información sobre la telemedicina o consulta online." |
| `srv_lab` | "Quiero información sobre los estudios de laboratorio, análisis de sangre y orina. ¿necesito ayuno?" |
| `srv_eco` | "Quiero información sobre la ecografía. ¿cómo me preparo?" |
| `srv_rx` | "Quiero información sobre la radiografía." |
| `srv_ecg` | "Quiero información sobre el electrocardiograma." |

---

## Flujos de prueba (Tests)

### Test 1: Greeting → Obras → OSDE

**Pasos:**
1. "Hola" → Debe responder con botones de bienvenida
2. Tocar "💳 Obras sociales" → Debe enviar lista de obras sociales
3. Tocar "OSDE" → Debe responder con info específica de OSDE (RAG)

**Validaciones:**
- No debe reenviar la lista de obras sociales en el paso 3
- La respuesta debe mencionar copagos de OSDE
- No debe haber loops

### Test 2: Anti-loop OSDE

**Pasos:**
1. "Hola" → Botones
2. Tocar "Obras sociales" → Lista
3. Tocar "OSDE" → RAG
4. Tocar "OSDE" → RAG
5. Tocar "OSDE" → RAG

**Validaciones:**
- Cada paso 3-5 debe ser RAG (no lista)
- No debe haber respuestas idénticas consecutivas

### Test 3: Greeting → Precios

**Pasos:**
1. "Hola" → Botones
2. Tocar "💰 Precios" → RAG

**Validaciones:**
- Debe mencionar precios de consultas ($25.000, $18.000, etc.)

### Test 4: Greeting → Turno

**Pasos:**
1. "Hola" → Botones
2. Tocar "🗓️ Turno" → RAG

**Validaciones:**
- Debe pedir nombre, DNI y obra social

### Test 5: Servicios → Laboratorio

**Pasos:**
1. "¿Qué servicios tienen?" → Lista de servicios
2. Tocar "Laboratorio" → RAG

**Validaciones:**
- Debe mencionar preparación de estudios (ayuno, etc.)
- No debe reenviar la lista

### Test 6: Urgencia

**Pasos:**
1. "Tengo dolor de pecho fuerte" → RAG

**Validaciones:**
- Debe redirigir a 107/911 o guardia
- NO debe dar diagnóstico ni consejo médico

### Test 7: Primera visita

**Pasos:**
1. "Es mi primera vez, ¿qué debo llevar?" → RAG

**Validaciones:**
- Debe mencionar documentos (DNI, credencial, estudios previos)

### Test 8: Obra social directa (Galeno)

**Pasos:**
1. "¿Atienden por Galeno?" → Lista de obras sociales
2. Tocar "Galeno" → RAG

**Validaciones:**
- Debe dar info específica de Galeno y copagos
- No debe reenviar la lista

---

## Cómo agregar un nuevo flujo de conversación

1. **Definir el ID del botón** en `_rag_query_for_button()`
2. **Agregar la lógica** en `process_inbound_by_id()` en la sección "1. DETECTAR CLICK DE BOTÓN"
3. **Crear el test** en `scripts/test_conversation_flows.py`
4. **Ejecutar tests** y verificar que pasen

---

*Última actualización: 2026-06-01*
