# Testing de Conversaciones

> Guía para ejecutar y entender los tests automáticos de flujos de conversación.

---

## Qué testeamos

El script `scripts/test_conversation_flows.py` simula conversaciones completas por WhatsApp como si fueran mensajes reales, pero usando el `FakeWhatsAppSender` (no toca la API de Meta ni el LLM real).

**Nota importante:** El script **SÍ usa el LLM real** para las respuestas del RAG. Esto significa que requiere:
- `LLM_API_KEY` configurado
- `LLM_BASE_URL` accesible
- Conexión a internet

---

## Cómo ejecutar

### Local (Windows)

```powershell
# Activar entorno virtual
.venv\Scripts\activate

# Ejecutar tests
$env:PYTHONIOENCODING = "utf-8"
python scripts\test_conversation_flows.py
```

### En el VPS (Linux)

```bash
cd /mnt/data/rodrigo-bot
python scripts/test_conversation_flows.py
```

---

## Resultado esperado

```
============================================================
🧪 TEST DE FLUJOS DE CONVERSACIÓN - CENTRO MÉDICO DEMO
============================================================

🧪 TEST 1: Greeting → Obras sociales → OSDE
   Paso 1 (Hola)          → [GREETING+BUTTONS] ...
   Paso 2 ([btn_obras])   → [INSURANCE LIST] ...
   Paso 3 ([os_osde])     → [RAG os_osde] ...

✅ PASÓ Greeting → Obras → OSDE
   loop: sin loops | id: identidad médica OK | prog: progresión OK

... (más tests) ...

============================================================
📈 RESULTADO: 8/8 tests pasaron | 0 fallos
============================================================
```

---

## Qué valida cada test

### Validaciones automáticas

| Validación | Descripción | Ejemplo de fallo |
|------------|-------------|------------------|
| **Sin loops** | La misma respuesta no se repite >2 veces | Tocar "OSDE" 3 veces y siempre recibir la lista |
| **Identidad médica** | La respuesta menciona términos del cliente | El bot dice "Soy la Secretaria Virtual de Rodrigo Rodriguez" (vieja identidad) |
| **Progresión** | Cada paso aporta información nueva | Paso 1 y 2 tienen exactamente la misma respuesta |
| **No diagnóstico** | Si hay síntomas, redirige al médico | Usuario dice "dolor de pecho" y el bot prescribe medicamento |
| **Documentos** | Para primera visita, menciona qué traer | No menciona DNI, credencial ni estudios previos |

---

## Flujos de prueba

| # | Nombre | Pasos | Qué valida |
|---|--------|-------|------------|
| 1 | **Greeting → Obras → OSDE** | Hola → Obras → OSDE | Anti-loop, info específica de OSDE |
| 2 | **Anti-loop OSDE** | Hola → Obras → OSDE x3 | Loop infinito |
| 3 | **Greeting → Precios** | Hola → Precios | Respuesta con valores de consulta |
| 4 | **Greeting → Turno** | Hola → Turno | Pide datos para agendar |
| 5 | **Servicios → Laboratorio** | "servicios" → Laboratorio | Preparación de estudios, no reenviar lista |
| 6 | **Urgencia** | "dolor de pecho" | Redirige a 107/911, no diagnóstico |
| 7 | **Primera visita** | "qué llevo primera vez" | Documentos necesarios |
| 8 | **Obra social directa** | "atienden por galeno?" → Galeno | Info específica de Galeno |

---

## Cómo agregar un nuevo test

### Paso 1: Crear el método de test

En `scripts/test_conversation_flows.py`, agregar un método en `ConversationTester`:

```python
def test_mi_nuevo_flujo(self) -> dict:
    print("\n🧪 TEST N: Mi nuevo flujo")
    phone = self._new_phone()
    steps = []
    
    # Paso 1
    result = self._send_message(phone, "Hola")
    resp = self._get_last_outbound(phone)
    steps.append({"user": "Hola", "bot_response": resp, "result": result})
    print(f"   Paso 1 (Hola)          → {result[:40]}...")
    assert "GREETING+BUTTONS" in result, "Debería enviar botones"
    
    # Paso 2
    result = self._send_message(phone, "[btn_mi_boton] Mi Botón")
    resp = self._get_last_outbound(phone)
    steps.append({"user": "[btn_mi_boton]", "bot_response": resp, "result": result})
    print(f"   Paso 2 ([btn_mi_boton]) → {result[:40]}...")
    assert "RAG" in result, "Debería responder con RAG"
    
    # Validaciones
    outbounds = self._get_all_outbounds(phone)
    ok_loop, msg_loop = self._check_loop(outbounds)
    ok_id, msg_id = self._check_identity(resp)
    
    return {
        "name": "Mi nuevo flujo",
        "passed": ok_loop and ok_id,
        "details": f"loop: {msg_loop} | id: {msg_id}",
        "steps": steps
    }
```

### Paso 2: Agregarlo a la ejecución

En `main()`, agregar el test a la lista:

```python
tests = [
    tester.test_greeting_to_osde,
    tester.test_anti_loop_osde,
    # ... otros tests ...
    tester.test_mi_nuevo_flujo,  # ← Agregar aquí
]
```

### Paso 3: Ejecutar

```bash
python scripts/test_conversation_flows.py
```

---

## Troubleshooting de tests

### "ERROR: no such table: conversation_claims"

La base de datos no está inicializada. Ejecutar:

```python
from app.db import init_db
from app.db_migrations import apply_migrations
init_db()
apply_migrations()
```

### "ASSERT FAILED: Debería enviar botones de bienvenida"

Puede ser que el mensaje se marque como duplicado. Verificar que los `message_id` sean únicos (usar `uuid.uuid4()` en tests).

### "RESPUESTA CON IDENTIDAD VIEJA (Rodrigo Rodriguez)"

El `system_prompt.txt` o `config.py` no se actualizaron correctamente. Verificar que `SYSTEM_PROMPT` tenga la identidad del nuevo cliente.

### "loop detectado"

El sistema anti-loop no está funcionando. Revisar:
1. Que `_parse_button_click()` detecta el formato `[id] Título`
2. Que los clicks de botón se procesan ANTES que las intenciones genéricas
3. Que `_was_last_outbound_a_list()` funciona correctamente

---

## Integración CI/CD

Para ejecutar tests automáticamente en cada deploy:

```bash
#!/bin/bash
# deploy.sh (fragmento)

python scripts/test_conversation_flows.py
if [ $? -ne 0 ]; then
    echo "❌ Tests fallaron. Abortando deploy."
    exit 1
fi

echo "✅ Tests pasaron. Continuando deploy..."
docker compose up -d --build
```

---

*Última actualización: 2026-06-01*
