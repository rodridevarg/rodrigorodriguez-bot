# Credenciales VPS - MiCita

> ⚠️ IMPORTANTE: Este archivo contiene credenciales. No compartir.

## VPS Info
- **Proveedor:** OVH
- **Hostname:** vps-cd6db2f1.vps.ovh.ca
- **IP IPv4:** 167.114.96.29
- **IP IPv6:** 2607:5300:205:200::6319
- **OS:** Ubuntu (cloud image)
- **Usuario SSH:** `ubuntu`
- **Usuario SSH alternativo:** `root` (solo para emergencias)
- **Puerto SSH:** 22

## Acceso SSH
- **Clave privada:** `~/.ssh/boston_vps`
- **Clave pública:** `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJOTg3gcejYYvpyVEQRu5TcaKSVNnCcu9zceqFnxLl3L boston-ai-deploy`
- **Autenticación:** Solo clave (sin contraseña)

## Historial de contraseñas Rescue Mode
- `J2CWjw7skxvH` (primera, usada para reiniciar)
- `7gA8B7AJ8JK6` (segunda, reinicio fallido)
- `f6LS9J7GcBGn` (tercera, reinicio fallido)
- *(Nota: OVH genera una nueva contraseña cada vez que se activa rescue mode)*

## Servicio Instalado
- **cliente-nspa** (MiCita / Herminda)
- **Dominio:** nspa.asistentebot.com.ar
- **Nota:** El VPS fue reinstalado por falta de pago. Se perdió todo y se reinstaló desde cero.

## Usuarios del Sistema
- `ubuntu` (UID 1000, home: /home/ubuntu)
- `root` (UID 0)

## Docker
- No instalado por defecto (se instala manualmente)
- Contenedores: `cliente-nspa-web` y `cliente-nspa-worker`

## Caddy
- Caddy maestro en `/mnt/data/boston-ai/Caddyfile`
- Sirve dominio `nspa.asistentebot.com.ar`

## Red Docker
- `boston-ai_default` (bridge network compartida)

## Fecha de creación
- Junio 2026
