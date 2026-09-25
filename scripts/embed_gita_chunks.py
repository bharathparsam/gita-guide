import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

from app.retrieval.nvidia_embeddings import NvidiaNemotronEmbeddings


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    load_dotenv(".env")
    parser = argparse.ArgumentParser(description="Embed the verse-aware Gita corpus")
    parser.add_argument(
        "--chunks", type=Path, default=Path("data/processed/gita_chunks.jsonl")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/gita_embeddings.npy")
    )
    args = parser.parse_args()

    chunks = [json.loads(line) for line in args.chunks.read_text().splitlines() if line]
    passages = [chunk["retrieval_text"] for chunk in chunks]
    model = NvidiaNemotronEmbeddings.from_environment()
    embeddings = np.asarray(
        model.embed_documents(passages),
        dtype=np.float32,
    )
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("NVIDIA returned a zero passage embedding")
    embeddings /= norms

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.output, embeddings)
    metadata_path = args.output.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "model": model.model,
                "chunks_path": str(args.chunks),
                "chunks_sha256": file_sha256(args.chunks),
                "rows": len(chunks),
                "dimensions": int(embeddings.shape[1]),
                "normalized": True,
                "embeddings_sha256": file_sha256(args.output),
                "query_input_type": "query",
                "passage_input_type": "passage",
                "query_prefix": "",
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Wrote {embeddings.shape} embeddings to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
