# Guia del Operador - Bot Multi-Cliente

> Este documento es para **vos** (el que opera la plataforma). Contiene todo lo que necesitas para crear clientes, deployar, hacer backup y escalar.

---

## Tabla de contenidos

1. [Arquitectura](#arquitectura)
2. [Crear un nuevo cliente](#crear-un-nuevo-cliente)
3. [Subir documentos de un cliente](#subir-documentos-de-un-cliente)
4. [Editar el prompt del sistema](#editar-el-prompt-del-sistema)
5. [Actualizar codigo de un cliente](#actualizar-codigo-de-un-cliente)
6. [Eliminar un cliente](#eliminar-un-cliente)
7. [Backup y restauracion](#backup-y-restauracion)
8. [Escalar (mas clientes o mas VPS)](#escalar)
9. [Comandos utiles](#comandos-utiles)

---

## Arquitectura

Cada cliente tiene **su propia instancia Docker aislada**:

```
/mnt/data/
├── boston-ai/                    # Caddy maestro + aibrain (NO TOCAR)
│   └── Caddyfile                 # Se agrega un bloque por cliente
│
├── cliente-{slug}/               # Una carpeta por cliente
│   ├── docker-compose.yml        # Contenedores con nombre unico
│   ├── .env                      # Variables del cliente
│   ├── app/                      # Codigo Python
│   ├── ui/                       # Chat web + admin
│   ├── scripts/                  # Utilitarios
│   └── data/
│       ├── docs/                 # Documentos del cliente (markdown)
│       ├── system_prompt.txt     # Prompt de la IA
│       └── app.sqlite3           # Base de datos SQLite
│
└── rodrigo-bot-template/         # Codigo base (este repo clonado en VPS)
```

Recursos compartidos:
- **Caddy maestro** (`boston-ai/Caddyfile`) — unico reverse proxy HTTPS
- **Red Docker** (`boston-ai_default`) — todos los webs se conectan
- **LLM API Key** (opcional) — misma cuenta de OpenCode para todos

Recursos aislados por cliente:
- Base de datos SQLite
- Documentos y embeddings ChromaDB
- Prompt de sistema
- Numero de WhatsApp
- Subdominio propio

---

## Crear un nuevo cliente

### Pre-requisitos

1. Tener acceso al VPS (SSH)
2. Tener el template en `/mnt/data/rodrigo-bot-template/`:
   ```bash
   cd /mnt/data
   git clone https://github.com/rodridevarg/rodrigorodriguez-bot.git rodrigo-bot-template
   ```
3. Tener aibrain levantado (la red `boston-ai_default` debe existir)
4. Tener el dominio configurado en Cloudflare con DNS wildcard

### Comando

```bash
cd /mnt/data/rodrigo-bot-template
./scripts/new_client.sh \
  --name "Dr. Garcia" \
  --slug medico \
  --domain "garcia.asistente.ai" \
  --phone "+54 11 1234-5678" \
  --email "contacto@drgarcia.com" \
  --bot-name "Asistente del Dr. Garcia" \
  --whatsapp-mode fake
```

### Args disponibles

| Arg | Requerido | Descripcion |
|-----|-----------|-------------|
| `--name` | Si | Nombre del negocio |
| `--slug` | Si | Identificador unico (ej: `medico`, `tienda-juan`) |
| `--domain` | Si | Subdominio completo (ej: `garcia.asistente.ai`) |
| `--phone` | Si | Telefono de contacto del negocio |
| `--email` | No | Email de contacto |
| `--bot-name` | No | Nombre del bot (default: "Asistente Virtual de {name}") |
| `--description` | No | Descripcion del bot |
| `--collection` | No | Nombre coleccion ChromaDB (default: `{slug}_docs`) |
| `--llm-key` | No | API Key LLM (default: del template) |
| `--llm-url` | No | URL base LLM (default: del template) |
| `--llm-model` | No | Modelo LLM (default: del template) |
| `--whatsapp-mode` | No | `fake` o `meta` (default: `fake`) |
| `--meta-phone-number-id` | No | ID del numero en Meta (si modo=meta) |
| `--admin-key` | No | API Key panel admin (generada aleatoriamente) |

### Output del script

El script crea:
- Carpeta `/mnt/data/cliente-{slug}/`
- Contenedores `{slug}-web` y `{slug}-worker`
- Volumen Docker `{slug}-data`
- Bloque en el Caddyfile para HTTPS
- Archivos `.env`, `data/docs/`, `data/system_prompt.txt`

Y muestra al final:
- URLs del cliente
- API Keys (guardar en lugar seguro)
- Proximos pasos

---

## Subir documentos de un cliente

Los documentos van en `cliente-{slug}/data/docs/` como archivos `.md` (Markdown).

### Pasos

1. Subir o editar archivos:
   ```bash
   # Opcion A: SCP desde tu PC local
   scp -i ~/.ssh/boston_vps ./docs_del_cliente/*.md root@vps:/mnt/data/cliente-medico/data/docs/

   # Opcion B: Editar directo en el VPS
   nano /mnt/data/cliente-medico/data/docs/faq.md
   ```

2. Reindexar:
   ```bash
   cd /mnt/data/cliente-medico
   docker compose exec web python scripts/index_documents.py
   ```

3. Probar:
   ```bash
   curl -X POST https://garcia.asistente.ai/ask-public \
     -H "Content-Type: application/json" \
     -d '{"question": "Cuales son los servicios?"}'
   ```

### Estructura recomendada de documentos

| Archivo | Contenido |
|---------|-----------|
| `home.md` | Presentacion general |
| `servicios.md` | Servicios/productos, descripciones |
| `precios.md` | Precios, planes, pagos |
| `faq.md` | Preguntas frecuentes |
| `horarios.md` | Dias y horarios |
| `contacto.md` | Direccion, email, telefono, redes |
| `proceso.md` | Como contratar, pasos, tiempos |

Ver `data/docs/README.md` en el template para reglas de formato.

---

## Editar el prompt del sistema

El prompt define la personalidad y reglas de la IA.

```bash
nano /mnt/data/cliente-medico/data/system_prompt.txt
```

Despues de editar, **no hace falta reindexar**, pero **si reiniciar los contenedores** para que el cambio surta efecto:

```bash
cd /mnt/data/cliente-medico && docker compose down && docker compose up -d
```

### Tips para un buen prompt

- Defini claramente el rol del bot ("Sos el asistente de...")
- Indica el tono (formal, casual, tecnico)
- Especifica que NO debe inventar precios ni promesas
- Menciona el idioma (espanol)
- Incluye instrucciones especificas del rubro si aplica

---

## Actualizar codigo de un cliente

Cuando hay una nueva version del template (bug fixes, features):

```bash
cd /mnt/data/rodrigo-bot-template
./scripts/deploy_client.sh --slug medico
```

Esto:
1. Hace backup de `.env` y `data/`
2. Copia el codigo actualizado
3. Restaura la configuracion
4. Rebuild y levanta contenedores

Para actualizar **todos los clientes**:

```bash
for d in /mnt/data/cliente-*/; do
    slug=$(basename "$d" | sed 's/cliente-//')
    echo "=== Actualizando $slug ==="
    ./scripts/deploy_client.sh --slug "$slug"
done
```

---

## Eliminar un cliente

```bash
cd /mnt/data/rodrigo-bot-template
./scripts/remove_client.sh --slug medico
```

Te pedira confirmacion escribiendo el slug.

Para eliminar sin confirmacion (cuidado):
```bash
./scripts/remove_client.sh --slug medico --yes
```

---

## Backup y restauracion

### Backup manual de un cliente

```bash
SLUG=medico
BACKUP_FILE="/mnt/backups/cliente-${SLUG}-$(date +%Y%m%d).tar.gz"

mkdir -p /mnt/backups
cd /mnt/data/cliente-${SLUG}

# Detener para backup consistente
docker compose down

# Comprimir todo
tar -czf "$BACKUP_FILE" .

# Volver a levantar
docker compose up -d

echo "Backup en: $BACKUP_FILE"
```

### Restaurar desde backup

```bash
SLUG=medico
BACKUP_FILE="/mnt/backups/cliente-medico-20260115.tar.gz"

# Eliminar actual si existe
rm -rf /mnt/data/cliente-${SLUG}

# Extraer backup
mkdir -p /mnt/data/cliente-${SLUG}
tar -xzf "$BACKUP_FILE" -C /mnt/data/cliente-${SLUG}/

# Levantar
cd /mnt/data/cliente-${SLUG}
docker compose up -d
```

### Backup automatico (cron)

```bash
# Editar crontab
crontab -e

# Backup diario a las 3 AM
0 3 * * * cd /mnt/data && for d in cliente-*/; do tar -czf "/mnt/backups/${d%/}-$(date +\%Y\%m\%d).tar.gz" "$d"; done
```

---

## Escalar

### Cuando el VPS se llena

Monitoreo semanal:
```bash
./scripts/check_vps.sh
```

**Umbrales de accion:**

| Indicador | Accion |
|-----------|--------|
| Disco > 80% | Limpiar logs, eliminar backups viejos, o migrar clientes |
| RAM disponible < 500MB | Ampliar VPS o migrar clientes a otro VPS |
| > 15-20 clientes en un VPS | Dividir en 2 VPS |

### Migrar un cliente a otro VPS

1. **En VPS origen:**
   ```bash
   cd /mnt/data/cliente-medico
   docker compose down
   tar -czf /tmp/medico.tar.gz .
   ```

2. **Transferir al nuevo VPS:**
   ```bash
   scp /tmp/medico.tar.gz root@nuevo-vps:/mnt/data/
   ```

3. **En VPS destino:**
   ```bash
   mkdir -p /mnt/data/cliente-medico
   tar -xzf /mnt/data/medico.tar.gz -C /mnt/data/cliente-medico/
   cd /mnt/data/cliente-medico
   docker compose up -d
   ```

4. **Actualizar DNS** del subdominio a la nueva IP.

5. **En VPS origen:**
   ```bash
   ./scripts/remove_client.sh --slug medico --yes
   ```

---

## Comandos utiles

```bash
# Listar clientes
./scripts/list_clients.sh

# Logs de un cliente
cd /mnt/data/cliente-medico && docker compose logs -f

# Logs solo del web
cd /mnt/data/cliente-medico && docker compose logs -f web

# Logs solo del worker
cd /mnt/data/cliente-medico && docker compose logs -f worker

# Entrar al contenedor
cd /mnt/data/cliente-medico && docker compose exec web bash

# Ver base de datos SQLite
cd /mnt/data/cliente-medico && docker compose exec web sqlite3 /app/data/app.sqlite3

# Reiniciar un cliente (down+up para leer .env modificado)
cd /mnt/data/cliente-medico && docker compose down && docker compose up -d

# Ver estado de Caddy
cd /mnt/data/boston-ai && docker compose logs -f caddy

# Recargar Caddy manualmente
cd /mnt/data/boston-ai && docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

---

*Ultima actualizacion: 2026-05-28*
