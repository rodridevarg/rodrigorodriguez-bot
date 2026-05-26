from app.config import DOCS_DIR


def load_documents():
    docs = []
    if not DOCS_DIR.exists():
        raise FileNotFoundError(f"No existe el directorio de documentos: {DOCS_DIR}")

    for md_file in sorted(DOCS_DIR.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        docs.append(
            {
                "id": md_file.stem,
                "title": md_file.stem.replace("_", " ").title(),
                "content": content,
                "source": str(md_file),
            }
        )
    return docs
