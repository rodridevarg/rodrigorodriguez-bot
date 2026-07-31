# Arquitectura Docker - Imagen Base Compartida

> Como funciona la imagen `asistentebot-base:latest` y como mantenerla.
> Leer este archivo cuando se hable de builds, imagenes Docker, espacio en disco,
> o actualizar el codigo del bot en el VPS.

---

## TL;DR

- Todos los clientes usan la MISMA imagen: `asistentebot-base:latest` (~10.4GB).
- Los clientes NO hacen build. Levantar un cliente nuevo tarda segundos.
- Los datos de cada cliente viven en `./data` (bind mount), fuera de la imagen.
- Si cambia el codigo (`app/`, `scripts/`, `ui/`) o `requirements.txt`:
  hay que reconstruir la imagen base y recrear TODOS los clientes.

---

## Por que existe

Antes, cada cliente hacia `docker compose build` y descargaba ~2GB de librerias
(PyTorch, sentence-transformers, ChromaDB) + ~470MB del modelo de embeddings.
Con 3 clientes eran ~28GB de imagenes duplicadas y el VPS llego al 94% de disco.

Ahora:

| Concepto | Antes | Ahora |
|----------|-------|-------|
| Imagen por cliente | ~9.5GB x2 (web+worker) | Compartida (10.4GB total) |
| Build de cliente nuevo | 10-15 min | Segundos |
| Modelo de embeddings | Descarga por contenedor | Pre-descargado en la imagen |
| Datos del cliente | Volumen nombrado Docker | Bind mount `./data` (host) |

---

## Que contiene la imagen base

Construida desde `Dockerfile.base` (en la raiz del repo y en el template del VPS):

1. `python:3.11-slim` + `build-essential`
2. `pip install -r requirements.txt`
3. Modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` pre-descargado
4. Codigo: `app/`, `scripts/`, `ui/`

NO contiene: `.env`, `data/`, documentos, prompts ni nada especifico de clientes.

---

## Como se construye

En el VPS, UNA sola vez (o cuando cambie el codigo):

```bash
cd /mnt/data/rodrigo-bot-template
sudo docker build -f Dockerfile.base -t asistentebot-base:latest .
```

Tarda 15-20 minutos la primera vez. Los rebuilds aprovechan cache (~10GB de build
cache que conviene NO borrar con `docker system prune`).

> **IMPORTANTE:** Antes de buildear, sincronizar el codigo local al template:
> ```bash
> tar czf - --exclude=__pycache__ app scripts ui requirements.txt Dockerfile.base docker-compose.template.yml | \
>   ssh -i ~/.ssh/boston_vps ubuntu@167.114.96.29 \
>   "cd /mnt/data/rodrigo-bot-template && sudo tar xzf -"
> ```

---

## Como usan la imagen los clientes

Cada cliente tiene su `docker-compose.yml` generado desde `docker-compose.template.yml`:

```yaml
services:
  web:
    image: asistentebot-base:latest    # SIN build
    container_name: {slug}-web
    volumes:
      - ./data:/app/data               # datos del cliente (bind mount)
    ...
  worker:
    image: asistentebot-base:latest
    container_name: {slug}-worker
    volumes:
      - ./data:/app/data
```

- **Bind mount `./data:/app/data`**: los docs, prompts, SQLite y ChromaDB de cada
  cliente viven en `/mnt/data/cliente-{slug}/data/` del host. Se editan sin rebuild.
- Despues de editar docs: `docker compose exec web python scripts/index_documents.py`.
- Despues de editar `.env`: `docker compose down && docker compose up -d`.

---

## Flujo de actualizacion de codigo (TODOS los clientes a la vez)

> **Trade-off aceptado:** todos los clientes corren la misma version del codigo.
> No se puede actualizar un solo cliente.

1. Commit + push del codigo en el repo local.
2. Sincronizar codigo al template (comando tar de arriba).
3. Rebuild de la imagen base.
4. Recrear todos los clientes:
   ```bash
   for c in cliente-nspa cliente-boston cliente-micita-info; do
     cd /mnt/data/$c && sudo docker compose down && sudo docker compose up -d
   done
   ```
5. Health check de cada dominio.

---

## Mantenimiento del disco

| Comando | Efecto | Cuando |
|---------|--------|--------|
| `docker system df` | Ver uso | Chequeo rutinario |
| `docker builder prune -af` | Libera build cache (~10GB) | Solo si falta disco; el proximo rebuild sera lento |
| `docker image prune` | Borra imagenes dangling | Ocasional |
| `journalctl --vacuum-size=100M` | Limita logs del sistema | Si /var crece |
| `df -h /` | Ver disco total | Siempre |

NO ejecutar `docker system prune -af` a la ligera: borra el build cache de la
imagen base y el proximo rebuild tardara 15-20 minutos otra vez.

---

## Notas tecnicas

- El modelo de embeddings se guarda en `/root/.cache/huggingface` DENTRO de la
  imagen. Los contenedores corren como root, asi que lo reusan sin descargar.
- ChromaDB descarga un modelo ONNX interno (~80MB) en el primer index por
  contenedor; es efimero y no esta en la imagen base.
- La red `boston-ai_default` conecta clientes, router y Caddy.

---

*Ultima actualizacion: 2026-07-31*
