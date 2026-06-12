# Guia: Crear Nuevo Cliente con Turnos (SaaS)

> Documento paso a paso para dar de alta un nuevo cliente en la plataforma AsistenteBot con la funcionalidad de agendamiento de turnos via WhatsApp.

---

## Resumen del Proceso

| Paso | Descripcion | Tiempo |
|------|-------------|--------|
| 1 | Crear cliente con `new_client.sh` | 2 min |
| 2 | Configurar servicios (`services.json`) | 10 min |
| 3 | Configurar horarios (`horarios.json`) | 5 min |
| 4 | Configurar Google Calendar | 5 min |
| 5 | Activar recordatorios (opcional) | 1 min |
| 6 | Reiniciar contenedores | 2 min |
| 7 | Probar conversaciones | 10 min |
| 8 | Entregar al cliente | 5 min |
| | **Total** | **~35-40 min** |

---

## Requisitos Previos

Antes de empezar, asegurate de tener:

- Acceso SSH al VPS (`ssh -i ~/.ssh/boston_vps root@167.114.96.29`)
- El `PHONE_NUMBER_ID` del numero de WhatsApp del cliente (desde Meta Developers)
- El `GOOGLE_CALENDAR_ID` del cliente (que el cliente te comparte)
- Definido el slug, dominio, nombre y telefono del cliente

---

## Paso 1: Crear el Cliente (2 minutos)

```bash
ssh -i ~/.ssh/boston_vps root@167.114.96.29
cd /mnt/data/rodrigo-bot-template

./scripts/new_client.sh \
  --name "Peluqueria Juancho" \
  --slug juancho \
  --domain "juancho.asistentebot.com.ar" \
  --phone "+54 11 3456-7890" \
  --email "contacto@juancho.com" \
  --whatsapp-mode meta \
  --meta-phone-number-id "123456789012345"
```

**Esto crea automaticamente:**
- `/mnt/data/cliente-juancho/` con todo el codigo base
- Contenedores Docker: `juancho-web`, `juancho-worker`
- `.env` con variables configuradas
- Archivos vacios: `data/services.json`, `data/horarios.json`
- Bloque en Caddyfile para el dominio
- Registro en webhook-router

---

## Paso 2: Configurar Servicios (10 minutos)

Editar el archivo:
```bash
nano /mnt/data/cliente-juancho/data/services.json
```

**Template de ejemplo:**
```json
{
  "servicios": [
    {
      "id": "corte_hombre",
      "nombre": "Corte de pelo Hombre",
      "categoria": "Cortes",
      "duracion_minutos": 30,
      "precio": 8000,
      "keywords": ["corte", "corte hombre", "pelo", "cabello", "hombre"]
    },
    {
      "id": "corte_mujer",
      "nombre": "Corte de pelo Mujer",
      "categoria": "Cortes",
      "duracion_minutos": 45,
      "precio": 12000,
      "keywords": ["corte mujer", "corte senora", "melena", "cambio de look"]
    },
    {
      "id": "tintura",
      "nombre": "Tintura",
      "categoria": "Color",
      "duracion_minutos": 90,
      "precio": 25000,
      "keywords": ["tintura", "color", "tenir", "tinte", "mechas", "reflejos"]
    },
    {
      "id": "barba",
      "nombre": "Arreglo de Barba",
      "categoria": "Barberia",
      "duracion_minutos": 20,
      "precio": 5000,
      "keywords": ["barba", "arreglo barba", "afeitado", "perfilado"]
    }
  ]
}
```

**Reglas importantes:**
- El `id` debe ser unico (sin espacios, usar guiones bajos)
- `keywords` son las palabras clave que el bot usa para detectar el servicio. Incluir sinonimos y variaciones.
- `duracion_minutos` afecta los slots disponibles en el calendario
- `precio` es solo informativo (el bot no cobra, solo muestra)

---

## Paso 3: Configurar Horarios (5 minutos)

```bash
nano /mnt/data/cliente-juancho/data/horarios.json
```

**Template:**
```json
{
  "zona_horaria": "America/Argentina/Buenos_Aires",
  "dias": {
    "lunes": { "apertura": "09:00", "cierre": "19:00", "abierto": true },
    "martes": { "apertura": "09:00", "cierre": "19:00", "abierto": true },
    "miercoles": { "apertura": "09:00", "cierre": "19:00", "abierto": true },
    "jueves": { "apertura": "09:00", "cierre": "19:00", "abierto": true },
    "viernes": { "apertura": "09:00", "cierre": "20:00", "abierto": true },
    "sabado": { "apertura": "10:00", "cierre": "14:00", "abierto": true },
    "domingo": { "abierto": false }
  },
  "duracion_turno_default": 30,
  "intervalo_minutos": 30,
  "feriados": []
}
```

**Notas:**
- `abierto: false` = cerrado (ej: domingos)
- `intervalo_minutos`: cada cuanto se ofrecen turnos (30 minutos = 09:00, 09:30, 10:00...)
- `feriados`: lista de fechas en formato "YYYY-MM-DD" donde el negocio esta cerrado

---

## Paso 4: Configurar Google Calendar (5 minutos)

### 4.1. Pedir al cliente que cree el calendario

Mandarle al cliente por WhatsApp/email:

```
Hola! Para activar los turnos automaticos necesito que hagas esto:

1. Andá a Google Calendar (calendar.google.com)
2. Crea un calendario nuevo (boton "+" > Crear calendario)
3. Nombralo: "Turnos - [Nombre del Negocio]"
4. En la configuracion del calendario, buscá "Compartir con" o "Compartir con personas especificas"
5. Agregá este email con permiso de "Hacer cambios y gestionar":
   nspa-865@guild-f42e3.iam.gserviceaccount.com
6. Guardá y pasame el "ID del calendario" (se ve en Configuracion > Integracion del calendario)
   Ejemplo: abc123@group.calendar.google.com
```

### 4.2. Ejecutar el script de setup

```bash
cd /mnt/data/rodrigo-bot-template
./scripts/setup_calendar.sh --slug juancho --calendar-id "abc123@group.calendar.google.com"
```

**Esto hace:**
- Agrega las variables `GOOGLE_CALENDAR_ID` y `GOOGLE_SERVICE_ACCOUNT_JSON` al `.env`
- Copia los archivos de config al container
- Reinicia los contenedores

---

## Paso 5: Activar Recordatorios (Opcional, 1 minuto)

```bash
nano /mnt/data/cliente-juancho/.env
```

Agregar al final:
```bash
# Recordatorios (activable por admin)
REMINDERS_ENABLED=true
REMINDER_HOURS_BEFORE=24
REMINDER_CONFIRMATION_REQUIRED=true

# Configuracion del negocio
BUSINESS_ADDRESS="Av. Siempreviva 742, Buenos Aires"
BUSINESS_NAME="Peluqueria Juancho"
```

**Opciones:**
- `REMINDERS_ENABLED`: true/false
- `REMINDER_HOURS_BEFORE`: 24, 12, 48, etc.
- `REMINDER_CONFIRMATION_REQUIRED`: si el usuario debe responder "Si" para confirmar

---

## Paso 6: Reiniciar Contenedores (2 minutos)

```bash
cd /mnt/data/cliente-juancho
docker compose down && docker compose up -d
```

**Verificar que esta levantado:**
```bash
curl https://juancho.asistentebot.com.ar/health
```

Deberia responder `{"status":"ok"}`

---

## Paso 7: Probar Conversaciones (10 minutos)

Escribir al WhatsApp del cliente desde otro celular:

### Test 1: Saludo
```
Usuario: "Hola"
Bot: [Menu con botones: Sacar turno, Servicios, Precios]
```

### Test 2: Flujo completo de turno
```
Usuario: "quiero un corte"
Bot: "Perfecto! Vamos a agendar tu Corte de pelo Hombre. ¿Para que dia?"

Usuario: "mañana"
Bot: "📅 Horarios disponibles para [fecha]:
      a) 09:00
      b) 09:30
      c) 10:00
      ..."

Usuario: "a"
Bot: "✅ 09:00 confirmado. ¿A nombre de quien?"

Usuario: "Juan Perez"
Bot: "📋 Resumen:
      📅 [fecha] a las 09:00
      💇 Corte de pelo Hombre (30 min)
      👤 Juan Perez
      ¿Confirmamos?"

Usuario: "si"
Bot: "✅ ¡Turno confirmado! Te enviaremos un recordatorio 24 horas antes."
```

### Test 3: Fecha pasada (debe rechazar)
```
Usuario: "ayer"
Bot: "No puedo agendar turnos en fechas pasadas. ¿Querés para hoy o mañana?"
```

### Test 4: Dia cerrado
```
Usuario: "domingo"
Bot: "Los domingos estamos cerrados. ¿Querés otro dia?"
```

### Test 5: Cancelar
```
Usuario: "cancelar mi turno"
Bot: "¿Que turno queres cancelar? [lista de turnos]"
```

### Test 6: Listar turnos
```
Usuario: "mis turnos"
Bot: "Estos son tus turnos confirmados: [lista]"
```

---

## Paso 8: Entregar al Cliente (5 minutos)

Mandarle por WhatsApp/email:

```
Hola [Nombre del Cliente]!

Tu Asistente Virtual esta listo 🎉

📅 Panel de administracion:
https://juancho.asistentebot.com.ar/admin

🔑 API Key: [COPIAR_DEL_OUTPUT_DEL_SCRIPT]

Desde el panel podes:
- Ver conversaciones en tiempo real
- Tomar control cuando quieras responder vos
- Liberar para que el bot siga automatico
- Ver los turnos agendados

💬 WhatsApp:
Tus clientes pueden escribir al WhatsApp y:
- Agendar turnos automaticamente
- Consultar precios
- Ver servicios
- Cancelar o reprogramar

¿Querés que te haga una prueba en vivo?
```

---

## Comandos Utiles Post-Creacion

```bash
# Ver logs
ssh -i ~/.ssh/boston_vps root@167.114.96.29
cd /mnt/data/cliente-juancho && docker compose logs -f

# Reiniciar si se modifica .env
cd /mnt/data/cliente-juancho && docker compose down && docker compose up -d

# Ver estado de todos los clientes
cd /mnt/data/rodrigo-bot-template && ./scripts/list_clients.sh

# Eliminar cliente (CUIDADO)
cd /mnt/data/rodrigo-bot-template && ./scripts/remove_client.sh --slug juancho --yes

# Agregar/cambiar servicios en caliente
cd /mnt/data/cliente-juancho
docker compose cp data/services.json web:/app/data/services.json
docker compose cp data/services.json worker:/app/data/services.json
docker compose restart worker

# Testear API
curl -X POST https://juancho.asistentebot.com.ar/ask-public \
  -H "Content-Type: application/json" \
  -d '{"question": "Hola, que servicios ofrecen?"}'
```

---

## Solucion de Problemas Comunes

### El bot no detecta los servicios
- Verificar que `services.json` tenga el formato correcto
- Copiar al container: `docker compose cp data/services.json web:/app/data/services.json`
- Reiniciar worker

### El calendario no conecta
- Verificar que `GOOGLE_CALENDAR_ID` este en el `.env`
- Verificar que el cliente compartio el calendario con la cuenta de servicio
- Probar: `docker compose exec web python -c "from app.calendar_service import is_calendar_configured; print(is_calendar_configured())"`

### El bot no inicia
- Verificar logs: `docker compose logs web`
- Verificar que `.env` no tenga errores de formato
- Verificar que todas las variables requeridas esten presentes

### Los horarios no estan bien
- Verificar `horarios.json` en el container
- Verificar que `intervalo_minutos` sea correcto

---

## Modelo de Precios Sugerido (para entregar al cliente)

| Plan | Setup (unico) | Mensual | Incluye |
|------|--------------|---------|---------|
| **Basico** | $150.000 | $80.000 | Bot, hasta 5 servicios, soporte email |
| **Pro** | $300.000 | $180.000 | Bot + Turnos + Panel admin + Human handoff, hasta 10 servicios, soporte WhatsApp |
| **Enterprise** | $500.000 | $350.000 | Todo ilimitado, recordatorios, ajustes ilimitados, soporte prioritario |

---

## Checklist de Entrega

- [ ] Cliente creado con `new_client.sh`
- [ ] `services.json` configurado con servicios reales
- [ ] `horarios.json` configurado con horarios reales
- [ ] Google Calendar conectado y funcionando
- [ ] Recordatorios activados (si el cliente lo quiere)
- [ ] Contenedores reiniciados y health check OK
- [ ] Test de conversacion completo pasado
- [ ] Panel admin entregado al cliente
- [ ] API Key entregada al cliente
- [ ] Documentacion de uso enviada al cliente

---

*Ultima actualizacion: 2026-06-11*
