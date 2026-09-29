import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from app.classifiers.taxonomy import GITA_TRAITS
from app.retrieval.trait_anchors import TRAIT_VERSE_ANCHORS
from scripts.ingest_gita_pdf import recursive_split_text


EXPECTED_VERSE_COUNTS = {
    1: 46,
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
    13: 35,
    14: 27,
    15: 20,
    16: 24,
    17: 28,
    18: 78,
}

EXPECTED_CHAPTER_TITLES = {
    1: "Observing the Armies on the Battlefield of Kurukṣetra",
    2: "Contents of the Gītā Summarized",
    3: "Karma-yoga",
    4: "Transcendental Knowledge",
    5: "Karma-yoga—Action in Kṛṣṇa Consciousness",
    6: "Sāṅkhya-yoga",
    7: "Knowledge of the Absolute",
    8: "Attaining the Supreme",
    9: "The Most Confidential Knowledge",
    10: "The Opulence of the Absolute",
    11: "The Universal Form",
    12: "Devotional Service",
    13: "Nature, the Enjoyer, and Consciousness",
    14: "The Three Modes of Material Nature",
    15: "The Yoga of the Supreme Person",
    16: "The Divine and Demoniac Natures",
    17: "The Divisions of Faith",
    18: "Conclusion—The Perfection of Renunciation",
}


def test_source_pdf_matches_provenance_manifest() -> None:
    manifest = json.loads(Path("data/sources.json").read_text())
    assert len(manifest["sources"]) == 1
    source = manifest["sources"][0]
    source_path = Path(source["local_path"])

    assert source["source_id"] == "bhagavad-gita-as-it-is"
    assert source["title"] == "Bhagavad-gita As It Is"
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
        assert chunk["source_id"] == "bhagavad-gita-as-it-is"
        assert chunk["section"] in {"translation", "purport"}
        assert "sloka" in chunk
        assert len(chunk["translation"]) <= 1_200
        if chunk["section"] == "translation":
            assert chunk["sloka"]
            covered[chunk["chapter"]].extend(
                range(chunk["verse_start"], chunk["verse_end"] + 1)
            )

    assert len(chunks) == 1_860
    assert sum(chunk["section"] == "translation" for chunk in chunks) == 653
    assert sum(chunk["section"] == "purport" for chunk in chunks) == 1_207
    assert sum(len(verses) for verses in covered.values()) == 700
    for chapter, count in EXPECTED_VERSE_COUNTS.items():
        assert covered[chapter] == list(range(1, count + 1))
        assert {
            chunk["chapter_title"]
            for chunk in chunks
            if chunk["chapter"] == chapter
        } == {EXPECTED_CHAPTER_TITLES[chapter]}


def test_extracted_text_uses_unicode_transliteration() -> None:
    raw = Path("data/processed/gita_chunks.jsonl").read_text()

    assert "Kṛṣṇa" in raw
    assert "Bhagavad-gītā" in raw
    assert not set("äéüåèÿëìïöòçùà").intersection(raw)


def test_corpus_preserves_the_readable_sloka_from_the_source_pdf() -> None:
    chunks = [
        json.loads(line)
        for line in Path("data/processed/gita_chunks.jsonl").read_text().splitlines()
    ]
    verse = next(
        chunk
        for chunk in chunks
        if chunk["chapter"] == 2
        and chunk["verse_start"] == 47
        and chunk["section"] == "translation"
    )

    assert verse["sloka"] == (
        "karmaṇy evādhikāras te\n"
        "mā phaleṣu kadācana\n"
        "mā karma-phala-hetur bhūr\n"
        "mā te saṅgo ’stv akarmaṇi"
    )


def test_every_trait_anchor_resolves_to_a_translation_chunk() -> None:
    chunks = [
        json.loads(line)
        for line in Path("data/processed/gita_chunks.jsonl").read_text().splitlines()
    ]
    translation_verses = {
        f"{chunk['chapter']}.{verse}"
        for chunk in chunks
        if chunk["section"] == "translation"
        for verse in range(chunk["verse_start"], chunk["verse_end"] + 1)
    }

    assert set(TRAIT_VERSE_ANCHORS) == set(GITA_TRAITS)
    assert set(TRAIT_VERSE_ANCHORS.values()) <= translation_verses


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
    assert vectors.shape == (1_860, 2048)
    assert vectors.dtype == np.float32
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)


def test_recursive_chunker_prefers_paragraph_and_sentence_boundaries() -> None:
    text = (
        "First paragraph has one complete sentence. It also has a second sentence.\n\n"
        "Second paragraph contains another complete sentence. "
        "The final sentence keeps this sample long enough to split cleanly."
    )

    chunks = recursive_split_text(text, chunk_size=110, chunk_overlap=20)

    assert len(chunks) >= 2
    assert all(len(chunk) <= 110 for chunk in chunks)
    assert chunks[0].endswith("sentence.")
