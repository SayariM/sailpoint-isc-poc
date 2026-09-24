"""RAG POC: documents -> local embeddings -> Chroma -> Groq answer with citations."""

from __future__ import annotations

import argparse
import functools
import os
import sys
from collections.abc import Iterable
from pathlib import Path

import pymupdf
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    # Only needed behind a TLS-inspecting corporate proxy; absent on cloud hosts.
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

load_dotenv()

ROOT = Path(__file__).parent
DOCS_DIR = ROOT / "docs"
CHROMA_DIR = ROOT / ".chroma"
COLLECTION = "poc"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHAT_MODEL = os.getenv("GROQ_CHAT_MODEL", "openai/gpt-oss-120b")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
TOP_K = 4
TEXT_SUFFIXES = {".md", ".txt", ".json", ".xml", ".csv", ".yaml", ".yml"}

PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Answer the question using only the provided context. "
            "If the context does not contain the answer, say you don't know. "
            "Cite the sources you used inline as [file p.N].",
        ),
        ("human", "Context:\n{context}\n\nQuestion: {question}"),
    ]
)


@functools.cache
def _store() -> Chroma:
    return Chroma(
        collection_name=COLLECTION,
        embedding_function=HuggingFaceEmbeddings(model_name=EMBED_MODEL),
        persist_directory=str(CHROMA_DIR),
    )


def cite(doc: Document) -> str:
    page = doc.metadata.get("page")
    return f"{doc.metadata['source']} p.{page}" if page else doc.metadata["source"]


def retrieve(query: str, k: int = TOP_K) -> list[Document]:
    return _store().similarity_search(query, k=k)


def format_context(docs: Iterable[Document]) -> str:
    return "\n\n".join(f"[{cite(d)}]\n{d.page_content}" for d in docs)


def chat(temperature: float = 0.0, api_key: str | None = None) -> ChatGroq:
    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError(
            "No Groq API key available. Set GROQ_API_KEY or supply your own key."
        )
    return ChatGroq(model=CHAT_MODEL, temperature=temperature, api_key=key)


def load_documents(docs_dir: Path) -> list[Document]:
    docs: list[Document] = []
    for path in sorted(docs_dir.rglob("*")):
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            with pymupdf.open(path) as pdf:
                for page_no, page in enumerate(pdf, start=1):
                    text = page.get_text().strip()
                    if text:
                        docs.append(
                            Document(
                                page_content=text,
                                metadata={"source": path.name, "page": page_no},
                            )
                        )
        elif suffix in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                docs.append(Document(page_content=text, metadata={"source": path.name}))
    return docs


def ingest() -> None:
    loaded = load_documents(DOCS_DIR)
    if not loaded:
        sys.exit(f"No extractable text found. Put documents in {DOCS_DIR}")

    chunks = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    ).split_documents(loaded)

    store = _store()
    store.reset_collection()  # full rebuild, so re-running never duplicates chunks
    store.add_documents(chunks)

    files = {doc.metadata["source"] for doc in loaded}
    print(f"Indexed {len(chunks)} chunks from {len(files)} file(s) into {CHROMA_DIR}")


def ask(question: str, k: int) -> None:
    hits = retrieve(question, k)
    if not hits:
        sys.exit("Index is empty. Run: python rag.py ingest")

    try:
        chain = PROMPT | chat()
    except RuntimeError as exc:
        sys.exit(str(exc))
    print(chain.invoke({"context": format_context(hits), "question": question}).content)

    print("\nRetrieved chunks:")
    for d in hits:
        print(f"  - {cite(d)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest", help="(re)build the vector index from docs/")
    ask_cmd = sub.add_parser("ask", help="query the indexed documents")
    ask_cmd.add_argument("question")
    ask_cmd.add_argument("-k", type=int, default=TOP_K, help="chunks to retrieve")

    args = parser.parse_args()
    if args.command == "ingest":
        ingest()
    else:
        ask(args.question, args.k)


if __name__ == "__main__":
    main()
