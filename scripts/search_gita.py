from __future__ import annotations

import argparse
import json

from dotenv import load_dotenv

from app.retrieval import build_local_gita_retriever


def main() -> int:
    load_dotenv(".env")
    parser = argparse.ArgumentParser(
        description="Search the bundled Bhagavad Gita vector index"
    )
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--minimum-score", type=float, default=-1.0)
    args = parser.parse_args()

    retriever = build_local_gita_retriever()
    documents = retriever.retrieve(
        args.query,
        top_k=args.top_k,
        minimum_score=args.minimum_score,
    )
    print(
        json.dumps(
            [
                {
                    "rank": rank,
                    "chapter": document.metadata["chapter"],
                    "verse": document.metadata["verse_label"],
                    "score": round(document.metadata["similarity_score"], 6),
                    "translation": document.page_content,
                    "source_pdf_page": document.metadata["source_pdf_page"],
                }
                for rank, document in enumerate(documents, start=1)
            ],
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
