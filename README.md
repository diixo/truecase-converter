# truecase-converter

## Context-aware JSONL pipeline

`contextual_truecase.py` preserves row order, IDs and JSON fields. Apart from
letter case, it may restore possessive apostrophes defined by canonical pairs
(`amastras -> Amastra's`); other punctuation and spelling stay unchanged. In balanced mode,
multiword canonical pairs are applied directly; ambiguous one-word pairs need
local Stanza POS/NER evidence or supporting evidence within the context window.

Edit the configuration constants at the beginning of `contextual_truecase.py`,
then run it without command-line parameters:

```powershell
python contextual_truecase.py
```

`INPUT_FILE`, `PAIRS_FILE`, and `OUTPUT_FILE` select the files. `USE_GPU`,
`STANZA_BATCH_SIZE`, `CONTEXT_RECORDS`, `USE_STANZA`, and `MODE` control the
processing strategy.

Stanza and its English resources must already be installed. If necessary:

```powershell
pip install stanza
python -m stanza.download en
```

Run the regression checks with `python -m unittest -v`.

