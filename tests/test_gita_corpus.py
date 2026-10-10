import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from app.classifiers.taxonomy import GITA_TRAITS
from app.models.classification import ClassificationResult
from app.retrieval.trait_anchors import (
    MESSAGE_INTENT_VERSE_ANCHORS,
    SITUATION_VERSE_ANCHORS,
    TRAIT_VERSE_ANCHORS,
    curated_anchor_verse_labels,
)
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
    assert {
        label
        for labels in SITUATION_VERSE_ANCHORS.values()
        for label in labels
    } <= translation_verses
    assert {
        label
        for _, labels in MESSAGE_INTENT_VERSE_ANCHORS
        for label in labels
    } <= translation_verses


def test_relationship_conflict_includes_concrete_conduct_anchors() -> None:
    classification = ClassificationResult(
        in_scope=True,
        in_scope_probability=0.99,
        primary_situation="relationship_conflict",
        primary_situation_confidence=0.95,
        primary_emotion="confusion",
        primary_emotion_confidence=0.82,
        root_conflict="loss",
        root_conflict_confidence=0.51,
        primary_trait="conflict",
        primary_trait_confidence=0.91,
        needs_review=True,
        low_confidence_fields=("root_conflict",),
    )

    assert curated_anchor_verse_labels(classification) == (
        "12.18",
        "12.13",
        "17.15",
    )


def test_anger_includes_actionable_conduct_anchors() -> None:
    classification = ClassificationResult(
        in_scope=True,
        in_scope_probability=0.99,
        primary_situation="anger",
        primary_situation_confidence=0.98,
        primary_emotion="anger",
        primary_emotion_confidence=0.95,
        root_conflict="lack_of_self_control",
        root_conflict_confidence=0.94,
        primary_trait="anger",
        primary_trait_confidence=0.97,
    )

    assert curated_anchor_verse_labels(classification) == (
        "2.62",
        "2.63",
        "2.64",
        "17.15",
        "17.16",
    )


def test_perfection_intent_includes_qualities_and_purpose_anchors() -> None:
    classification = ClassificationResult(
        in_scope=False,
        in_scope_probability=0.42,
        primary_situation="purpose",
        primary_situation_confidence=0.8,
        primary_emotion="calm",
        primary_emotion_confidence=0.8,
        root_conflict="other",
        root_conflict_confidence=0.7,
        primary_trait="purpose",
        primary_trait_confidence=0.85,
    )

    assert curated_anchor_verse_labels(
        classification,
        message_intents=("perfection_of_person",),
    ) == ("18.46", "12.13", "12.14", "12.18")


def test_relationship_loss_intent_includes_supportive_anchors() -> None:
    classification = ClassificationResult(
        in_scope=True,
        in_scope_probability=0.99,
        primary_situation="grief",
        primary_situation_confidence=0.97,
        primary_emotion="sadness",
        primary_emotion_confidence=0.97,
        root_conflict="loss",
        root_conflict_confidence=1.0,
        primary_trait="grief",
        primary_trait_confidence=0.39,
        needs_review=True,
        low_confidence_fields=("primary_trait",),
    )

    assert curated_anchor_verse_labels(
        classification,
        message_intents=("relationship_loss",),
    ) == ("2.14", "6.5", "12.13", "12.17", "12.19")


def test_low_confidence_trait_does_not_choose_the_curated_anchor() -> None:
    classification = ClassificationResult(
        in_scope=True,
        in_scope_probability=0.98,
        primary_situation="relationship_conflict",
        primary_situation_confidence=0.94,
        primary_emotion="sadness",
        primary_emotion_confidence=0.9,
        root_conflict="duty_conflict",
        root_conflict_confidence=0.88,
        primary_trait="success",
        primary_trait_confidence=0.35,
        needs_review=True,
        low_confidence_fields=("primary_trait",),
    )

    assert curated_anchor_verse_labels(classification) == (
        "12.18",
        "12.13",
        "17.15",
    )


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
