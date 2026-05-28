# PLAN: Secretaría Virtual Multi-Cliente
## Producto SaaS white-label para WhatsApp Business

---

## 1. Resumen Ejecutivo

Convertir el bot actual de Rodrigo Rodríguez en una **plataforma replicable** para ofrecer asistentes virtuales por WhatsApp a cualquier negocio (médicos, tiendas, servicios, etc.).

**Modelo de negocio:** Fee de setup + mensualidad recurrente.
**Arquitectura:** Una instancia Docker aislada por cliente.
**WhatsApp:** WABA propia con múltiples números (Opción B).
**Dominios:** Subdominios de un dominio genérico.

---

## 2. Decisiones de Arquitectura

| Aspecto | Decisión | Justificación |
|---------|----------|---------------|
| **Arquitectura** | Instancia por cliente (multi-instance) | Aislamiento total, falla de un cliente no afecta a otros, fácil de escalar |
| **WABA** | Mi WABA, múltiples números | Setup inmediato (15 min vs 15 días), cliente no hace trámites con Meta |
| **Dominios** | Subdominios propios | Branding consistente, un solo certificado SSL, control total |
| **Base de datos** | SQLite por instancia | Simple, no requiere servidor de DB, suficiente para 1 cliente |
| **Vector Store** | ChromaDB por instancia | Aislado, sin mezcla de conocimiento entre clientes |
| **Panel admin** | Por instancia | Cada cliente accede solo a sus conversaciones |
| **Deploy** | Scripts automatizados | Crear cliente en minutos, no horas |

---

## 3. Estructura en el VPS

```
/mnt/data/
├── boston-ai/                    # Caddy maestro + aibrain (existente, NO TOCAR)
│   └── Caddyfile                 # Se agrega un bloque por cada nuevo cliente
│
├── rodrigo-bot/                  # Bot original de Rodrigo (queda como está)
│   ├── docker-compose.yml
│   └── ...
│
├── cliente-{slug}/               # Template por cada nuevo cliente
│   ├── docker-compose.yml        # Contenedores con nombre único
│   ├── .env                      # Variables del cliente
│   ├── Dockerfile                # Igual para todos
│   ├── requirements.txt          # Igual para todos
│   ├── app/                      # Código Python (copia del template)
│   ├── ui/                       # Chat web + admin (copia del template)
│   ├── scripts/                  # run_worker.py, etc.
│   └── data/
│       ├── docs/                 # Documentos del cliente (markdown)
│       │   ├── faq.md
│       │   ├── servicios.md
│       │   ├── precios.md
│       │   └── ...
│       ├── system_prompt.txt     # Prompt de la IA para este cliente
│       └── app.sqlite3           # Base de datos SQLite (generada al inicio)
│
└── ... (otros clientes)
```

---

## 4. Fases de Implementación

### FASE 0: Infraestructura Base (1-2 días)

| Tarea | Descripción | Entregable |
|-------|-------------|------------|
| **0.1 Dominio genérico** | Comprar dominio para subdominios (`asistentebot.com.ar`) | Dominio activo en Cloudflare |
| **0.2 DNS Wildcard** | Configurar `*.tudominio.com` → IP del VPS | Subdominios funcionan automáticamente |
| **0.3 Evaluar VPS** | Revisar disco, RAM, CPU actuales | Saber cuántos clientes caben hoy |
| **0.4 Plan de escalado** | Definir cuándo migrar a VPS más grande o múltiples VPS | Documento de escalabilidad |

---

### FASE 1: Parametrizar el Template (3-4 días)

**Objetivo:** Convertir el código actual en un template 100% genérico.

| Archivo | Cambio |
|---------|--------|
| `app/config.py` | Agregar: `BOT_NAME`, `BOT_DESCRIPTION`, `FALLBACK_MESSAGE`, `CONTACT_PHONE`, `CONTACT_EMAIL`, `SYSTEM_PROMPT_PATH`, `COLLECTION_NAME` |
| `app/rag_service.py` | Leer `SYSTEM_PROMPT` desde archivo en vez de hardcodear. Usar `FALLBACK_MESSAGE` configurable |
| `app/vector_store.py` | Usar `COLLECTION_NAME` desde config (ej. `docs_{slug}`) |
| `app/whatsapp_service.py` | Usar `CONTACT_PHONE` y `FALLBACK_MESSAGE` del config |
| `app/main.py` | Título de FastAPI = `BOT_NAME`. Eliminar referencias a "Rodrigo" |
| `ui/index.html` | Cargar `BOT_NAME` dinámicamente (endpoint `/config` o inyección en build) |
| `ui/admin/index.html` | Usar `BOT_NAME` en branding |
| `.env.example` | Limpiar, dejar variables genéricas documentadas |
| `data/system_prompt.txt` (nuevo) | Archivo de prompt editable por cliente |
| `data/docs/README.md` (nuevo) | Instrucciones para el operador sobre qué documentos subir |

---

### FASE 2: Scripts de Automatización (2-3 días)

#### 2.1 `scripts/new_client.sh`

Crea un nuevo cliente desde cero.

```bash
./scripts/new_client.sh \
  --name "Dr. García" \
  --slug "medico" \
  --domain "garcia.asistentebot.com.ar" \
  --port 8002 \
  --phone "+54 11 1234-5678"
```

**Pasos del script:**
1. Verificar slug único y puerto disponible
2. Crear `/mnt/data/cliente-{slug}/`
3. Copiar código base (app/, ui/, scripts/, Dockerfile, requirements.txt)
4. Generar `.env` con valores del cliente
5. Generar `docker-compose.yml` con nombres únicos de contenedores y puerto
6. Crear `data/docs/` con plantillas vacías
7. Crear `data/system_prompt.txt` con prompt genérico
8. Agregar bloque al Caddyfile de aibrain
9. Recargar Caddy
10. Levantar contenedores con `docker compose up -d --build`
11. Mostrar resumen: URLs, API key, checklist de siguiente pasos

#### 2.2 `scripts/deploy_client.sh`

Actualiza código de un cliente existente (nueva versión del template).

```bash
./scripts/deploy_client.sh --slug medico
```

**Pasos:** Backup de .env y data/, copiar archivos actualizados, restaurar configuración, rebuild.

#### 2.3 `scripts/remove_client.sh`

Elimina un cliente completamente.

```bash
./scripts/remove_client.sh --slug medico
```

**Pasos:** Confirmación, detener contenedores, eliminar volumen, borrar directorio, limpiar Caddyfile.

#### 2.4 `scripts/list_clients.sh`

Lista todos los clientes activos con estado.

---

### FASE 3: Documentación Operativa (1-2 días)

#### Para el operador (vos)

| Documento | Contenido |
|-----------|-----------|
| `docs/OPERADOR.md` | Cómo crear cliente, subir documentos, editar prompt, deployar, backup, escalar |
| `docs/TROUBLESHOOTING.md` | Errores comunes y soluciones paso a paso |
| `docs/CHECKLIST_ENTREGA.md` | Lista de verificación antes de entregar a un cliente |

#### Para el cliente

| Documento | Contenido |
|-----------|-----------|
| `docs/ONBOARDING_CLIENTE.md` | Qué información necesitás de ellos (FAQ, precios, servicios, horarios, tono) |
| `docs/PLANTILLAS/medico.md` | Ejemplo de documentación para un consultorio médico |
| `docs/PLANTILLAS/tienda.md` | Ejemplo para una tienda online |
| `docs/PLANTILLAS/servicios.md` | Ejemplo para un servicio profesional |

---

### FASE 4: Cliente Piloto (1 semana)

| Día | Actividad |
|-----|-----------|
| **1** | Ejecutar `new_client.sh` para el primer cliente real |
| **2** | Recopilar información del cliente (usar `ONBOARDING_CLIENTE.md`) |
| **3** | Subir documentos, editar prompt, ajustar al rubro |
| **4** | Testear 10-15 conversaciones, corregir errores |
| **5** | Entregar panel admin al cliente, capacitación básica |
| **6** | Monitorear, ajustes finales |
| **7** | Cobrar setup + primer mes, documentar aprendizajes |

---

### FASE 5: Ventas y Crecimiento (continuo)

#### Modelo de precios (ARS, sugerido)

| Plan | Setup (único) | Mensual | Incluye |
|------|--------------|---------|---------|
| **Básico** | $150.000 | $80.000 | Bot, hasta 5 documentos, soporte email |
| **Pro** | $300.000 | $180.000 | Bot + Panel admin + Human handoff, hasta 10 docs, soporte WhatsApp |
| **Enterprise** | $500.000 | $350.000 | Todo ilimitado, reportes mensuales, ajustes ilimitados, soporte prioritario |

#### Proceso de venta

1. **Contacto** → Explicar el servicio
2. **Demo gratuita** → 3-5 días de prueba con su información real
3. **Propuesta** → Enviar precio y alcance
4. **Setup** → Cobrar fee, ejecutar `new_client.sh`
5. **Entrega** → Panel admin, dominio, API key
6. **Soporte** → Primer mes con ajustes ilimitados

---

## 5. Recursos Compartidos vs Aislados

| Recurso | ¿Compartido? | Notas |
|---------|-------------|-------|
| **Caddy maestro** | ✅ Sí | Único reverse proxy. Agregar bloque por cliente |
| **Red Docker** | ✅ Sí | `boston-ai_default`. Todos los webs se conectan |
| **VPS / IP** | ✅ Sí | Mismo servidor hasta que se llene |
| **Imagen Docker** | ✅ Sí | Se construye con cache |
| **LLM API Key** | ✅ Sí (opcional) | Misma cuenta de OpenCode para todos |
| **Base de datos** | ❌ No | Cada cliente tiene su SQLite |
| **Documentos** | ❌ No | `data/docs/` por cliente |
| **Prompt de sistema** | ❌ No | `system_prompt.txt` por cliente |
| **WhatsApp número** | ❌ No | Cada cliente = número distinto |
| **Dominio** | ❌ No | Subdominio único por cliente |

---

## 6. Limitaciones y Consideraciones

| Limitación | Mitigación |
|------------|-----------|
| **Meta permite ~10-20 números por WABA** | Pedir ampliación a Meta cuando se acerque el límite |
| **Si Meta bloquea mi WABA, caen todos** | Cumplir estrictamente políticas de Meta, no spamear |
| **El nombre en WhatsApp es mi empresa** | Configurar display name por número (posible en Meta) |
| **VPS se llena con muchos clientes** | Monitorear `df -h`, migrar clientes a VPS nuevo cuando llegue al 80% |
| **Cada instancia consume RAM** | ~300MB por cliente. Planificar capacidad |

---

## 7. Checklist para empezar

- [ ] Comprar dominio genérico
- [ ] Configurar DNS wildcard en Cloudflare
- [ ] Revisar capacidad del VPS actual
- [ ] Renombrar repo actual a nombre genérico (opcional)
- [ ] Implementar FASE 1 (parametrizar template)
- [ ] Implementar FASE 2 (scripts de automatización)
- [ ] Escribir documentación operativa
- [ ] Encontrar primer cliente piloto
- [ ] Ejecutar `new_client.sh` con cliente real
- [ ] Validar, ajustar, documentar aprendizajes
- [ ] Definir precios finales
- [ ] Preparar material de ventas

---

## 8. Próximos pasos inmediatos

1. **Confirmar este plan** (ajustar lo que sea necesario)
2. **Definir prioridad:** ¿FASE 0 (infra) primero o FASE 1 (código) primero?
3. **Asignar fechas reales** a cada fase
4. **Empezar implementación**

---

*Plan creado: 2026-05-27*
*Estado: BORRADOR - Pendiente de confirmación para ejecutar*