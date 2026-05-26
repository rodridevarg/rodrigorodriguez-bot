from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_model = None


def get_model():
    global _model
    if _model is None:
        print("Cargando modelo de embeddings... (puede tardar la primera vez)")
        _model = SentenceTransformer(MODEL_NAME)
        print("Modelo cargado.")
    return _model


def embed_text(text: str):
    model = get_model()
    return model.encode(text, convert_to_list=True)


def embed_texts(texts: list):
    model = get_model()
    return model.encode(texts, convert_to_list=True)
