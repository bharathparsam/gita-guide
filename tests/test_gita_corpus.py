import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


EXPECTED_VERSE_COUNTS = {
    1: 47,
    2: 72,
    3: 43,
    4: 42,
    5: 29,
    6: 47,
    7: 30,
    8: 28,
    9: 34,
    10: 42,
    11: 55,
    12: 20,
    13: 34,
    14: 27,
    15: 20,
    16: 24,
    17: 28,
    18: 78,
}

EXPECTED_CHAPTER_TITLES = {
    1: "The Grief of Arjuna",
    2: "The Way of Knowledge",
    3: "The Way of Action",
    4: "The Way of Renunciation of Action in Knowledge",
    5: "The Way of Renunciation",
    6: "The Way of Meditation",
    7: "The Way of Knowledge With Realization",
    8: "The Way to the Imperishable Brahman",
    9: "The Way of the Kingly Knowledge and the Kingly Secret",
    10: "Glimpses of the Divine Glory",
    11: "The Vision of the Universal Form",
    12: "The Way of Devotion",
    13: "The Discrimination of the Kshetra and the Kshetrajna",
    14: "The Discrimination of the Three Gunas",
    15: "The Way to the Supreme Spirit",
    16: "The Classification of the Divine and the Non-divine Attributes",
    17: "The Enquiry into the Threefold Shraddha",
    18: "The Way of Liberation in Renunciation",
}


def test_source_pdf_matches_provenance_manifest() -> None:
    manifest = json.loads(Path("data/sources.json").read_text())
    source = manifest["sources"][0]
    source_path = Path(source["local_path"])

    assert source["license"] == "Public domain"
    assert source_path.exists()
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == source["sha256"]


def test_chunks_cover_all_700_verses_once() -> None:
    chunks = [
        json.loads(line)
        for line in Path("data/processed/gita_chunks.jsonl").read_text().splitlines()
    ]
    covered: dict[int, list[int]] = defaultdict(list)
    ids = set()

    for chunk in chunks:
        assert chunk["chunk_id"] not in ids
        ids.add(chunk["chunk_id"])
        assert chunk["translation"]
        assert chunk["retrieval_text"]
        covered[chunk["chapter"]].extend(
            range(chunk["verse_start"], chunk["verse_end"] + 1)
        )

    assert len(chunks) == 671
    assert sum(len(verses) for verses in covered.values()) == 700
    for chapter, count in EXPECTED_VERSE_COUNTS.items():
        assert covered[chapter] == list(range(1, count + 1))
        assert {
            chunk["chapter_title"]
            for chunk in chunks
            if chunk["chapter"] == chapter
        } == {EXPECTED_CHAPTER_TITLES[chapter]}


def test_bundled_embeddings_match_corpus_and_manifest() -> None:
    chunks_path = Path("data/processed/gita_chunks.jsonl")
    embeddings_path = Path("data/processed/gita_embeddings.npy")
    metadata_path = Path("data/processed/gita_embeddings.metadata.json")
    metadata = json.loads(metadata_path.read_text())
    vectors = np.load(embeddings_path, allow_pickle=False, mmap_mode="r")

    assert metadata["model"] == "nvidia/nemotron-3-embed-1b"
    assert metadata["chunks_sha256"] == hashlib.sha256(
        chunks_path.read_bytes()
    ).hexdigest()
    assert metadata["embeddings_sha256"] == hashlib.sha256(
        embeddings_path.read_bytes()
    ).hexdigest()
    assert vectors.shape == (671, 2048)
    assert vectors.dtype == np.float32
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)
