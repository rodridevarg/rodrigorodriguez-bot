from openai import OpenAI
from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


def ask_llm(prompt: str, model: str = None) -> str:
    model = model or LLM_MODEL
    if not model:
        raise ValueError(
            "No se configuró LLM_MODEL. "
            "Ejecutá 'python scripts/discover_api.py' para descubrirlo."
        )
    if not LLM_API_KEY:
        raise ValueError("No se configuró LLM_API_KEY")
    if not LLM_BASE_URL:
        raise ValueError(
            "No se configuró LLM_BASE_URL. "
            "Ejecutá 'python scripts/discover_api.py' para descubrirlo."
        )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content
