import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader


CHAPTER_NUMBERS = {
    "One": 1,
    "Two": 2,
    "Three": 3,
    "Four": 4,
    "Five": 5,
    "Six": 6,
    "Seven": 7,
    "Eight": 8,
    "Nine": 9,
    "Ten": 10,
    "Eleven": 11,
    "Twelve": 12,
    "Thirteen": 13,
    "Fourteen": 14,
    "Fifteen": 15,
    "Sixteen": 16,
    "Seventeen": 17,
    "Eighteen": 18,
}
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
CHAPTER_PATTERN = re.compile(r"^Chapter\s+(" + "|".join(CHAPTER_NUMBERS) + r")$")
VERSE_PATTERN = re.compile(r"^(\d+)(?:-(\d+))?\)\s*(.*)$")
SPEAKER_PATTERN = re.compile(r"^(.*(?:said|asked)):$", re.IGNORECASE)
PAGE_NUMBER_PATTERN = re.compile(r"^\d+$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_line(line: str) -> str:
    return " ".join(line.replace("\u00ad", "").split())


def load_source(manifest_path: Path, source_id: str) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text())
    source = next(
        (item for item in manifest["sources"] if item["source_id"] == source_id),
        None,
    )
    if source is None:
        raise ValueError(f"Source {source_id!r} was not found in {manifest_path}")
    return source


def extract_chunks(pdf_path: Path, source: dict[str, Any]) -> list[dict[str, Any]]:
    reader = PdfReader(pdf_path)
    chunks: list[dict[str, Any]] = []
    current_chapter: int | None = None
    current_chapter_title: str | None = None
    current_speaker: str | None = None
    current: dict[str, Any] | None = None
    awaiting_chapter_title = False
    chapter_title_parts: list[str] = []

    def resolved_chapter_title() -> str:
        title = " ".join(chapter_title_parts)
        return title.replace("- ", "-").strip()

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        translation = " ".join(current.pop("text_parts"))
        translation = re.sub(r"\s+([,.;:?!])", r"\1", translation).strip()
        if translation:
            current["translation"] = translation
            current["retrieval_text"] = (
                f"Bhagavad Gita, chapter {current['chapter']} "
                f"({current['chapter_title']}), verse {current['verse_label']}. "
                f"Speaker: {current['speaker'] or 'Unknown'}. {translation}"
            )
            chunks.append(current)
        current = None

    for pdf_page, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = clean_line(raw_line)
            if not line or PAGE_NUMBER_PATTERN.fullmatch(line):
                continue

            chapter_match = CHAPTER_PATTERN.fullmatch(line)
            if chapter_match:
                flush()
                current_chapter = CHAPTER_NUMBERS[chapter_match.group(1)]
                current_chapter_title = None
                current_speaker = None
                awaiting_chapter_title = True
                chapter_title_parts = []
                continue

            if awaiting_chapter_title:
                speaker_match = SPEAKER_PATTERN.fullmatch(line)
                if speaker_match:
                    current_chapter_title = resolved_chapter_title()
                    if not current_chapter_title:
                        raise ValueError(
                            f"Chapter {current_chapter} has no extracted title"
                        )
                    awaiting_chapter_title = False
                    current_speaker = speaker_match.group(1)
                    continue
                chapter_title_parts.append(line)
                continue

            if current_chapter is None:
                continue

            speaker_match = SPEAKER_PATTERN.fullmatch(line)
            if speaker_match:
                flush()
                current_speaker = speaker_match.group(1)
                continue

            verse_match = VERSE_PATTERN.match(line)
            if verse_match:
                flush()
                verse_start = int(verse_match.group(1))
                verse_end = int(verse_match.group(2) or verse_start)
                verse_label = (
                    str(verse_start)
                    if verse_start == verse_end
                    else f"{verse_start}-{verse_end}"
                )
                current = {
                    "chunk_id": (
                        f"{source['source_id']}:"
                        f"{current_chapter:02d}:{verse_start:03d}-{verse_end:03d}"
                    ),
                    "source_id": source["source_id"],
                    "chapter": current_chapter,
                    "chapter_title": current_chapter_title,
                    "verse_start": verse_start,
                    "verse_end": verse_end,
                    "verse_label": verse_label,
                    "speaker": current_speaker,
                    "source_pdf_page": pdf_page,
                    "text_parts": [verse_match.group(3)],
                }
                continue

            if current is not None:
                current["text_parts"].append(line)

    flush()
    return chunks


def validate_chunks(chunks: list[dict[str, Any]]) -> None:
    if not chunks:
        raise ValueError("No verse chunks were extracted")
    chapters = {chunk["chapter"] for chunk in chunks}
    if chapters != set(range(1, 19)):
        raise ValueError(f"Expected chapters 1-18, found {sorted(chapters)}")
    chunk_ids = [chunk["chunk_id"] for chunk in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("Duplicate chunk IDs were extracted")

    for chapter, expected_count in EXPECTED_VERSE_COUNTS.items():
        covered = [
            verse
            for chunk in chunks
            if chunk["chapter"] == chapter
            for verse in range(chunk["verse_start"], chunk["verse_end"] + 1)
        ]
        expected = set(range(1, expected_count + 1))
        if set(covered) != expected or len(covered) != len(expected):
            raise ValueError(
                f"Chapter {chapter} verse coverage is invalid: "
                f"expected 1-{expected_count}, found {sorted(set(covered))}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract verse-aware Gita chunks from PDF")
    parser.add_argument("--manifest", type=Path, default=Path("data/sources.json"))
    parser.add_argument("--source-id", default="gita-swarupananda-1909")
    parser.add_argument("--output", type=Path, default=Path("data/processed/gita_chunks.jsonl"))
    args = parser.parse_args()

    source = load_source(args.manifest, args.source_id)
    pdf_path = Path(source["local_path"])
    if not pdf_path.exists():
        raise FileNotFoundError(f"Source PDF not found: {pdf_path}")

    actual_hash = sha256(pdf_path)
    if actual_hash != source["sha256"]:
        raise ValueError(
            f"Checksum mismatch for {pdf_path}: expected {source['sha256']}, got {actual_hash}"
        )

    chunks = extract_chunks(pdf_path, source)
    validate_chunks(chunks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as stream:
        for chunk in chunks:
            stream.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(
        json.dumps(
            {
                "source_id": source["source_id"],
                "chunks": len(chunks),
                "chapters": 18,
                "output": str(args.output),
                "sha256": actual_hash,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
