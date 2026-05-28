import time
import signal
import sys
from app.config import DEBUG, BOT_NAME
from app.db import init_db
from app.db_migrations import apply_migrations
from app.whatsapp_store import store
from app.whatsapp_service import WhatsAppService

POLL_INTERVAL_SECONDS = 2
BATCH_SIZE = 10


class Worker:
    def __init__(self):
        self.running = True
        self.service = WhatsAppService()
        self._setup_signals()

    def _setup_signals(self):
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        print(f"\n[WORKER] Señal recibida ({signum}), deteniendo...")
        self.running = False

    def run(self):
        print(f"[WORKER] Iniciando worker de {BOT_NAME}")
        print(f"[WORKER] Intervalo de polling: {POLL_INTERVAL_SECONDS}s")

        init_db()
        apply_migrations()

        while self.running:
            try:
                pending = store.get_pending_inbounds(limit=BATCH_SIZE)

                if pending:
                    print(f"[WORKER] {len(pending)} mensajes pendientes encontrados")

                    for msg in pending:
                        if not self.running:
                            break

                        msg_id = msg["provider_message_id"]
                        print(f"[WORKER] Procesando mensaje {msg_id}...")

                        result = self.service.process_inbound_by_id(msg["id"])

                        if result.startswith("["):
                            print(f"[WORKER] Resultado: {result}")
                        else:
                            print(f"[WORKER] Respuesta enviada: {result}")

                else:
                    if DEBUG:
                        print("[WORKER] Sin mensajes pendientes")

            except Exception as e:
                print(f"[WORKER ERROR] {e}")
                import traceback
                traceback.print_exc()

            for _ in range(POLL_INTERVAL_SECONDS):
                if not self.running:
                    break
                time.sleep(1)

        print("[WORKER] Detenido correctamente")


def main():
    worker = Worker()
    worker.run()


if __name__ == "__main__":
    main()
