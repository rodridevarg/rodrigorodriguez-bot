from typing import List, Dict, Optional
from app.retriever import retrieve
from app.llm_client import ask_llm
from app.config import TOP_K, DEBUG, CONVERSATION_ACTIVE_CONTEXT_TURNS

SYSTEM_PROMPT = """Sos la Secretaria Virtual de Rodrigo Rodriguez. Ayudás a emprendedores y profesionales a vender más con atención automatizada por WhatsApp.

Respondé usando ÚNICAMENTE la información proporcionada en el contexto.
Si no encontrás la respuesta en el contexto, decí claramente que no lo sabés y sugerí contactar por WhatsApp a Rodrigo.
Sé cercano, profesional y entusiasta. Respondé en español. No inventes precios ni promesas que no estén en el contexto."""


def _build_retrieval_query(question: str, history: Optional[List[Dict]]) -> str:
    if not history:
        return question
    recent = history[-3:]
    parts = [turn["question"] for turn in recent]
    parts.append(question)
    return " ".join(parts)


def _build_history_block(history: Optional[List[Dict]]) -> str:
    if not history:
        return ""
    lines = []
    for turn in history[-CONVERSATION_ACTIVE_CONTEXT_TURNS:]:
        lines.append(f"Cliente: {turn['question']}")
        lines.append(f"Asistente: {turn['answer']}")
    return "\n".join(lines)


def build_prompt(
    question: str, docs: List[Dict], history: Optional[List[Dict]] = None
) -> str:
    context = "\n\n---\n\n".join(
        [f"Fuente: {d['title']}\n{d['content']}" for d in docs]
    )
    history_block = _build_history_block(history)

    parts = [SYSTEM_PROMPT]
    if history_block:
        parts.append(
            f"\nHistorial reciente de la conversacion:\n{history_block}"
        )
    parts.append(f"\nContexto de conocimiento:\n{context}")
    parts.append(f"\nPregunta actual del cliente: {question}")
    parts.append("\nRespuesta:")

    return "\n".join(parts)


def answer_question(
    question: str, conversation_history: Optional[List[Dict]] = None
) -> Dict:
    retrieval_query = _build_retrieval_query(question, conversation_history)
    retrieved = retrieve(retrieval_query, top_k=TOP_K)

    if not retrieved and conversation_history:
        retrieved = retrieve(question, top_k=TOP_K)

    if not retrieved:
        return {
            "answer": (
                "No encontré información sobre eso en mi base de conocimiento. "
                "Te sugiero contactar a Rodrigo por WhatsApp: +54 9 2477 614405"
            ),
            "sources": [],
        }

    if DEBUG:
        print(f"[RAG] Fuentes usadas: {[d['title'] for d in retrieved]}")
        if conversation_history:
            print(f"[RAG] Historial: {len(conversation_history)} turnos")

    prompt = build_prompt(question, retrieved, conversation_history)
    answer = ask_llm(prompt)

    return {
        "answer": answer,
        "sources": [{"id": d["id"], "title": d["title"]} for d in retrieved],
    }
