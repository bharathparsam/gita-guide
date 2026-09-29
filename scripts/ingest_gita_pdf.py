from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader


CHAPTER_NUMBERS = {
    "ONE": 1,
    "TWO": 2,
    "THREE": 3,
    "FOUR": 4,
    "FIVE": 5,
    "SIX": 6,
    "SEVEN": 7,
    "EIGHT": 8,
    "NINE": 9,
    "TEN": 10,
    "ELEVEN": 11,
    "TWELVE": 12,
    "THIRTEEN": 13,
    "FOURTEEN": 14,
    "FIFTEEN": 15,
    "SIXTEEN": 16,
    "SEVENTEEN": 17,
    "EIGHTEEN": 18,
}
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
CHAPTER_PATTERN = re.compile(r"^CHAPTER\s+(" + "|".join(CHAPTER_NUMBERS) + r")$")
TEXT_PATTERN = re.compile(r"^TEXTS?\s+(\d+)(?:[\u2013-](\d+))?$")
SECTION_HEADINGS = {"TRANSLATION", "PURPORT"}
SPEAKER_MARKERS = {
    "sri bhagavan uvaca": "Krishna",
    "arjuna uvaca": "Arjuna",
    "sanjaya uvaca": "Sanjaya",
    "dhrtarastra uvaca": "Dhritarashtra",
}
LEGACY_TRANSLITERATION = str.maketrans(
    {
        "ä": "ā",
        "é": "ī",
        "ü": "ū",
        "å": "ṛ",
        "è": "ṝ",
        "ÿ": "ḷ",
        "ë": "ṇ",
        "ì": "ṅ",
        "ï": "ñ",
        "ö": "ṭ",
        "ò": "ḍ",
        "ñ": "ṣ",
        "ç": "ś",
        "ù": "ḥ",
        "à": "ṁ",
        "Ä": "Ā",
        "É": "Ī",
        "Ü": "Ū",
        "Å": "Ṛ",
        "È": "Ṝ",
        "Ÿ": "Ḷ",
        "Ë": "Ṇ",
        "Ì": "Ṅ",
        "Ï": "Ñ",
        "Ö": "Ṭ",
        "Ò": "Ḍ",
        "Ñ": "Ṣ",
        "Ç": "Ś",
        "Ù": "Ḥ",
        "À": "Ṁ",
    }
)
DEFAULT_CHUNK_SIZE = 1_200
DEFAULT_CHUNK_OVERLAP = 160
DEFAULT_SOURCE_ID = "bhagavad-gita-as-it-is"


@dataclass(slots=True)
class VerseSection:
    chapter: int
    chapter_title: str
    verse_start: int
    verse_end: int
    verse_label: str
    source_pdf_page: int
    speaker: str
    translation_lines: list[str] = field(default_factory=list)
    purport_lines: list[str] = field(default_factory=list)
    preamble_lines: list[str] = field(default_factory=list)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_source(manifest_path: Path, source_id: str) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = next(
        (item for item in manifest["sources"] if item["source_id"] == source_id),
        None,
    )
    if source is None:
        raise ValueError(f"Source {source_id!r} was not found in {manifest_path}")
    return source


def _fold_ascii(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    return "".join(character for character in value if not unicodedata.combining(character))


def _decode_legacy_transliteration(value: str) -> str:
    """Convert the PDF's legacy BBT font mapping to standard Unicode IAST."""
    return value.translate(LEGACY_TRANSLITERATION)


def _speaker_from_preamble(lines: Iterable[str], current: str) -> str:
    folded = " ".join(_fold_ascii(line).casefold() for line in lines)
    folded = re.sub(r"[^a-z\s]", " ", folded)
    folded = " ".join(folded.split())
    for marker, speaker in SPEAKER_MARKERS.items():
        if marker in folded:
            return speaker
    return current


def _join_layout_lines(lines: Iterable[str]) -> str:
    paragraphs: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if not current:
            return
        text = ""
        for raw in current:
            line = " ".join(raw.split())
            if not line:
                continue
            if text.endswith("-") and line[:1].islower():
                text += line
            else:
                text = f"{text} {line}".strip()
        text = re.sub(r"\s+([,.;:?!])", r"\1", text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            paragraphs.append(text)
        current.clear()

    for raw in lines:
        if raw.strip():
            current.append(raw)
        else:
            flush()
    flush()
    return "\n\n".join(paragraphs)


def _extract_sloka(lines: Iterable[str]) -> str:
    """Extract the readable IAST verse block before the word-for-word glossary."""
    verse_lines: list[str] = []
    for raw_line in lines:
        line = " ".join(raw_line.split())
        if not line:
            continue
        if "—" in line:
            break
        if re.search(r"\d", line):
            continue
        letters = [character for character in line if character.isalpha()]
        if letters and sum(character.islower() for character in letters) / len(letters) >= 0.9:
            verse_lines.append(line)
    return "\n".join(verse_lines)


def _split_preserving_separator(text: str, separator: str) -> list[str]:
    if separator == "":
        return list(text)
    if separator == ". ":
        return [part for part in re.split(r"(?<=\.)\s+", text) if part]
    return [part for part in text.split(separator) if part]


def _recursive_units(text: str, chunk_size: int, separators: tuple[str, ...]) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    separator = separators[0]
    parts = _split_preserving_separator(text, separator)
    if len(parts) == 1:
        return _recursive_units(text, chunk_size, separators[1:]) if len(separators) > 1 else [text]

    units: list[str] = []
    joiner = " " if separator in {". ", " "} else separator
    pending = ""
    for part in parts:
        part = part.strip()
        candidate = f"{pending}{joiner if pending else ''}{part}".strip()
        if pending and len(candidate) > chunk_size:
            units.extend(
                _recursive_units(pending, chunk_size, separators[1:])
                if len(pending) > chunk_size and len(separators) > 1
                else [pending]
            )
            pending = part
        else:
            pending = candidate
    if pending:
        units.extend(
            _recursive_units(pending, chunk_size, separators[1:])
            if len(pending) > chunk_size and len(separators) > 1
            else [pending]
        )
    return units


def recursive_split_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split at paragraph, newline, and sentence boundaries with bounded overlap."""
    if chunk_size < 100:
        raise ValueError("chunk_size must be at least 100 characters")
    if not 0 <= chunk_overlap < chunk_size:
        raise ValueError("chunk_overlap must be non-negative and smaller than chunk_size")
    units = _recursive_units(text, chunk_size, ("\n\n", "\n", ". ", " ", ""))
    chunks: list[str] = []
    carry = ""
    for unit in units:
        candidate = f"{carry} {unit}".strip() if carry else unit.strip()
        if len(candidate) > chunk_size and carry:
            candidate = unit.strip()
        chunks.append(candidate)
        if chunk_overlap:
            sentences = re.split(r"(?<=\.)\s+", candidate)
            tail: list[str] = []
            length = 0
            for sentence in reversed(sentences):
                added = len(sentence) + (1 if tail else 0)
                if tail and length + added > chunk_overlap:
                    break
                tail.append(sentence)
                length += added
            carry = " ".join(reversed(tail)).strip()
            if carry == candidate:
                carry = ""
    return [chunk for chunk in chunks if chunk]


def extract_sections(pdf_path: Path) -> list[VerseSection]:
    reader = PdfReader(pdf_path)
    sections: list[VerseSection] = []
    chapter: int | None = None
    chapter_title_parts: list[str] = []
    reading_chapter_title = False
    current: VerseSection | None = None
    current_part = "preamble"
    current_speaker = "Unknown"

    def flush() -> None:
        nonlocal current, current_speaker
        if current is None:
            return
        current_speaker = _speaker_from_preamble(current.preamble_lines, current_speaker)
        current.speaker = current_speaker
        sections.append(current)
        current = None

    for page_number, page in enumerate(reader.pages, start=1):
        text = _decode_legacy_transliteration(
            page.extract_text(extraction_mode="layout") or ""
        )
        for raw_line in text.splitlines():
            line = " ".join(raw_line.split())
            chapter_match = CHAPTER_PATTERN.fullmatch(line)
            if chapter_match:
                flush()
                chapter = CHAPTER_NUMBERS[chapter_match.group(1)]
                chapter_title_parts = []
                reading_chapter_title = True
                current_speaker = "Unknown"
                continue

            text_match = TEXT_PATTERN.fullmatch(line)
            if text_match and chapter is not None:
                flush()
                reading_chapter_title = False
                verse_start = int(text_match.group(1))
                verse_end = int(text_match.group(2) or verse_start)
                current = VerseSection(
                    chapter=chapter,
                    chapter_title=" ".join(chapter_title_parts).strip(),
                    verse_start=verse_start,
                    verse_end=verse_end,
                    verse_label=(
                        str(verse_start)
                        if verse_start == verse_end
                        else f"{verse_start}-{verse_end}"
                    ),
                    source_pdf_page=page_number,
                    speaker=current_speaker,
                )
                current_part = "preamble"
                continue

            if reading_chapter_title:
                if line:
                    chapter_title_parts.append(line)
                continue
            if current is None:
                continue
            if line in SECTION_HEADINGS:
                current_part = line.casefold()
                continue
            getattr(current, f"{current_part}_lines").append(raw_line.rstrip())

    flush()
    for index, section in enumerate(sections):
        if index + 1 < len(sections) and sections[index + 1].chapter == section.chapter:
            next_start = sections[index + 1].verse_start
            if next_start > section.verse_end + 1:
                section.verse_end = next_start - 1
                section.verse_label = f"{section.verse_start}-{section.verse_end}"
        elif section.verse_end < EXPECTED_VERSE_COUNTS[section.chapter]:
            section.verse_end = EXPECTED_VERSE_COUNTS[section.chapter]
            section.verse_label = f"{section.verse_start}-{section.verse_end}"
    return sections


def build_chunks(
    sections: Iterable[VerseSection],
    source: dict[str, Any],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    source_id = str(source["source_id"])
    author = str(source["translator_commentator"])
    for verse in sections:
        sloka = _extract_sloka(verse.preamble_lines)
        for section_name, raw_lines in (
            ("translation", verse.translation_lines),
            ("purport", verse.purport_lines),
        ):
            text = _join_layout_lines(raw_lines)
            if not text:
                continue
            parts = recursive_split_text(
                text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            for index, part in enumerate(parts, start=1):
                chunk_id = (
                    f"{source_id}:{verse.chapter:02d}:"
                    f"{verse.verse_start:03d}-{verse.verse_end:03d}:"
                    f"{section_name}:{index:03d}"
                )
                section_label = (
                    "Verse translation"
                    if section_name == "translation"
                    else "Purport commentary"
                )
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "source_id": source_id,
                        "source_title": source["title"],
                        "chapter": verse.chapter,
                        "chapter_title": verse.chapter_title,
                        "verse_start": verse.verse_start,
                        "verse_end": verse.verse_end,
                        "verse_label": verse.verse_label,
                        "speaker": verse.speaker,
                        "section": section_name,
                        "content_author": author,
                        "sloka": sloka,
                        "source_pdf_page": verse.source_pdf_page,
                        "chunk_index": index,
                        "chunk_count": len(parts),
                        "translation": part,
                        "retrieval_text": (
                            f"{source['title']}, chapter {verse.chapter} "
                            f"({verse.chapter_title}), verse {verse.verse_label}. "
                            f"Verse speaker: {verse.speaker}. {section_label} by {author}. {part}"
                        ),
                    }
                )
    return chunks


def validate_chunks(chunks: list[dict[str, Any]], *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
    if not chunks:
        raise ValueError("No Gita chunks were extracted")
    if {chunk["chapter"] for chunk in chunks} != set(range(1, 19)):
        raise ValueError("Expected chapters 1-18")
    chunk_ids = [chunk["chunk_id"] for chunk in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("Duplicate chunk IDs were extracted")
    if any(len(chunk["translation"]) > chunk_size for chunk in chunks):
        raise ValueError("A chunk exceeds the configured character limit")

    for chapter, expected_count in EXPECTED_VERSE_COUNTS.items():
        translation_ranges = {
            (chunk["verse_start"], chunk["verse_end"])
            for chunk in chunks
            if chunk["chapter"] == chapter and chunk["section"] == "translation"
        }
        covered = [
            verse
            for start, end in sorted(translation_ranges)
            for verse in range(start, end + 1)
        ]
        expected = list(range(1, expected_count + 1))
        if covered != expected:
            raise ValueError(
                f"Chapter {chapter} verse coverage is invalid: "
                f"expected 1-{expected_count}, found {covered}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract and recursively chunk Bhagavad-gita As It Is"
    )
    parser.add_argument("--manifest", type=Path, default=Path("data/sources.json"))
    parser.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    parser.add_argument("--output", type=Path, default=Path("data/processed/gita_chunks.jsonl"))
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
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

    sections = extract_sections(pdf_path)
    chunks = build_chunks(
        sections,
        source,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    validate_chunks(chunks, chunk_size=args.chunk_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for chunk in chunks:
            stream.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    counts = {
        section: sum(chunk["section"] == section for chunk in chunks)
        for section in ("translation", "purport")
    }
    print(
        json.dumps(
            {
                "source_id": source["source_id"],
                "verse_sections": len(sections),
                "chunks": len(chunks),
                "section_chunks": counts,
                "chapters": 18,
                "chunk_size": args.chunk_size,
                "chunk_overlap": args.chunk_overlap,
                "output": str(args.output),
                "source_sha256": actual_hash,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
