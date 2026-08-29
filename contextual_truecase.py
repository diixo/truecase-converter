#!/usr/bin/env python3
"""Context-aware, case-only truecasing for lowercase JSONL corpora.

The script combines a deterministic sentence-case baseline, a file-specific
canonical-name lexicon, and Stanza POS/NER evidence. Every output row has the
same schema as its input row; ``text`` may change case and restore explicitly
configured possessive apostrophes.
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


# ---------------------------------------------------------------------------
# Configuration: edit these values, then run ``python contextual_truecase.py``.
# ---------------------------------------------------------------------------
INPUT_FILE = Path("splitted/bookcorpus_part_01160.jsonl")
PAIRS_FILE = Path("truecased/bookcorpus_part_01160_truecase_pairs.txt")
OUTPUT_FILE = Path("truecased/bookcorpus_part_01160_truecased.jsonl")

USE_STANZA = False
USE_GPU = True
STANZA_BATCH_SIZE = 100
FLAN_MODEL = "google/flan-t5-large"
FLAN_BATCH_SIZE = 2
FLAN_CONTEXT_RECORDS = 3
FLAN_MAX_INPUT_TOKENS = 512
PROGRESS_EVERY = 100
CONTEXT_RECORDS = 20
MODE = "balanced"  # "balanced" or "aggressive"


WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
SENTENCE_END = frozenset(".!?")
ENTITY_TYPES = {
    "PERSON", "ORG", "GPE", "LOC", "FAC", "NORP", "PRODUCT",
    "EVENT", "WORK_OF_ART", "LAW", "LANGUAGE", "NAMED_OBJ",
}
# NAMED_OBJ is reserved for a custom/future NER resolver. The stock English
# Stanza OntoNotes model has no such label; named ships may instead appear as
# PRODUCT/ORG, or be detected through PROPN and the canonical-pairs file.


@dataclass(frozen=True)
class Pair:
    source: tuple[str, ...]
    canonical: tuple[str, ...]


BUILTIN_CONTRACTION_PAIRS = (
    Pair(("im",), ("I'm",)),
    Pair(("ive",), ("I've",)),
    Pair(("ill",), ("I'll",)),
    Pair(("id",), ("I'd",)),
)
CONTEXTUAL_CONTRACTIONS = {"ill", "id"}


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


def add_builtin_pairs(pairs: Sequence[Pair]) -> list[Pair]:
    """Add contraction repairs, preferring explicit file-specific pairs."""
    result = list(pairs)
    existing = {pair.source for pair in result}
    result.extend(pair for pair in BUILTIN_CONTRACTION_PAIRS if pair.source not in existing)
    return sorted(result, key=lambda pair: len(pair.source), reverse=True)


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


def print_progress(phase: str, processed: int, total: int, started_at: float) -> None:
    elapsed = max(time.perf_counter() - started_at, 1e-9)
    percent = processed / total * 100 if total else 100.0
    speed = processed / elapsed
    eta = (total - processed) / speed if speed else 0.0
    print(
        f"[{phase}] {processed:,}/{total:,} ({percent:6.2f}%) | "
        f"{speed:,.1f} records/s | elapsed {elapsed:.1f}s | ETA {eta:.1f}s",
        flush=True,
    )


def stanza_evidence(nlp, texts: Sequence[str], batch_size: int = 100) -> list[set[int]]:
    """Return alphabetic-token indices supported as proper names by POS or NER."""
    evidence: list[set[int]] = []
    started_at = time.perf_counter()
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
        processed = min(chunk_start + len(chunk), len(texts))
        if processed % PROGRESS_EVERY == 0 or processed == len(texts):
            print_progress("stanza", processed, len(texts), started_at)
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


def index_pairs(pairs: Sequence[Pair]) -> dict[str, list[Pair]]:
    pairs_by_first: dict[str, list[Pair]] = defaultdict(list)
    for pair in pairs:
        pairs_by_first[pair.source[0]].append(pair)
    for candidates in pairs_by_first.values():
        candidates.sort(key=lambda pair: len(pair.source), reverse=True)
    return pairs_by_first


def make_flan_prompt(
    texts: Sequence[str], row_index: int, candidates: Sequence[tuple[int, str]],
) -> str:
    context_start = max(0, row_index - FLAN_CONTEXT_RECORDS)
    context_end = min(len(texts), row_index + FLAN_CONTEXT_RECORDS + 1)
    before = "\n".join(text[-500:] for text in texts[context_start:row_index]) or "(none)"
    after = "\n".join(text[:500] for text in texts[row_index + 1:context_end]) or "(none)"
    target = texts[row_index]
    if len(target) > 1_500:
        spans = list(WORD_RE.finditer(target))
        excerpts = []
        for token_index, _ in candidates:
            span = spans[token_index]
            excerpts.append(target[max(0, span.start() - 300):span.end() + 300])
        target = "\n[...]\n".join(dict.fromkeys(excerpts))
    choices = "\n".join(
        f"{choice}: token={token_index}, canonical={canonical}"
        for choice, (token_index, canonical) in enumerate(candidates)
    )
    return (
        "Decide which candidate words in TARGET are proper names or named objects. "
        "Use the narrative context. Do not select ordinary words, verbs, months used "
        "generically, titles, or common nouns. Return only comma-separated candidate "
        "numbers, or NONE.\n\n"
        f"CANDIDATES:\n{choices}\n\nTARGET:\n{target}\n\n"
        f"CONTEXT BEFORE:\n{before}\n\nCONTEXT AFTER:\n{after}\n\nANSWER:"
    )


def flan_evidence(
    texts: Sequence[str], pairs: Sequence[Pair], model_name: str = FLAN_MODEL,
) -> list[set[int]]:
    """Resolve context-sensitive pair occurrences with FLAN-T5."""
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    print(f"Loading FLAN resolver: {model_name} ...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    # Candidate definitions and TARGET are intentionally at the beginning of
    # the prompt. If context has to be shortened, discard only its tail.
    tokenizer.truncation_side = "right"
    dtype = torch.float16 if USE_GPU and torch.cuda.is_available() else torch.float32
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name, torch_dtype=dtype)
    device = torch.device("cuda" if USE_GPU and torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    declared_limits = [FLAN_MAX_INPUT_TOKENS]
    tokenizer_limit = getattr(tokenizer, "model_max_length", None)
    if isinstance(tokenizer_limit, int) and tokenizer_limit < 1_000_000:
        declared_limits.append(tokenizer_limit)
    model_limit = getattr(model.config, "n_positions", None)
    if isinstance(model_limit, int) and model_limit > 0:
        declared_limits.append(model_limit)
    input_limit = min(declared_limits)
    print(f"FLAN encoder input limit: {input_limit} tokens", flush=True)

    pairs_by_first = index_pairs(pairs)
    jobs: list[tuple[int, list[tuple[int, str]], str]] = []
    for row_index, text in enumerate(texts):
        candidates: list[tuple[int, str]] = []
        for pair, indices in pair_occurrences(text, pairs_by_first):
            if len(pair.source) != 1:
                continue
            candidates.append((indices[0], pair.canonical[0]))
        if candidates:
            jobs.append((row_index, candidates, make_flan_prompt(texts, row_index, candidates)))

    evidence = [set() for _ in texts]
    started_at = time.perf_counter()
    truncated_prompts = 0
    for batch_start in range(0, len(jobs), FLAN_BATCH_SIZE):
        batch = jobs[batch_start:batch_start + FLAN_BATCH_SIZE]
        prompts = [job[2] for job in batch]
        prompt_lengths = [
            len(ids) for ids in tokenizer(
                prompts, add_special_tokens=True, truncation=False
            )["input_ids"]
        ]
        truncated_prompts += sum(length > input_limit for length in prompt_lengths)
        encoded = tokenizer(
            prompts, return_tensors="pt", padding=True,
            truncation=True, max_length=input_limit,
        ).to(device)
        if encoded["input_ids"].shape[1] > input_limit:
            raise AssertionError("FLAN tokenizer exceeded the encoder input limit")
        with torch.inference_mode():
            generated = model.generate(
                **encoded, max_new_tokens=32, do_sample=False, num_beams=1,
            )
        answers = tokenizer.batch_decode(generated, skip_special_tokens=True)
        for (row_index, candidates, _), answer in zip(batch, answers):
            if answer.strip().upper() == "NONE":
                continue
            if not re.fullmatch(r"\s*\d+(?:\s*,\s*\d+)*\s*", answer):
                continue
            selected = {int(value) for value in re.findall(r"\d+", answer)}
            for choice in selected:
                if 0 <= choice < len(candidates):
                    evidence[row_index].add(candidates[choice][0])
        processed = min(batch_start + len(batch), len(jobs))
        if processed % PROGRESS_EVERY == 0 or processed == len(jobs):
            print_progress("flan", processed, len(jobs), started_at)
    print(
        f"FLAN prompts truncated safely: {truncated_prompts:,}/{len(jobs):,}",
        flush=True,
    )
    return evidence


def truecase_records(
    rows: list[dict], pairs: Sequence[Pair], evidence: Sequence[set[int]],
    context_records: int, mode: str, propagate_evidence: bool = True,
) -> list[dict]:
    pairs_by_first = index_pairs(pairs)
    occurrences = [pair_occurrences(row["text"], pairs_by_first) for row in rows]
    confident_by_form: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for row_index, found in enumerate(occurrences):
        for pair, indices in found:
            if set(indices) & evidence[row_index]:
                confident_by_form[pair.source].append(row_index)

    output: list[dict] = []
    started_at = time.perf_counter()
    for row_index, row in enumerate(rows):
        original = row["text"]
        baseline = sentence_baseline(original)
        replacements: dict[int, str] = {}
        for pair, indices in occurrences[row_index]:
            local_support = bool(set(indices) & evidence[row_index])
            nearby_support = any(
                abs(row_index - seen_at) <= context_records
                for seen_at in confident_by_form[pair.source]
            ) if propagate_evidence else False
            possessive_restore = any(
                ("'" in canonical or "’" in canonical)
                and "'" not in source and "’" not in source
                for source, canonical in zip(pair.source, pair.canonical)
            ) and pair.source[0] not in CONTEXTUAL_CONTRACTIONS
            accept = (
                mode == "aggressive"
                or len(pair.source) > 1
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
        processed = row_index + 1
        if processed % PROGRESS_EVERY == 0 or processed == len(rows):
            print_progress("truecase", processed, len(rows), started_at)
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


def main() -> int:
    if MODE not in {"balanced", "aggressive"}:
        raise ValueError("MODE must be 'balanced' or 'aggressive'")
    if STANZA_BATCH_SIZE < 1:
        raise ValueError("STANZA_BATCH_SIZE must be positive")
    if PROGRESS_EVERY < 1:
        raise ValueError("PROGRESS_EVERY must be positive")
    if OUTPUT_FILE.resolve() == INPUT_FILE.resolve():
        print("Refusing to overwrite the input file", file=sys.stderr)
        return 2
    print(f"Reading {INPUT_FILE} ...", flush=True)
    rows = read_jsonl(INPUT_FILE)
    pairs = add_builtin_pairs(load_pairs(PAIRS_FILE))
    print(f"Loaded {len(rows):,} records and {len(pairs):,} canonical pairs", flush=True)
    if USE_STANZA:
        evidence = stanza_evidence(
            make_stanza_pipeline(USE_GPU),
            [row["text"] for row in rows],
            STANZA_BATCH_SIZE,
        )
    else:
        evidence = flan_evidence([row["text"] for row in rows], pairs)
    # Stanza produces sparse evidence, so nearby propagation helps recover
    # missed mentions. FLAN explicitly decides every single-word occurrence;
    # a positive answer must therefore never leak to a neighbouring occurrence.
    results = truecase_records(
        rows, pairs, evidence, CONTEXT_RECORDS, MODE,
        propagate_evidence=USE_STANZA,
    )
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8", newline="\n") as handle:
        for row in results:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    changed = sum(a["text"] != b["text"] for a, b in zip(rows, results))
    print(f"Wrote {len(results):,} rows to {OUTPUT_FILE} ({changed:,} changed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
