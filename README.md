# truecase-converter

## Context-aware JSONL pipeline

`contextual_truecase.py` preserves row order, IDs and JSON fields. Apart from
letter case, it may restore possessive apostrophes defined by canonical pairs
(`amastras -> Amastra's`); other punctuation and spelling stay unchanged. In balanced mode,
multiword canonical pairs are applied directly; ambiguous one-word pairs need
local Stanza POS/NER evidence or supporting evidence within the context window.

Stanza and FLAN-T5 have separate files and output paths. Edit the constants at
the beginning of the selected runner, then run it without parameters:

```powershell
python truecase_flan.py
python truecase_stanza.py
```

`INPUT_FILE`, `PAIRS_FILE`, and `OUTPUT_FILE` select the files. In
`truecase_flan.py`, `MODEL`, `USE_GPU`, `BATCH_SIZE`,
`MODEL_CONTEXT_RECORDS`, and `MAX_INPUT_TOKENS` configure FLAN. In
`truecase_stanza.py`, `USE_GPU` and `BATCH_SIZE` configure Stanza. Both runners
also expose `CONTEXT_RECORDS` and `MODE`. Progress is printed every 100 records.

Every single-word pair is resolved by the selected contextual model; there is
no hardcoded word blacklist. Positive evidence is propagated only to nearby
occurrences of the exact same source spelling, reducing intermittent NER/model
misses without conflating forms such as `ferio` and `fiero`. Multiword pairs and
explicit possessive-apostrophe restorations are applied deterministically.

Built-in missing-apostrophe pairs are `im -> I'm`, `ive -> I've`,
`ill -> I'll`, and `id -> I'd`. The first two are deterministic; ambiguous
`ill` and `id` require confirmation from the contextual resolver.

`data/person_names_truecase.json` contributes additional person-name candidates.
For FLAN, dictionary membership is passed as a probabilistic hint rather than
an unconditional capitalization rule, so common-word homonyms remain contextual.
Tokens absent from the configured pairs and person-name dictionary are not sent
to FLAN as candidates. Candidate groups are capped by
`MAX_CANDIDATES_PER_PROMPT` to preserve the model's limited encoder context.

FLAN input is capped by the smallest of `MAX_INPUT_TOKENS`, the tokenizer
limit, and the model's declared position limit. Candidates and target text are
placed first, so only trailing context is lost when a prompt must be truncated.
When `ALLOW_CONTEXT_EXTENSION = True`, `MAX_INPUT_TOKENS` is used directly even
above the declared 512-token limit. This retains more context but increases VRAM
use and does not guarantee the same model quality.

Stanza and its English resources must already be installed. If necessary:

```powershell
pip install stanza
python -m stanza.download en
```

Run the regression checks with `python -m unittest -v`.
