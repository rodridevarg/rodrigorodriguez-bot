from app.vector_store import query


def retrieve(question: str, top_k: int = 3):
    results = query(question, n_results=top_k)
    
    documents = []
    for result in results:
        documents.append({
            "id": result["id"],
            "title": result["metadata"].get("title", result["id"]),
            "content": result["text"],
            "source": result["metadata"].get("source", ""),
        })
    
    return documents
