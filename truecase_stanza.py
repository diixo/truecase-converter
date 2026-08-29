"""Run contextual truecasing with Stanza POS/NER evidence."""

import time
from pathlib import Path
from typing import Sequence

from contextual_truecase import (
    PROGRESS_EVERY,
    WORD_RE,
    add_builtin_pairs,
    load_pairs,
    load_person_name_pairs,
    merge_pairs,
    print_progress,
    read_jsonl,
    truecase_records,
    write_jsonl,
)


INPUT_FILE = Path("splitted/bookcorpus_part_01160.jsonl")
PAIRS_FILE = Path("truecased/bookcorpus_part_01160_truecase_pairs.txt")
PERSON_NAMES_FILE = Path("data/person_names_truecase.json")
OUTPUT_FILE = Path("truecased/bookcorpus_part_01160_stanza_truecased.jsonl")

USE_GPU = True
BATCH_SIZE = 100
CONTEXT_RECORDS = 20
MODE = "balanced"

ENTITY_TYPES = {
    "PERSON", "ORG", "GPE", "LOC", "FAC", "NORP", "PRODUCT",
    "EVENT", "WORK_OF_ART", "LAW", "LANGUAGE", "NAMED_OBJ",
}


def make_stanza_pipeline():
    try:
        import stanza
        return stanza.Pipeline(
            "en", processors="tokenize,pos,ner", use_gpu=USE_GPU,
            verbose=False, download_method=None,
        )
    except Exception as exc:
        raise RuntimeError(
            "Could not load Stanza English tokenize/POS/NER resources. "
            "Install stanza and run: python -m stanza.download en"
        ) from exc


def stanza_evidence(nlp, texts: Sequence[str]) -> list[set[int]]:
    """Return alphabetic-token indices supported as proper names by POS or NER."""
    evidence: list[set[int]] = []
    started_at = time.perf_counter()
    for chunk_start in range(0, len(texts), BATCH_SIZE):
        chunk = texts[chunk_start:chunk_start + BATCH_SIZE]
        docs = nlp.bulk_process(list(chunk))
        for text, doc in zip(chunk, docs):
            spans = list(WORD_RE.finditer(text))
            supported: set[int] = set()
            for index, span in enumerate(spans):
                if any(
                    ent.type in ENTITY_TYPES
                    and span.start() < ent.end_char and span.end() > ent.start_char
                    for ent in doc.ents
                ):
                    supported.add(index)
            for sentence in doc.sentences:
                for word in sentence.words:
                    if word.upos != "PROPN" or word.start_char is None:
                        continue
                    for index, span in enumerate(spans):
                        if span.start() < word.end_char and span.end() > word.start_char:
                            supported.add(index)
            evidence.append(supported)
        processed = min(chunk_start + len(chunk), len(texts))
        if processed % PROGRESS_EVERY == 0 or processed == len(texts):
            print_progress("stanza", processed, len(texts), started_at)
    return evidence


def main() -> int:
    print(f"Reading {INPUT_FILE} ...", flush=True)
    rows = read_jsonl(INPUT_FILE)
    pairs = add_builtin_pairs(merge_pairs(
        load_pairs(PAIRS_FILE), load_person_name_pairs(PERSON_NAMES_FILE)
    ))
    print(f"Loaded {len(rows):,} records and {len(pairs):,} canonical pairs", flush=True)
    evidence = stanza_evidence(make_stanza_pipeline(), [row["text"] for row in rows])
    results = truecase_records(
        rows, pairs, evidence, CONTEXT_RECORDS, MODE, propagate_evidence=True
    )
    write_jsonl(INPUT_FILE, OUTPUT_FILE, rows, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
