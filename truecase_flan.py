"""Run contextual truecasing with FLAN-T5 decisions per occurrence."""

import re
import time
from pathlib import Path
from typing import Sequence

from contextual_truecase import (
    PROGRESS_EVERY,
    WORD_RE,
    Pair,
    add_builtin_pairs,
    index_pairs,
    load_pairs,
    load_person_name_pairs,
    merge_pairs,
    pair_occurrences,
    print_progress,
    read_jsonl,
    truecase_records,
    write_jsonl,
)


INPUT_FILE = Path("splitted/bookcorpus_part_01160.jsonl")
PAIRS_FILE: Path | None = None  # Or Path("truecased/bookcorpus_part_01160_truecase_pairs.txt")
PERSON_NAMES_FILE = Path("data/person_names_truecase.json")
OUTPUT_FILE = Path("truecased/bookcorpus_part_01160_truecased.jsonl")

MODEL = "google/flan-t5-large"
USE_GPU = True
BATCH_SIZE = 2
MODEL_CONTEXT_RECORDS = 5
MAX_INPUT_TOKENS = 512
MAX_CANDIDATES_PER_PROMPT = 10
CONTEXT_RECORDS = 20
MODE = "balanced"


def parse_flan_answer(answer: str, candidate_count: int) -> set[int] | None:
    """Parse a terse FLAN answer; None means malformed, not a negative decision."""
    value = answer.strip()
    if value.upper().rstrip(".") == "NONE":
        return set()
    # FLAN sometimes wraps an otherwise valid terse answer in [] or appends a
    # final period. Explanatory prose remains invalid and is never trusted.
    value = value.rstrip(".").strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1].strip()
    if not re.fullmatch(r"\d+(?:\s*,\s*\d+)*", value):
        return None
    selected = {int(item) for item in re.findall(r"\d+", value)}
    return {item for item in selected if 0 <= item < candidate_count}


def make_flan_prompt(
    texts: Sequence[str], row_index: int,
    candidates: Sequence[tuple[int, str, bool]],
    context_records: int,
) -> str:
    context_start = max(0, row_index - context_records)
    context_end = min(len(texts), row_index + context_records + 1)
    before = "\n".join(text[-500:] for text in texts[context_start:row_index]) or "(none)"
    after = "\n".join(text[:500] for text in texts[row_index + 1:context_end]) or "(none)"
    target = texts[row_index]
    if len(target) > 1_500:
        spans = list(WORD_RE.finditer(target))
        excerpts = []
        for token_index, _, _ in candidates:
            span = spans[token_index]
            excerpts.append(target[max(0, span.start() - 300):span.end() + 300])
        target = "\n[...]\n".join(dict.fromkeys(excerpts))
    choices = "\n".join(
        f"{choice}: token={token_index}, canonical={canonical}, "
        f"common_person_name={'yes' if is_person_name else 'no'}"
        for choice, (token_index, canonical, is_person_name) in enumerate(candidates)
    )
    return (
        "Decide which candidate words in TARGET are proper names or named objects. "
        "Use the narrative context. Do not select ordinary words, verbs, months used "
        "generically, titles, or common nouns. common_person_name=yes is a useful "
        "prior, not proof: select it only when this occurrence denotes a person. "
        "Return only comma-separated candidate "
        "numbers, or NONE.\n\n"
        f"CANDIDATES:\n{choices}\n\nTARGET:\n{target}\n\n"
        f"CONTEXT BEFORE:\n{before}\n\nCONTEXT AFTER:\n{after}\n\nANSWER:"
    )


def build_flan_candidates(
    text: str, pairs_by_first: dict[str, list[Pair]],
    person_name_sources: set[str],
) -> list[tuple[int, str, bool]]:
    """Create a closed candidate set; FLAN cannot introduce another token."""
    known_candidates = {
        indices[0]: (pair.canonical[0], pair.source[0] in person_name_sources)
        for pair, indices in pair_occurrences(text, pairs_by_first)
        if len(pair.source) == 1
    }
    return [
        (token_index, canonical, is_person_name)
        for token_index, (canonical, is_person_name) in sorted(known_candidates.items())
    ]


def flan_evidence(
    texts: Sequence[str], pairs: Sequence[Pair], person_name_sources: set[str],
) -> list[set[int]]:
    """Let FLAN select only among supplied candidates, never generate new names."""
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    print(f"Loading FLAN resolver: {MODEL} ...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    tokenizer.truncation_side = "right"
    dtype = torch.float16 if USE_GPU and torch.cuda.is_available() else torch.float32
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL, dtype=dtype)
    device = torch.device("cuda" if USE_GPU and torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    declared_limits = [MAX_INPUT_TOKENS]
    tokenizer_limit = getattr(tokenizer, "model_max_length", None)
    if isinstance(tokenizer_limit, int) and tokenizer_limit < 1_000_000:
        declared_limits.append(tokenizer_limit)
    model_limit = getattr(model.config, "n_positions", None)
    if isinstance(model_limit, int) and model_limit > 0:
        declared_limits.append(model_limit)
    input_limit = min(declared_limits)
    print(f"FLAN encoder input limit: {input_limit} tokens", flush=True)

    pairs_by_first = index_pairs(pairs)
    jobs: list[tuple[int, list[tuple[int, str, bool]], str]] = []
    for row_index, text in enumerate(texts):
        candidates = build_flan_candidates(
            text, pairs_by_first, person_name_sources
        )

        for start in range(0, len(candidates), MAX_CANDIDATES_PER_PROMPT):
            candidate_group = candidates[start:start + MAX_CANDIDATES_PER_PROMPT]
            jobs.append((row_index, candidate_group, make_flan_prompt(
                texts, row_index, candidate_group, MODEL_CONTEXT_RECORDS
            )))

    evidence = [set() for _ in texts]
    started_at = time.perf_counter()
    truncated_prompts = 0
    malformed_answers = 0
    for batch_start in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[batch_start:batch_start + BATCH_SIZE]
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
            selected = parse_flan_answer(answer, len(candidates))
            if selected is None:
                malformed_answers += 1
                continue
            for choice in selected:
                evidence[row_index].add(candidates[choice][0])
        processed = min(batch_start + len(batch), len(jobs))
        if processed % PROGRESS_EVERY == 0 or processed == len(jobs):
            print_progress("flan", processed, len(jobs), started_at)
    print(f"FLAN prompts truncated safely: {truncated_prompts:,}/{len(jobs):,}", flush=True)
    print(f"FLAN malformed answers ignored: {malformed_answers:,}/{len(jobs):,}", flush=True)
    return evidence


def build_candidate_pairs(
    pairs_file: Path | None, person_names_file: Path,
) -> tuple[list[Pair], set[str]]:
    """Build candidates with file pairs > person names > built-ins priority."""
    person_name_pairs = load_person_name_pairs(person_names_file)
    person_name_sources = {
        pair.source[0] for pair in person_name_pairs if len(pair.source) == 1
    }
    if pairs_file is None:
        file_pairs = []
        print(
            "Pairs file disabled (PAIRS_FILE = None); "
            "using person names and built-in contractions only",
            flush=True,
        )
    elif pairs_file.exists():
        file_pairs = load_pairs(pairs_file)
    else:
        file_pairs = []
        print(
            f"WARNING: pairs file not found: {pairs_file}; "
            "using person names and built-in contractions only",
            flush=True,
        )
    pairs = add_builtin_pairs(merge_pairs(file_pairs, person_name_pairs))
    return pairs, person_name_sources


def main() -> int:

    print(f"Reading {INPUT_FILE} ...", flush=True)
    rows = read_jsonl(INPUT_FILE)

    pairs, person_name_sources = build_candidate_pairs(PAIRS_FILE, PERSON_NAMES_FILE)

    print(f"Loaded {len(rows):,} records and {len(pairs):,} canonical pairs", flush=True)
    evidence = flan_evidence(
        [row["text"] for row in rows], pairs, person_name_sources
    )

    results = truecase_records(
        rows, pairs, evidence, CONTEXT_RECORDS, MODE, propagate_evidence=True
    )
    write_jsonl(INPUT_FILE, OUTPUT_FILE, rows, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
