"""
Configuración de clips para Kling AI Video Generator
MiCita - Herminda "Energía y Destino" (30 segundos)
"""

from pathlib import Path

# Rutas base
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output" / "kling_videos"
IMAGES_DIR = PROJECT_ROOT

# Crear directorio de salida si no existe
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Configuración de clips
# Cada clip genera un video que luego se une en CapCut
CLIPS = [
    {
        "id": "clip_01_herminda_saluda",
        "nombre": "Herminda Saluda",
        "imagen": IMAGES_DIR / "this.png",
        "prompt": (
            "The witch character smiles warmly and waves her hand in greeting. "
            "She slightly tilts her head. Soft purple magical particles float around her. "
            "Lavender gradient background. 3D Pixar animation, subtle motion, cinematic lighting."
        ),
        "duration": 5,  # segundos
        "aspect_ratio": "9:16",
        "negative_prompt": "deformed face, blurry, distorted, extra fingers, bad anatomy",
    },
    {
        "id": "clip_02_herminda_hechizo",
        "nombre": "Herminda Lanzando Hechizo",
        "imagen": IMAGES_DIR / "this.png",
        "prompt": (
            "The witch character raises her hand and makes a magical gesture. "
            "Sparkling purple magic swirls from her fingers. "
            "A glowing smartphone screen appears in front of her showing WhatsApp messages. "
            "She looks at the phone with a satisfied smirk. Dynamic magical effects, cinematic lighting."
        ),
        "duration": 7,
        "aspect_ratio": "9:16",
        "negative_prompt": "deformed face, blurry, distorted, extra fingers, bad anatomy",
    },
    {
        "id": "clip_03_whatsapp_calendar",
        "nombre": "WhatsApp a Calendar",
        "imagen": IMAGES_DIR / "screenshot_whatsapp.png",
        "imagen_tail": IMAGES_DIR / "screenshot_calendar.png",
        "prompt": (
            "Smooth transition from WhatsApp conversation to Google Calendar event. "
            "The chat messages morph into a confirmed appointment. "
            "Clean UI, soft purple glow, modern interface."
        ),
        "duration": 7,
        "aspect_ratio": "9:16",
        "negative_prompt": "blurry, distorted, low quality, extra hands, fingers",
        "fallback": True,
    },
    {
        "id": "clip_04_herminda_guino",
        "nombre": "Herminda Guiño",
        "imagen": IMAGES_DIR / "this.png",
        "prompt": (
            "The witch character winks playfully, gives a thumbs-up, and blows a small magical sparkle. "
            "The purple lotus logo glows behind her. Soft confetti particles fall. "
            "Friendly expression, happy ending feel, cinematic lighting."
        ),
        "duration": 5,
        "aspect_ratio": "9:16",
        "negative_prompt": "deformed face, blurry, distorted, extra fingers, bad anatomy",
    },
]

# Configuración de la API
KLING_API_CONFIG = {
    "base_url": "https://api-singapore.klingai.com",
    "api_version": "v1",
    "endpoint": "videos/image2video",
    "model": "kling-v2-6",  # Modelo recomendado para consistencia de personaje
    "mode": "pro",  # Modo pro para mejor calidad (720p=std, 1080p=pro, 4k=4k)
    "max_retries": 3,
    "retry_delay": 5,  # segundos entre reintentos
    "polling_interval": 10,  # segundos entre consultas de estado
    "max_polling_time": 300,  # 5 minutos máximo de espera
}

# Configuración de logging
LOG_CONFIG = {
    "filename": OUTPUT_DIR / "kling_generation.log",
    "format": "%(asctime)s [%(levelname)s] %(message)s",
    "datefmt": "%Y-%m-%d %H:%M:%S",
}
