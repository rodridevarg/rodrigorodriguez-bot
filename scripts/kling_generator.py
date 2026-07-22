#!/usr/bin/env python3
"""
Kling AI Video Generator - Script para MiCita
Genera videos automáticamente usando la API de Kling AI

Uso:
    1. Copiar scripts/.env.example a scripts/.env y completar credenciales
    2. Ejecutar: python scripts/kling_generator.py
    3. Los videos se guardan en output/kling_videos/

Notas:
    - Este script solo genera el Clip 1 (Herminda saluda) como prueba
    - Si funciona bien, descomentar los demás clips en config.py
    - El clip 3 (WhatsApp → Calendar) probablemente necesite fallback manual
"""

import os
import sys
import time
import base64
import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Verificar dependencias
try:
    import requests
    from dotenv import load_dotenv
    import jwt
except ImportError:
    print("❌ Error: Faltan dependencias.")
    print("Instalá con: pip install requests python-dotenv pyjwt")
    sys.exit(1)

# Cargar variables de entorno
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    print(f"⚠️  No se encontró .env en {env_path}")
    print("Copiá .env.example a .env y completá tus credenciales")
    sys.exit(1)

# Importar configuración
sys.path.insert(0, str(Path(__file__).parent))
from config import CLIPS, KLING_API_CONFIG, LOG_CONFIG, OUTPUT_DIR


class KlingAuth:
    """Maneja la autenticación JWT para Kling AI API"""
    
    def __init__(self, access_key: str, secret_key: str):
        self.access_key = access_key
        self.secret_key = secret_key
    
    def generate_jwt_token(self) -> str:
        """Genera token JWT según documentación de Kling AI"""
        # Según la documentación:
        # Header: {"alg": "HS256", "typ": "JWT"}
        # Payload: {"iss": access_key, "exp": now+1800, "nbf": now-5}
        # Token: jwt.encode(payload, secret_key, headers=headers)
        
        now = int(time.time())
        
        headers = {
            "alg": "HS256",
            "typ": "JWT"
        }
        
        payload = {
            "iss": self.access_key,
            "exp": now + 1800,  # Valido por 30 minutos
            "nbf": now - 5     # Valido desde 5 segundos antes
        }
        
        token = jwt.encode(payload, self.secret_key, headers=headers)
        return token
    
    def get_headers(self) -> Dict[str, str]:
        """Retorna headers de autenticación para cada request"""
        api_token = self.generate_jwt_token()
        
        # Formato: Authorization: Bearer <token>
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_token}",
            "User-Agent": "MiCita-Kling-Generator/1.0"
        }


class KlingVideoGenerator:
    """Generador de videos usando Kling AI API"""
    
    def __init__(self):
        self.access_key = os.getenv("KLING_ACCESS_KEY")
        self.secret_key = os.getenv("KLING_SECRET_KEY")
        self.base_url = os.getenv("KLING_BASE_URL", KLING_API_CONFIG["base_url"])
        
        if not self.access_key or not self.secret_key:
            raise ValueError(
                "Faltan credenciales. Verificá que .env tenga:\n"
                "KLING_ACCESS_KEY=tu_access_key\n"
                "KLING_SECRET_KEY=tu_secret_key"
            )
        
        self.auth = KlingAuth(self.access_key, self.secret_key)
        self.session = requests.Session()
        self.setup_logging()
    
    def setup_logging(self):
        """Configura logging a archivo"""
        logging.basicConfig(
            level=logging.INFO,
            format=LOG_CONFIG["format"],
            datefmt=LOG_CONFIG["datefmt"],
            handlers=[
                logging.FileHandler(LOG_CONFIG["filename"], encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def encode_image_to_base64(self, image_path: Path) -> str:
        """Convierte imagen a base64 para enviar a la API (sin prefijo data:image)"""
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    
    def submit_video_task(self, clip_config: Dict[str, Any]) -> Optional[str]:
        """
        Envía tarea de generación de video a Kling AI
        Retorna task_id si tiene éxito, None si falla
        """
        image_path = clip_config["imagen"]
        
        if not image_path.exists():
            self.logger.error(f"❌ Imagen no encontrada: {image_path}")
            return None
        
        self.logger.info(f"📸 Codificando imagen: {image_path.name}")
        image_base64 = self.encode_image_to_base64(image_path)
        
        # Preparar payload (según documentación de Kling AI)
        # Nota: image_base64 ya viene sin prefijo (ver función encode_image_to_base64)
        payload = {
            "model_name": KLING_API_CONFIG["model"],
            "prompt": clip_config["prompt"],
            "image": image_base64,
            "duration": str(clip_config["duration"]),
            "aspect_ratio": clip_config["aspect_ratio"],
            "negative_prompt": clip_config["negative_prompt"],
        }
        
        # Si hay imagen_tail (para transiciones first_frame → last_frame)
        if "imagen_tail" in clip_config and clip_config["imagen_tail"]:
            image_tail_path = clip_config["imagen_tail"]
            if image_tail_path.exists():
                self.logger.info(f"📸 Codificando imagen tail: {image_tail_path.name}")
                image_tail_base64 = self.encode_image_to_base64(image_tail_path)
                payload["image_tail"] = image_tail_base64
            else:
                self.logger.warning(f"⚠️  imagen_tail no encontrada: {image_tail_path}")
        
        # Construir URL
        endpoint = f"{self.base_url}/{KLING_API_CONFIG['api_version']}/{KLING_API_CONFIG['endpoint']}"
        
        self.logger.info(f"🚀 Enviando tarea a Kling AI: {clip_config['nombre']}")
        self.logger.info(f"   Prompt: {clip_config['prompt'][:60]}...")
        
        # Intentar con reintentos
        for attempt in range(KLING_API_CONFIG["max_retries"]):
            try:
                headers = self.auth.get_headers()
                response = self.session.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    task_id = data.get("data", {}).get("task_id")
                    if task_id:
                        self.logger.info(f"✅ Tarea creada: {task_id}")
                        return task_id
                    else:
                        self.logger.error(f"⚠️  No se encontró task_id en respuesta: {data}")
                        return None
                
                elif response.status_code == 401:
                    self.logger.error("❌ Error de autenticación. Verificá tus credenciales en .env")
                    self.logger.error(f"   Respuesta: {response.text}")
                    return None
                
                elif response.status_code == 429:
                    self.logger.warning(f"⏳ Rate limit. Esperando {KLING_API_CONFIG['retry_delay']}s...")
                    time.sleep(KLING_API_CONFIG["retry_delay"])
                
                else:
                    self.logger.error(f"❌ Error HTTP {response.status_code}: {response.text}")
                    if attempt < KLING_API_CONFIG["max_retries"] - 1:
                        time.sleep(KLING_API_CONFIG["retry_delay"])
            
            except requests.exceptions.RequestException as e:
                self.logger.error(f"❌ Error de conexión: {e}")
                if attempt < KLING_API_CONFIG["max_retries"] - 1:
                    time.sleep(KLING_API_CONFIG["retry_delay"])
        
        return None
    
    def check_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta el estado de una tarea de video
        Retorna dict con info si está completada, None si falla
        """
        endpoint = f"{self.base_url}/{KLING_API_CONFIG['api_version']}/videos/{task_id}"
        
        try:
            headers = self.auth.get_headers()
            response = self.session.get(endpoint, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {})
            else:
                self.logger.error(f"❌ Error consultando estado: {response.status_code}")
                return None
        
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Error consultando estado: {e}")
            return None
    
    def wait_for_completion(self, task_id: str, clip_name: str) -> Optional[str]:
        """
        Espera a que la tarea se complete (polling)
        Retorna URL del video si tiene éxito, None si falla
        """
        self.logger.info(f"⏳ Esperando generación de: {clip_name}")
        
        start_time = time.time()
        elapsed = 0
        
        while elapsed < KLING_API_CONFIG["max_polling_time"]:
            status_data = self.check_task_status(task_id)
            
            if not status_data:
                self.logger.warning("⚠️  No se pudo obtener estado. Reintentando...")
                time.sleep(KLING_API_CONFIG["polling_interval"])
                elapsed = time.time() - start_time
                continue
            
            status = status_data.get("status", "unknown")
            self.logger.info(f"   Estado: {status} ({int(elapsed)}s)")
            
            if status == "completed" or status == "success":
                video_url = status_data.get("video_url") or status_data.get("result", {}).get("video_url")
                if video_url:
                    self.logger.info(f"✅ Video generado: {video_url[:60]}...")
                    return video_url
                else:
                    self.logger.error("❌ Estado 'completed' pero no hay video_url")
                    return None
            
            elif status == "failed" or status == "error":
                error_msg = status_data.get("error", "Sin detalle")
                self.logger.error(f"❌ Tarea fallida: {error_msg}")
                return None
            
            # Estados: pending, processing, queuing...
            time.sleep(KLING_API_CONFIG["polling_interval"])
            elapsed = time.time() - start_time
        
        self.logger.error(f"⏱️  Timeout después de {KLING_API_CONFIG['max_polling_time']}s")
        return None
    
    def download_video(self, video_url: str, output_path: Path) -> bool:
        """
        Descarga el video generado
        Retorna True si tiene éxito
        """
        self.logger.info(f"📥 Descargando video a: {output_path}")
        
        try:
            response = self.session.get(video_url, stream=True, timeout=60)
            
            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                file_size = output_path.stat().st_size
                self.logger.info(f"✅ Descargado: {output_path} ({file_size / 1024:.1f} KB)")
                return True
            else:
                self.logger.error(f"❌ Error descargando: HTTP {response.status_code}")
                return False
        
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Error descargando: {e}")
            return False
    
    def generate_clip(self, clip_config: Dict[str, Any]) -> Optional[Path]:
        """
        Pipeline completo para generar un clip:
        1. Subir imagen
        2. Crear tarea
        3. Esperar completitud
        4. Descargar
        
        Retorna Path del archivo descargado o None
        """
        clip_name = clip_config["nombre"]
        clip_id = clip_config["id"]
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"🎬 GENERANDO CLIP: {clip_name}")
        self.logger.info(f"{'='*60}")
        
        # Paso 1: Crear tarea
        task_id = self.submit_video_task(clip_config)
        if not task_id:
            self.logger.error(f"❌ No se pudo crear tarea para {clip_name}")
            return None
        
        # Paso 2: Esperar
        video_url = self.wait_for_completion(task_id, clip_name)
        if not video_url:
            self.logger.error(f"❌ No se pudo generar {clip_name}")
            return None
        
        # Paso 3: Descargar
        output_path = OUTPUT_DIR / f"{clip_id}.mp4"
        if self.download_video(video_url, output_path):
            self.logger.info(f"🎉 Clip completado: {output_path}")
            return output_path
        else:
            return None
    
    def run(self, clip_indices: Optional[list] = None):
        """
        Ejecuta el generador para los clips especificados
        
        Args:
            clip_indices: Lista de índices de clips a generar (0-3).
                         Si es None, genera solo el primero (prueba).
        """
        self.logger.info("🎬 Kling AI Video Generator - MiCita")
        self.logger.info(f"📁 Output: {OUTPUT_DIR}")
        self.logger.info(f"🔑 Access Key: {self.access_key[:8]}...")
        
        # Por defecto, solo generar el primer clip como prueba
        if clip_indices is None:
            clip_indices = [0]
            self.logger.info("⚠️  Modo prueba: Solo se generará el Clip 1 (Herminda Saluda)")
            self.logger.info("   Si funciona, ejecutá: python scripts/kling_generator.py --all")
        
        results = []
        for idx in clip_indices:
            if idx >= len(CLIPS):
                self.logger.error(f"❌ Índice {idx} fuera de rango (0-{len(CLIPS)-1})")
                continue
            
            clip = CLIPS[idx]
            result = self.generate_clip(clip)
            results.append((clip["nombre"], result))
            
            # Pequeña pausa entre clips
            if idx < clip_indices[-1]:
                self.logger.info("⏳ Pausa de 5 segundos antes del siguiente clip...")
                time.sleep(5)
        
        # Resumen
        self.logger.info(f"\n{'='*60}")
        self.logger.info("📊 RESUMEN")
        self.logger.info(f"{'='*60}")
        for name, path in results:
            status = "✅ OK" if path else "❌ Falló"
            self.logger.info(f"   {status} {name}")
        
        successful = [r for r in results if r[1]]
        self.logger.info(f"\n✅ Completados: {len(successful)}/{len(results)}")


def main():
    """Punto de entrada principal"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generador de videos MiCita usando Kling AI API"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generar todos los clips (1-4). Por defecto solo genera el primero (prueba)"
    )
    parser.add_argument(
        "--clip",
        type=int,
        choices=[0, 1, 2, 3],
        help="Generar un clip específico por índice (0-3)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Listar clips disponibles y salir"
    )
    
    args = parser.parse_args()
    
    if args.list:
        print("📋 Clips disponibles:")
        for i, clip in enumerate(CLIPS):
            print(f"   {i}: {clip['nombre']} ({clip['duration']}s)")
        print("\nUso: python scripts/kling_generator.py --clip 0")
        return
    
    try:
        generator = KlingVideoGenerator()
        
        if args.all:
            generator.run(clip_indices=[0, 1, 2, 3])
        elif args.clip is not None:
            generator.run(clip_indices=[args.clip])
        else:
            # Por defecto: solo clip 1 (prueba)
            generator.run(clip_indices=[0])
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
