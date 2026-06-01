#!/usr/bin/env python3
"""
TEST DE FLUJOS DE CONVERSACIÓN
Simula conversaciones completas por WhatsApp para verificar:
- No hay loops infinitos
- Las respuestas acercan al objetivo
- La identidad médica se mantiene
- No se dan diagnósticos médicos
"""

import os
import sys
import tempfile
import json

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db import init_db, get_connection
from app.whatsapp_service import WhatsAppService, normalize_phone_for_meta
from app.whatsapp_models import InboundTextMessage
from app.whatsapp_store import store
from app.config import SYSTEM_PROMPT


class ConversationTester:
    def __init__(self):
        self.service = WhatsAppService()
        self.phone_counter = 1000
        self.msg_counter = 0
        
    def _new_phone(self) -> str:
        """Genera un número de teléfono único para cada test."""
        self.phone_counter += 1
        return f"54911{self.phone_counter:08d}"
    
    def _send_message(self, phone: str, text: str) -> dict:
        """Simula que un usuario envía un mensaje."""
        import uuid
        msg = InboundTextMessage(
            from_number=phone,
            message_id=f"msg_{uuid.uuid4().hex[:16]}",
            text=text,
            timestamp="2026-06-01T12:00:00Z",
            provider="fake"
        )
        return self.service.handle_inbound_text(msg)
    
    def _get_last_outbound(self, phone: str) -> str:
        """Obtiene el último mensaje enviado por el bot a un número."""
        history = store.get_conversation_history(phone, limit=1)
        if history:
            return history[0].get("answer", "")
        return ""
    
    def _get_all_outbounds(self, phone: str) -> list:
        """Obtiene todos los mensajes enviados por el bot a un número."""
        history = store.get_conversation_history(phone, limit=50)
        return [h.get("answer", "") for h in history]
    
    def _check_loop(self, outbounds: list, max_repeats: int = 2) -> tuple:
        """Verifica si hay loops (misma respuesta repetida)."""
        if len(outbounds) < max_repeats + 1:
            return True, "pocos mensajes"
        
        # Normalizar respuestas para comparación (ignorar IDs y timestamps)
        normalized = []
        for msg in outbounds:
            # Quitar prefijos tipo [RAG os_osde] o [INSURANCE LIST]
            clean = msg.split("]", 1)[-1].strip() if "]" in msg else msg
            normalized.append(clean[:100])  # Comparar primeros 100 chars
        
        # Verificar repetición consecutiva
        for i in range(len(normalized) - max_repeats):
            if all(normalized[i] == normalized[i+j] for j in range(1, max_repeats+1)):
                return False, f"loop detectado: '{normalized[i][:50]}...' repetido {max_repeats+1} veces"
        
        return True, "sin loops"
    
    def _check_identity(self, text: str) -> tuple:
        """Verifica que la respuesta mantenga identidad médica."""
        medical_terms = [
            "centro médico", "consultorio", "turno", "obra social", 
            "consulta", "paciente", "dr. pérez", "doctor", "médico",
            "secretaria virtual"
        ]
        text_lower = text.lower()
        has_medical = any(term in text_lower for term in medical_terms)
        
        # Evitar identidad vieja de Rodrigo Rodriguez
        old_identity = ["rodrigo rodriguez", "secretaria virtual de rodrigo", 
                       "automatización para negocios", "emprendedores"]
        has_old = any(term in text_lower for term in old_identity)
        
        if has_old:
            return False, "RESPUESTA CON IDENTIDAD VIEJA (Rodrigo Rodriguez)"
        if not has_medical:
            return False, "respuesta no tiene términos médicos (¿perdió identidad?)"
        
        return True, "identidad médica OK"
    
    def _check_no_diagnosis(self, text: str) -> tuple:
        """Verifica que no se den diagnósticos ni consejos médicos."""
        text_lower = text.lower()
        
        # Si el usuario mencionó síntomas, verificar redirección
        symptom_keywords = ["dolor", "fiebre", "tos", "mareo", "vomito", "sangrado"]
        has_symptom = any(k in text_lower for k in symptom_keywords)
        
        if has_symptom:
            # Si hay síntoma, el bot debería redirigir al médico o urgencias
            redirect_terms = ["consultar", "médico", "doctor", "urgencia", "107", "911", "guardia"]
            has_redirect = any(t in text_lower for t in redirect_terms)
            
            if not has_redirect:
                return False, "menciona síntomas pero NO redirige al médico/urgencias"
        
        return True, "no diagnóstico detectado"
    
    def _check_progression(self, steps: list, expected_flow: list) -> tuple:
        """Verifica que la conversación progrese hacia el objetivo."""
        # Cada paso debería aportar información nueva
        outbounds = [s["bot_response"] for s in steps]
        
        for i in range(1, len(outbounds)):
            prev = outbounds[i-1][:80]
            curr = outbounds[i][:80]
            if prev == curr:
                return False, f"paso {i} no aporta info nueva (igual al anterior)"
        
        return True, "progresión OK"

    # =====================================================================
    # FLUJOS DE PRUEBA
    # =====================================================================
    
    def test_greeting_to_osde(self) -> dict:
        """Flujo 1: Saludo → Obras sociales → OSDE"""
        print("\n🧪 TEST 1: Greeting → Obras sociales → OSDE")
        phone = self._new_phone()
        steps = []
        
        # Paso 1: "Hola"
        result = self._send_message(phone, "Hola")
        resp = self._get_last_outbound(phone)
        steps.append({"user": "Hola", "bot_response": resp, "result": result})
        print(f"   Paso 1 (Hola)          → {result[:40]}...")
        assert "GREETING+BUTTONS" in result or "BUTTONS" in result, "Debería enviar botones de bienvenida"
        
        # Paso 2: Click "Obras sociales" → envía lista
        result = self._send_message(phone, "[btn_obras] 💳 Obras sociales")
        resp = self._get_last_outbound(phone)
        steps.append({"user": "[btn_obras]", "bot_response": resp, "result": result})
        print(f"   Paso 2 ([btn_obras])   → {result[:40]}...")
        assert "INSURANCE LIST" in result, "Debería enviar lista de obras sociales"
        
        # Paso 3: Click "OSDE" → NO debería reenviar la lista, sino RAG
        result = self._send_message(phone, "[os_osde] OSDE")
        resp = self._get_last_outbound(phone)
        steps.append({"user": "[os_osde]", "bot_response": resp, "result": result})
        print(f"   Paso 3 ([os_osde])     → {result[:40]}...")
        assert "RAG os_osde" in result, "Debería responder con RAG específico de OSDE"
        assert "INSURANCE LIST" not in result, "NO debería reenviar la lista"
        
        # Validaciones
        outbounds = self._get_all_outbounds(phone)
        ok_loop, msg_loop = self._check_loop(outbounds)
        ok_id, msg_id = self._check_identity(resp)
        ok_prog, msg_prog = self._check_progression(steps, ["greeting", "list", "detail"])
        
        passed = ok_loop and ok_id and ok_prog
        return {
            "name": "Greeting → Obras → OSDE",
            "passed": passed,
            "details": f"loop: {msg_loop} | id: {msg_id} | prog: {msg_prog}",
            "steps": steps
        }
    
    def test_anti_loop_osde(self) -> dict:
        """Flujo 2: Anti-loop (OSDE x3)"""
        print("\n🧪 TEST 2: Anti-loop OSDE")
        phone = self._new_phone()
        steps = []
        
        # "Hola" → botones
        self._send_message(phone, "Hola")
        # Click Obras → lista
        self._send_message(phone, "[btn_obras] Obras sociales")
        # OSDE x3
        for i in range(3):
            result = self._send_message(phone, "[os_osde] OSDE")
            resp = self._get_last_outbound(phone)
            steps.append({"user": f"OSDE #{i+1}", "bot_response": resp, "result": result})
            print(f"   Paso {i+3} (OSDE)        → {result[:40]}...")
            assert "RAG os_osde" in result, f"Paso {i+1}: debería ser RAG, no lista"
        
        outbounds = self._get_all_outbounds(phone)
        ok_loop, msg_loop = self._check_loop(outbounds)
        
        return {
            "name": "Anti-loop OSDE",
            "passed": ok_loop,
            "details": msg_loop,
            "steps": steps
        }
    
    def test_greeting_to_precios(self) -> dict:
        """Flujo 3: Saludo → Precios"""
        print("\n🧪 TEST 3: Greeting → Precios")
        phone = self._new_phone()
        steps = []
        
        self._send_message(phone, "Hola")
        result = self._send_message(phone, "[btn_precios] 💰 Precios")
        resp = self._get_last_outbound(phone)
        steps.append({"user": "[btn_precios]", "bot_response": resp, "result": result})
        print(f"   Paso 2 ([btn_precios]) → {result[:40]}...")
        
        assert "RAG btn_precios" in result, "Debería responder con RAG de precios"
        assert "$25.000" in resp or "precio" in resp.lower() or "consulta" in resp.lower(), \
            "Debería mencionar precios de consulta"
        
        ok_id, msg_id = self._check_identity(resp)
        
        return {
            "name": "Greeting → Precios",
            "passed": ok_id,
            "details": msg_id,
            "steps": steps
        }
    
    def test_greeting_to_turno(self) -> dict:
        """Flujo 4: Saludo → Turno"""
        print("\n🧪 TEST 4: Greeting → Turno")
        phone = self._new_phone()
        
        self._send_message(phone, "Hola")
        result = self._send_message(phone, "[btn_turno] 🗓️ Sacar turno")
        resp = self._get_last_outbound(phone)
        print(f"   Paso 2 ([btn_turno])   → {result[:40]}...")
        
        assert "RAG btn_turno" in result, "Debería responder con RAG de turnos"
        assert "nombre" in resp.lower() or "dni" in resp.lower() or "obra social" in resp.lower(), \
            "Debería pedir datos para el turno"
        
        ok_id, _ = self._check_identity(resp)
        
        return {
            "name": "Greeting → Turno",
            "passed": ok_id,
            "details": "Pide datos para turno",
            "steps": [{"user": "[btn_turno]", "bot_response": resp}]
        }
    
    def test_services_to_laboratorio(self) -> dict:
        """Flujo 5: Servicios → Laboratorio"""
        print("\n🧪 TEST 5: Servicios → Laboratorio")
        phone = self._new_phone()
        steps = []
        
        # El usuario escribe "servicios" libremente (no es click de botón)
        result = self._send_message(phone, "Qué servicios tienen?")
        resp = self._get_last_outbound(phone)
        steps.append({"user": "Qué servicios?", "bot_response": resp, "result": result})
        print(f"   Paso 1 (servicios)     → {result[:40]}...")
        assert "SERVICES LIST" in result, "Debería enviar lista de servicios"
        
        # Click en Laboratorio
        result = self._send_message(phone, "[srv_lab] Laboratorio")
        resp = self._get_last_outbound(phone)
        steps.append({"user": "[srv_lab]", "bot_response": resp, "result": result})
        print(f"   Paso 2 ([srv_lab])     → {result[:40]}...")
        assert "RAG srv_lab" in result, "Debería responder con RAG de laboratorio"
        assert "SERVICES LIST" not in result, "NO debería reenviar lista"
        
        outbounds = self._get_all_outbounds(phone)
        ok_loop, msg_loop = self._check_loop(outbounds)
        
        return {
            "name": "Servicios → Laboratorio",
            "passed": ok_loop,
            "details": msg_loop,
            "steps": steps
        }
    
    def test_urgencia(self) -> dict:
        """Flujo 6: Urgencia médica"""
        print("\n🧪 TEST 6: Urgencia (dolor de pecho)")
        phone = self._new_phone()
        
        result = self._send_message(phone, "Tengo dolor de pecho fuerte")
        resp = self._get_last_outbound(phone)
        print(f"   Paso 1 (urgencia)      → {result[:40]}...")
        
        ok_no_diag, msg_no_diag = self._check_no_diagnosis(resp)
        ok_id, msg_id = self._check_identity(resp)
        
        passed = ok_no_diag and ok_id
        
        return {
            "name": "Urgencia (dolor de pecho)",
            "passed": passed,
            "details": f"no-diag: {msg_no_diag} | id: {msg_id}",
            "steps": [{"user": "dolor de pecho", "bot_response": resp}]
        }
    
    def test_primera_visita(self) -> dict:
        """Flujo 7: Primera visita"""
        print("\n🧪 TEST 7: Primera visita")
        phone = self._new_phone()
        
        result = self._send_message(phone, "Es mi primera vez, qué debo llevar?")
        resp = self._get_last_outbound(phone)
        print(f"   Paso 1 (primera vez)   → {result[:40]}...")
        
        has_docs = any(w in resp.lower() for w in ["documento", "dni", "credencial", "obra social"])
        ok_id, msg_id = self._check_identity(resp)
        
        passed = has_docs and ok_id
        
        return {
            "name": "Primera visita",
            "passed": passed,
            "details": f"documentos: {has_docs} | id: {msg_id}",
            "steps": [{"user": "primera vez", "bot_response": resp}]
        }
    
    def test_obra_social_directa(self) -> dict:
        """Flujo 8: Pregunta directa por obra social"""
        print("\n🧪 TEST 8: Obra social directa (Galeno)")
        phone = self._new_phone()
        steps = []
        
        # Pregunta directa (no es click de botón)
        result = self._send_message(phone, "Atienden por Galeno?")
        resp = self._get_last_outbound(phone)
        steps.append({"user": "Galeno?", "bot_response": resp, "result": result})
        print(f"   Paso 1 (Galeno?)       → {result[:40]}...")
        
        # Debería enviar lista (es la primera vez que pregunta)
        assert "INSURANCE LIST" in result, "Primera pregunta de obra social → lista"
        
        # Ahora toca Galeno en la lista
        result = self._send_message(phone, "[os_galeno] Galeno")
        resp = self._get_last_outbound(phone)
        steps.append({"user": "[os_galeno]", "bot_response": resp, "result": result})
        print(f"   Paso 2 ([os_galeno])   → {result[:40]}...")
        
        assert "RAG os_galeno" in result, "Click en Galeno → RAG específico"
        
        outbounds = self._get_all_outbounds(phone)
        ok_loop, msg_loop = self._check_loop(outbounds)
        
        return {
            "name": "Obra social directa (Galeno)",
            "passed": ok_loop,
            "details": msg_loop,
            "steps": steps
        }


def main():
    print("=" * 60)
    print("🧪 TEST DE FLUJOS DE CONVERSACIÓN - CENTRO MÉDICO DEMO")
    print("=" * 60)
    
    # Inicializar DB temporal
    db_path = os.path.join(tempfile.gettempdir(), "test_medical_bot.sqlite3")
    os.environ["APP_DB_PATH"] = db_path
    if os.path.exists(db_path):
        os.remove(db_path)
    
    from app.db_migrations import apply_migrations
    init_db()
    apply_migrations()
    
    tester = ConversationTester()
    
    # Ejecutar todos los tests
    tests = [
        tester.test_greeting_to_osde,
        tester.test_anti_loop_osde,
        tester.test_greeting_to_precios,
        tester.test_greeting_to_turno,
        tester.test_services_to_laboratorio,
        tester.test_urgencia,
        tester.test_primera_visita,
        tester.test_obra_social_directa,
    ]
    
    results = []
    for test_fn in tests:
        try:
            result = test_fn()
            results.append(result)
        except AssertionError as e:
            results.append({
                "name": test_fn.__name__,
                "passed": False,
                "details": f"ASSERT FAILED: {e}",
                "steps": []
            })
            print(f"   ❌ ASSERT FAILED: {e}")
        except Exception as e:
            results.append({
                "name": test_fn.__name__,
                "passed": False,
                "details": f"ERROR: {e}",
                "steps": []
            })
            print(f"   ❌ ERROR: {e}")
    
    # Reporte final
    print("\n" + "=" * 60)
    print("📊 REPORTE FINAL")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for r in results:
        status = "✅ PASÓ" if r["passed"] else "❌ FALLÓ"
        print(f"\n{status} {r['name']}")
        print(f"   {r['details']}")
        if not r["passed"]:
            failed += 1
        else:
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"📈 RESULTADO: {passed}/{len(results)} tests pasaron | {failed} fallos")
    print("=" * 60)
    
    # Guardar reporte JSON
    report_path = os.path.join(tempfile.gettempdir(), "test_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Reporte detallado guardado en: {report_path}")
    
    # Limpiar DB temporal
    if os.path.exists(db_path):
        os.remove(db_path)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
