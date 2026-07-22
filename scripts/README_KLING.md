# 🎬 Kling AI Video Generator - Instrucciones

## Requisitos

- Python 3.9+ instalado
- Credenciales de Kling AI (Access Key + Secret Key)
- `this.png` (Herminda) en la raíz del proyecto
- `screenshot_whatsapp.png` (para el clip 3) - opcional

## Instalación rápida

```bash
# 1. Entrar al proyecto
cd C:\Users\rodri\desarrollos\rodrigorodriguez-bot

# 2. Activar entorno virtual (si lo tenés)
.venv\Scripts\activate

# 3. Instalar dependencias
pip install requests python-dotenv
```

## Configuración de credenciales

```bash
# 1. Copiar el template de credenciales
copy scripts\.env.example scripts\.env

# 2. Editar scripts\.env con tus credenciales reales:
# KLING_ACCESS_KEY=AbPeMynTKKGkpbEKykGCKFHQyGbRJRf9
# KLING_SECRET_KEY=Yk8t8BFaeMBMJFNPARrMTTTYLM8mJkL9
```

⚠️ **IMPORTANTE:** El archivo `.env` está en `.gitignore` y NUNCA se sube al repo.

## Uso del script

### Opción 1: Prueba con 1 clip (recomendado para empezar)
```bash
python scripts\kling_generator.py
```
Esto genera solo el **Clip 1 (Herminda saluda)**. Si sale bien, seguimos con los demás.

### Opción 2: Generar un clip específico
```bash
# Listar clips disponibles
python scripts\kling_generator.py --list

# Generar clip 2 (Herminda hechizo)
python scripts\kling_generator.py --clip 2
```

### Opción 3: Generar todos los clips
```bash
python scripts\kling_generator.py --all
```

## Resultados

Los videos se guardan en: `output/kling_videos/`
- `clip_01_herminda_saluda.mp4`
- `clip_02_herminda_hechizo.mp4`
- `clip_03_whatsapp_calendar.mp4`
- `clip_04_herminda_guino.mp4`

También se genera un log: `output/kling_videos/kling_generation.log`

## Si algo falla

1. **Revisar credenciales:** Verificá que el `.env` esté bien configurado
2. **Revisar imagen:** Asegurate de que `this.png` exista en la raíz del proyecto
3. **Revisar log:** Mirá el archivo `.log` para ver el error exacto
4. **Autenticación:** Si falla con 401, puede que la firma HMAC no sea exacta para tu cuenta. En ese caso, probá con el formato alternativo comentado en el script.

## Próximo paso: Editar en CapCut

Cuando tengas los clips:
1. Abrir CapCut Desktop
2. Importar los MP4 de `output/kling_videos/`
3. Seguir la guía: `docs/PROMPTS_VIDEO_HERMINDA.html`

## Nota sobre el Clip 3

El clip de WhatsApp → Calendar es difícil para la IA. Si Kling no lo genera bien, usá el **fallback**: armar la transición manualmente en CapCut con los screenshots de WhatsApp y Google Calendar.
