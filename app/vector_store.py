import chromadb
from chromadb.config import Settings
from app.config import CHROMA_DIR

_client = None


def get_client():
    global _client
    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_collection(name: str = "rodrigo_docs"):
    client = get_client()
    return client.get_or_create_collection(name=name)


def add_documents(documents: list, collection_name: str = "rodrigo_docs"):
    collection = get_collection(collection_name)
    
    ids = [doc["id"] for doc in documents]
    texts = [doc["text"] for doc in documents]
    metadatas = [doc.get("metadata", {}) for doc in documents]
    
    collection.add(
        ids=ids,
        documents=texts,
        metadatas=metadatas,
    )
    print(f"[OK] {len(documents)} documentos agregados a ChromaDB.")


def query(text: str, n_results: int = 3, collection_name: str = "rodrigo_docs"):
    collection = get_collection(collection_name)
    
    results = collection.query(
        query_texts=[text],
        n_results=n_results,
    )
    
    documents = []
    for i in range(len(results["ids"][0])):
        documents.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    
    return documents


def clear_collection(collection_name: str = "rodrigo_docs"):
    client = get_client()
    try:
        client.delete_collection(name=collection_name)
        print(f"[OK] Coleccion '{collection_name}' eliminada.")
    except Exception:
        print(f"[INFO] La coleccion '{collection_name}' no existia.")
