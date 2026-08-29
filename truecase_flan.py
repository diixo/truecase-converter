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
    pair_occurrences,
    print_progress,
    read_jsonl,
    truecase_records,
    write_jsonl,
)


INPUT_FILE = Path("splitted/bookcorpus_part_01160.jsonl")
PAIRS_FILE = Path("truecased/bookcorpus_part_01160_truecase_pairs.txt")
OUTPUT_FILE = Path("truecased/bookcorpus_part_01160_truecased.jsonl")

MODEL = "google/flan-t5-large"
USE_GPU = True
BATCH_SIZE = 2
MODEL_CONTEXT_RECORDS = 5
MAX_INPUT_TOKENS = 512
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
    texts: Sequence[str], row_index: int, candidates: Sequence[tuple[int, str]],
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


def flan_evidence(texts: Sequence[str], pairs: Sequence[Pair]) -> list[set[int]]:
    """Resolve every single-word pair occurrence with FLAN-T5."""
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
    jobs: list[tuple[int, list[tuple[int, str]], str]] = []
    for row_index, text in enumerate(texts):
        candidates = [
            (indices[0], pair.canonical[0])
            for pair, indices in pair_occurrences(text, pairs_by_first)
            if len(pair.source) == 1
        ]
        if candidates:
            jobs.append((row_index, candidates, make_flan_prompt(
                texts, row_index, candidates, MODEL_CONTEXT_RECORDS
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


def main() -> int:
    print(f"Reading {INPUT_FILE} ...", flush=True)
    rows = read_jsonl(INPUT_FILE)
    pairs = add_builtin_pairs(load_pairs(PAIRS_FILE))
    print(f"Loaded {len(rows):,} records and {len(pairs):,} canonical pairs", flush=True)
    evidence = flan_evidence([row["text"] for row in rows], pairs)
    results = truecase_records(
        rows, pairs, evidence, CONTEXT_RECORDS, MODE, propagate_evidence=True
    )
    write_jsonl(INPUT_FILE, OUTPUT_FILE, rows, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
