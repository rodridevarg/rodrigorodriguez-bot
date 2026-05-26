import sys
from pathlib import Path

current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir.parent))

from app.documents import load_documents
from app.vector_store import add_documents, clear_collection


def main():
    print("=" * 60)
    print("INDEXANDO DOCUMENTOS EN CHROMADB")
    print("=" * 60)
    print()
    
    print("[1/4] Cargando documentos...")
    docs = load_documents()
    print(f"   {len(docs)} documentos encontrados.")
    print()
    
    print("[2/4] Limpiando coleccion anterior...")
    clear_collection("rodrigo_docs")
    print()
    
    print("[3/4] Preparando documentos...")
    chroma_docs = []
    for doc in docs:
        chroma_docs.append({
            "id": doc["id"],
            "text": doc["content"],
            "metadata": {
                "title": doc["title"],
                "source": doc["source"],
            }
        })
        print(f"   - {doc['id']}: {len(doc['content'])} caracteres")
    print()
    
    print("[4/4] Indexando en ChromaDB (esto genera embeddings)...")
    add_documents(chroma_docs, collection_name="rodrigo_docs")
    print()
    
    print("=" * 60)
    print("INDEXACION COMPLETA")
    print("=" * 60)
    print()
    print("Ahora podes ejecutar: python app/chat_local.py")
    print("El chat usara busqueda semantica en vez de palabras clave.")


if __name__ == "__main__":
    main()
