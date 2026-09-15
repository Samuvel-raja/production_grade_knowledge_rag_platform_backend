"""One-off: create the Pinecone index if it doesn't already exist.

Usage (from backend/):
    python scripts/init_pinecone.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.vectorstore import init_vectorstore  # noqa: E402


def main() -> None:
    if not settings.pinecone_api_key:
        print("PINECONE_API_KEY is not set in .env — nothing to do.")
        return
    init_vectorstore()
    print(
        f"Pinecone index '{settings.pinecone_index}' is ready "
        f"(dimension={settings.embedding_dim}, region={settings.pinecone_region})."
    )


if __name__ == "__main__":
    main()
