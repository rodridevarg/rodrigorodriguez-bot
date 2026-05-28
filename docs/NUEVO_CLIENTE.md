# Nuevo Cliente - Proceso por Cliente

> Lo unico que hay que hacer **CADA VEZ** que aparece un cliente nuevo.
> Asume que el setup unico ya esta hecho (ver `docs/SETUP_UNICO.md`).

---

## Checklist rapido

| # | Paso | Tiempo |
|---|------|--------|
| 1 | Comprar chip / numero para el cliente | 10 min |
| 2 | Verificar numero en Meta | 5 min |
| 3 | Ejecutar `new_client.sh` | 2 min |
| 4 | Subir documentos del cliente | 30 min |
| 5 | Probar conversaciones | 15 min |
| 6 | Entregar panel admin al cliente | 5 min |
| | **Total** | **~1 hora** |

---

## Paso 1: Obtener un numero de telefono

### Opcion A: Chip prepago (recomendado)
- Comprar chip en kiosco (~ARS 2000-5000)
- Poner en tu celular temporalmente
- Verificar en Meta (recibi SMS)
- Sacar chip, guardarlo

### Opcion B: Numero virtual (Twilio, etc.)
- Comprar numero online
- Recibir SMS por web

### Opcion C: Cliente presta su numero
- El cliente te presta su celular 5 min
- Verificas en Meta
- **Advertencia**: su WhatsApp normal deja de funcionar

---

## Paso 2: Verificar en Meta

1. Meta Business Manager → tu WABA → **Agregar numero de telefono**
2. Ingresar numero
3. Recibir SMS con codigo
4. Verificar
5. Anotar el `PHONE_NUMBER_ID` (se ve en la lista de numeros)

---

## Paso 3: Crear el cliente (un solo comando)

```bash
cd /mnt/data/rodrigo-bot-template

./scripts/new_client.sh \
  --name "Dr. Garcia" \
  --slug garcia \
  --domain "garcia.asistentebot.com.ar" \
  --phone "+54 11 1234-5678" \
  --email "contacto@drgarcia.com" \
  --meta-phone-number-id "AQUI_EL_PHONE_NUMBER_ID"
```

El script hace **todo automaticamente**:
- Crea carpeta `/mnt/data/cliente-garcia/`
- Genera `.env`, `docker-compose.yml`
- Crea documentos iniciales
- Levanta contenedores
- Registra en webhook-router
- Agrega al Caddyfile
- Recarga Caddy

**Output**: te muestra URLs, API keys y proximos pasos.

---

## Paso 4: Subir documentos del cliente

```bash
# Desde tu PC local
scp -i ~/.ssh/boston_vps ./docs_del_cliente/*.md root@167.114.96.29:/mnt/data/cliente-garcia/data/docs/

# O editar directo en el VPS
nano /mnt/data/cliente-garcia/data/docs/home.md
nano /mnt/data/cliente-garcia/data/docs/servicios.md
nano /mnt/data/cliente-garcia/data/docs/precios.md
nano /mnt/data/cliente-garcia/data/docs/faq.md
```

Luego indexar:
```bash
cd /mnt/data/cliente-garcia
docker compose exec web python scripts/index_documents.py
```

---

## Paso 5: Editar prompt (opcional)

```bash
nano /mnt/data/cliente-garcia/data/system_prompt.txt
```

Reiniciar para aplicar:
```bash
cd /mnt/data/cliente-garcia && docker compose restart
```

---

## Paso 6: Probar

```bash
# Probar API
curl -X POST https://garcia.asistentebot.com.ar/ask-public \
  -H "Content-Type: application/json" \
  -d '{"question": "Hola, que servicios ofrecen?"}'

# Probar WhatsApp
# Escribir al numero del cliente desde otro celular
```

---

## Paso 7: Entregar al cliente

Enviar por email/WhatsApp:

```
Hola Dr. Garcia,

Tu Asistente Virtual esta listo.

Panel de administracion:
https://garcia.asistentebot.com.ar/admin

API Key para el panel: [COPIAR_DEL_OUTPUT_DEL_SCRIPT]

Desde el panel podes:
- Ver conversaciones en tiempo real
- Tomar control cuando quieras responder vos mismo
- Liberar para que el bot siga automatico

Cualquier duda, escribime.
```

---

## Comandos utiles posteriores

```bash
# Ver logs
cd /mnt/data/cliente-garcia && docker compose logs -f

# Actualizar codigo (si hay nueva version del template)
cd /mnt/data/rodrigo-bot-template
./scripts/deploy_client.sh --slug garcia

# Eliminar cliente
cd /mnt/data/rodrigo-bot-template
./scripts/remove_client.sh --slug garcia
```

---

*Ultima actualizacion: 2026-05-28*
