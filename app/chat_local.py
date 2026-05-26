import sys
import io

# Windows: forzar UTF-8 para evitar errores con emojis
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag_service import answer_question
from app.config import DEBUG


def main():
    print("[BOT] Secretaria Virtual - Rodrigo Rodriguez (Chat Local)")
    print("Escribi tu pregunta o 'salir' para terminar.\n")
    print("[INFO] Usando busqueda semantica (entiende sinonimos y reformulaciones)\n")

    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[BYE] Chau!")
            break

        if question.lower() in ("salir", "exit", "quit"):
            print("[BYE] Chau!")
            break

        if not question:
            continue

        result = answer_question(question)

        if DEBUG and result["sources"]:
            print(f"[DEBUG] Fuentes usadas: {[s['title'] for s in result['sources']]}")

        print(f"\n[BOT] {result['answer']}\n")

        if result["sources"]:
            print("[FUENTES]")
            for s in result["sources"]:
                print(f"  - {s['title']}")
            print()


if __name__ == "__main__":
    main()
