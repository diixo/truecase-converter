#!/usr/bin/env python3
"""Context-aware, case-only truecasing for lowercase JSONL corpora.

The script combines a deterministic sentence-case baseline, a file-specific
canonical-name lexicon, and Stanza POS/NER evidence.  Every output row has the
same schema as its input row and only ``text`` is changed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
SENTENCE_END = frozenset(".!?")
ENTITY_TYPES = {
    "PERSON", "ORG", "GPE", "LOC", "FAC", "NORP", "PRODUCT",
    "EVENT", "WORK_OF_ART", "LAW", "LANGUAGE",
}


@dataclass(frozen=True)
class Pair:
    source: tuple[str, ...]
    canonical: tuple[str, ...]


def alphabetic_tokens(text: str) -> list[str]:
    return [m.group(0) for m in WORD_RE.finditer(text)]


def load_pairs(path: Path) -> list[Pair]:
    pairs: list[Pair] = []
    seen: set[tuple[str, ...]] = set()
    skipped = 0
    with path.open(encoding="utf-8-sig") as handle:
        for line_no, raw in enumerate(handle, 1):
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                continue
            if " - " not in raw:
                raise ValueError(f"{path}:{line_no}: expected 'source - Canonical'")
            left, right = raw.split(" - ", 1)
            source = tuple(t.lower() for t in alphabetic_tokens(left))
            canonical = tuple(alphabetic_tokens(right))
            # A possessive apostrophe may be restored (``amastras -> Amastra's``).
            # Other spelling and punctuation rewrites stay out of this pipeline.
            if (not source or len(source) != len(canonical)
                    or tuple(t.lower().replace("'", "").replace("’", "")
                             for t in canonical) != source):
                skipped += 1
                continue
            if source not in seen:
                pairs.append(Pair(source, canonical))
                seen.add(source)
    if skipped:
        print(f"Ignored {skipped} non-case-only pair(s) from {path}", file=sys.stderr)
    return sorted(pairs, key=lambda p: len(p.source), reverse=True)


def sentence_baseline(text: str) -> str:
    """Capitalize sentence starts and standalone 'i', preserving all bytes but case."""
    chars = list(text)
    need_capital = True
    for match in WORD_RE.finditer(text):
        token = match.group(0)
        start, end = match.span()
        if need_capital:
            chars[start] = chars[start].upper()
        if token.lower() == "i":
            chars[start] = "I"
        need_capital = False
        if any(ch in SENTENCE_END for ch in text[end:match.end()]):
            need_capital = True

        # Punctuation between this token and the next token determines whether
        # the next alphabetic token begins a sentence.
        next_match = WORD_RE.search(text, end)
        gap_end = next_match.start() if next_match else len(text)
        if any(ch in SENTENCE_END for ch in text[end:gap_end]):
            need_capital = True
    return "".join(chars)


def allowed_truecase_equal(source: str, result: str) -> bool:
    """Accept case changes and apostrophes inserted into the result."""
    source_index = result_index = 0
    while source_index < len(source) and result_index < len(result):
        a, b = source[source_index], result[result_index]
        if b in "'’" and a not in "'’":
            result_index += 1
            continue
        if not (a == b or (a.isalpha() and b.isalpha() and a.lower() == b.lower())):
            return False
        source_index += 1
        result_index += 1
    return source_index == len(source) and all(ch in "'’" for ch in result[result_index:])


# Backward-compatible public name used by earlier callers/tests.
case_only_equal = allowed_truecase_equal


def apply_token_cases(text: str, replacements: dict[int, str]) -> str:
    matches = list(WORD_RE.finditer(text))
    result = text
    # Descending offsets keep all earlier token offsets valid when an apostrophe
    # makes a later replacement one character longer.
    for token_index, canonical in sorted(replacements.items(), reverse=True):
        match = matches[token_index]
        source = match.group(0)
        if source.lower() != canonical.lower().replace("'", "").replace("’", ""):
            continue
        result = result[:match.start()] + canonical + result[match.end():]
    return result


def make_stanza_pipeline(use_gpu: bool):
    try:
        import stanza
        return stanza.Pipeline(
            "en", processors="tokenize,pos,ner", use_gpu=use_gpu,
            verbose=False, download_method=None,
        )
    except Exception as exc:
        raise RuntimeError(
            "Could not load Stanza English tokenize/POS/NER resources. "
            "Install stanza and run: python -m stanza.download en"
        ) from exc


def stanza_evidence(nlp, texts: Sequence[str], batch_size: int = 128) -> list[set[int]]:
    """Return alphabetic-token indices supported as proper names by POS or NER."""
    evidence: list[set[int]] = []
    for chunk_start in range(0, len(texts), batch_size):
        chunk = texts[chunk_start:chunk_start + batch_size]
        docs = nlp.bulk_process(list(chunk))
        for text, doc in zip(chunk, docs):
            spans = list(WORD_RE.finditer(text))
            supported: set[int] = set()
            for i, span in enumerate(spans):
                for ent in doc.ents:
                    if ent.type in ENTITY_TYPES and span.start() < ent.end_char and span.end() > ent.start_char:
                        supported.add(i)
                        break
            for sentence in doc.sentences:
                for word in sentence.words:
                    if word.upos != "PROPN" or word.start_char is None:
                        continue
                    for i, span in enumerate(spans):
                        if span.start() < word.end_char and span.end() > word.start_char:
                            supported.add(i)
            evidence.append(supported)
    return evidence


def pair_occurrences(text: str, pairs_by_first: dict[str, list[Pair]]):
    matches = list(WORD_RE.finditer(text))
    lowered = [m.group(0).lower() for m in matches]
    occupied: set[int] = set()
    found: list[tuple[Pair, tuple[int, ...]]] = []
    for start, first in enumerate(lowered):
        for pair in pairs_by_first.get(first, ()):  # longest first
            width = len(pair.source)
            if start + width > len(lowered):
                continue
            indices = tuple(range(start, start + width))
            if any(i in occupied for i in indices):
                continue
            if tuple(lowered[start:start + width]) != pair.source:
                continue
            found.append((pair, indices))
            occupied.update(indices)
            break
    return found


def truecase_records(
    rows: list[dict], pairs: Sequence[Pair], evidence: Sequence[set[int]],
    context_records: int, mode: str,
) -> list[dict]:
    pairs_by_first: dict[str, list[Pair]] = defaultdict(list)
    for pair in pairs:
        pairs_by_first[pair.source[0]].append(pair)
    for candidates in pairs_by_first.values():
        candidates.sort(key=lambda pair: len(pair.source), reverse=True)
    occurrences = [pair_occurrences(row["text"], pairs_by_first) for row in rows]
    confident_by_form: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for row_index, found in enumerate(occurrences):
        for pair, indices in found:
            if set(indices) & evidence[row_index]:
                confident_by_form[pair.source].append(row_index)

    output: list[dict] = []
    for row_index, row in enumerate(rows):
        original = row["text"]
        baseline = sentence_baseline(original)
        replacements: dict[int, str] = {}
        for pair, indices in occurrences[row_index]:
            local_support = bool(set(indices) & evidence[row_index])
            nearby_support = any(
                abs(row_index - seen_at) <= context_records
                for seen_at in confident_by_form[pair.source]
            )
            acronym = any(sum(ch.isupper() for ch in token) > 1 for token in pair.canonical)
            possessive_restore = any(
                ("'" in canonical or "’" in canonical)
                and "'" not in source and "’" not in source
                for source, canonical in zip(pair.source, pair.canonical)
            )
            accept = (
                mode == "aggressive"
                or len(pair.source) > 1
                or acronym
                or possessive_restore
                or local_support
                or nearby_support
            )
            if accept:
                replacements.update(zip(indices, pair.canonical))
        result = apply_token_cases(baseline, replacements)
        if not allowed_truecase_equal(original, result):
            raise AssertionError(f"truecase invariant failed for id={row.get('id')}")
        new_row = dict(row)
        new_row["text"] = result
        output.append(new_row)
    return output


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line_no, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            row = json.loads(raw)
            if not isinstance(row.get("text"), str):
                raise ValueError(f"{path}:{line_no}: missing string field 'text'")
            rows.append(row)
    return rows


def parse_args(argv: Iterable[str] | None = None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--context-records", type=int, default=20)
    parser.add_argument("--mode", choices=("balanced", "aggressive"), default="balanced")
    parser.add_argument("--no-stanza", action="store_true", help="Use rules/pairs only")
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--batch-size", type=int, default=128,
                        help="Records per Stanza bulk call (default: 128)")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = args.output or args.input.with_name(args.input.stem + "_truecased.jsonl")
    if output_path.resolve() == args.input.resolve():
        print("Refusing to overwrite the input file", file=sys.stderr)
        return 2
    rows = read_jsonl(args.input)
    pairs = load_pairs(args.pairs)
    if args.no_stanza:
        evidence = [set() for _ in rows]
    else:
        evidence = stanza_evidence(
            make_stanza_pipeline(args.gpu), [row["text"] for row in rows], args.batch_size
        )
    results = truecase_records(rows, pairs, evidence, args.context_records, args.mode)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in results:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    changed = sum(a["text"] != b["text"] for a, b in zip(rows, results))
    print(f"Wrote {len(results):,} rows to {output_path} ({changed:,} changed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
