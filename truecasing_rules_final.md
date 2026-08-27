# Strict Contextual Truecasing for BookCorpus JSONL

## Purpose

This document defines the mandatory truecasing procedure for BookCorpus-style JSONL files.

The goal is to restore correct capitalization while changing **only letter case**.

The implementation must preserve the original text exactly apart from capitalization.

---

# 1. Core Architecture

The required architecture is:

```text
local context window
    -> LLM semantic analysis
    -> casing decisions for all potentially named expressions
    -> Python applies those already-decided case changes
    -> structural and case-only validation
```

The LLM is the semantic decision-maker.

Python is only the execution and validation layer.

---

# 2. Non-Deviation Requirement

The implementation **MUST follow this architecture exactly**.

Do not replace the LLM semantic pass with:

- dictionaries;
- global entity maps used as detectors;
- regex-based name/entity detection;
- candidate extraction pipelines;
- heuristic rules;
- frequency analysis;
- whitelist-based detection;
- NER tools;
- local language models;
- Hugging Face models;
- global replacement tables;
- automatic propagation rules;
- shortcuts that avoid semantic review of every context window.

The LLM **MUST semantically review every context window** and make casing decisions for all potentially named expressions in that window.

Python is strictly limited to:

- reading JSONL;
- applying already-decided casing changes;
- writing JSONL;
- validating structure;
- validating case-only invariants.

If a faster or simpler implementation conflicts with this architecture, **do not use it**.

Do not optimize away the LLM semantic pass.

Do not silently change the algorithm during execution.

If the task cannot be executed according to this architecture, **do not substitute another method**. State the limitation explicitly instead.

---

# 3. Sequential Contextual Processing

Process the file sequentially using overlapping context windows of approximately **5–8 neighboring records/sentences**.

If the current window is insufficient to decide whether a lowercase expression is a proper noun, expand the context.

Each record must be interpreted as part of its surrounding narrative, not as an isolated sentence.

For every record, the LLM must consider **all semantically referential expressions**, including:

- people;
- character names;
- first names;
- surnames;
- titles;
- nicknames;
- geographic names;
- countries;
- cities;
- streets;
- buildings;
- institutions;
- organizations;
- companies;
- brands;
- book/work titles;
- historical events;
- astronomical objects;
- peoples and nationalities;
- abbreviations;
- weekdays;
- months;
- fictional races;
- fictional technologies;
- named objects;
- unique fictional entities.

## Coverage Rule

**Do not consider a record complete until every potentially referential lowercase expression in that record has been semantically reviewed.**

The objective is not merely to detect obvious names.

The objective is to ensure complete coverage of all possible named expressions.

---

# 4. Semantic Decision Rule

Capitalization decisions must come from **semantic interpretation of context**.

The LLM must determine whether a lowercase expression represents:

- a unique person;
- a place;
- an organization;
- an institution;
- a title;
- a brand;
- a calendar proper name;
- an abbreviation;
- a fictional proper noun;
- or an ordinary common word.

No surface pattern alone is sufficient.

Examples:

```text
a baby girl named emily
```

Contextually:

```text
Emily
```

But the rule is **not**:

```text
named X -> capitalize X
```

The phrase is only evidence. The final decision must still be semantic.

Likewise:

```text
raoul signals the other grays
```

must become:

```text
Raoul signals the other grays
```

because `Raoul` is understood as a person in context.

---

# 5. Dynamic Context Expansion

The default context window is approximately 5–8 neighboring records.

Expand the context when necessary.

Examples of when to expand:

- an unfamiliar lowercase name appears only once;
- a surname is introduced much earlier;
- a fictional place is referenced indirectly;
- a pronoun or role must be resolved to identify a character;
- a term may be either a common noun or proper noun;
- a title is introduced separately from the name;
- a unique fictional object is defined several lines earlier.

The algorithm must prefer semantic certainty over a fixed window size.

---

# 6. Fragment / Book Boundaries

A single 10,000-row JSONL file may contain multiple independent books or fragments.

Entity context may only persist inside the current coherent book/story fragment.

When a new unrelated work begins:

```text
RESET semantic entity memory
RESET entity ledger
RESET assumptions from the previous book
```

Do not propagate capitalization decisions across unrelated books.

---

# 7. Entity Ledger

After the LLM has **semantically confirmed** an entity, it may retain a temporary entity ledger for the current book.

Example:

```text
raoul -> Raoul -> PERSON
harris -> Harris -> PERSON
milky way -> Milky Way -> PLACE
```

The ledger is allowed only as **memory of already-understood entities**.

It is **not** a detection mechanism.

The ledger must never be used to decide that an unseen lowercase token is an entity merely because it resembles another known token.

The correct sequence is:

```text
LLM discovers entity semantically
    -> entity may be stored in ledger
    -> ledger assists later consistency checking
```

Not:

```text
word matches dictionary
    -> assume entity
```

---

# 8. One-Off Entities

A proper noun must be restored even if it occurs only once in the entire book.

Frequency must not influence whether something is considered an entity.

Examples:

```text
Emily
Raoul
Harris
Oxford
```

A single occurrence is sufficient if the semantic context establishes the identity.

---

# 9. Compound Entity Spans

Prefer complete semantic spans over isolated token decisions.

Example:

```text
henry thomas
```

must be considered first as:

```text
Henry Thomas
```

rather than separately deciding:

```text
Henry
thomas
```

Likewise:

```text
milky way terminal
```

should be resolved as:

```text
Milky Way Terminal
```

Longer confirmed spans should be applied before shorter spans.

This prevents failures such as:

```text
Henry thomas
```

---

# 10. Ambiguity-First Policy

If the same lowercase surface form may be either a common word or proper noun, **never assign it a global casing rule**.

Each occurrence must be resolved from context.

Examples:

```text
may have -> may have
May 18 -> May 18

march forward -> march forward
March 2026 -> March 2026

rose from the chair -> rose from the chair
Rose entered the room -> Rose entered the room

the bill was high -> bill
Bill entered the room -> Bill
```

This applies to all ambiguous lexical forms.

---

# 11. Calendar Audit

Weekdays and months require a dedicated audit.

## Weekdays

Check for:

```text
Monday
Tuesday
Wednesday
Thursday
Friday
Saturday
Sunday
```

## Months

Check for:

```text
January
February
March
April
May
June
July
August
September
October
November
December
```

Ambiguous forms such as `may` and `march` must still be resolved semantically.

Example:

```text
he may have no choice
```

must remain:

```text
he may have no choice
```

while:

```text
Friday , May 18
```

must restore:

```text
Friday , May 18
```

---

# 12. Abbreviation Audit

Perform a dedicated contextual audit for abbreviations.

Examples may include:

```text
NASA
CIA
FBI
OHSU
ITS
U.S.
BC
```

Do not uppercase a token merely because it matches letters of a known abbreviation.

The surrounding context must confirm the abbreviation identity.

---

# 13. Proper-Place / Institution Audit

A separate coverage check must verify named places and institutions.

Examples:

```text
Oxford
Hart Senate Building
Capitol Building
Milky Way Terminal
New York City
Chicago Terminal
Oregon Health and Science University
```

Do not assume that a lowercase geographical or institutional expression is ordinary merely because it appears only once.

---

# 14. Pass 1 — Semantic Discovery

Perform a full sequential pass over the book/fragment.

For each context window:

1. read all records in the window;
2. understand the narrative context;
3. inspect every record;
4. identify every potentially named lowercase expression;
5. decide its correct casing semantically;
6. record exact casing decisions for concrete spans;
7. update the entity ledger only after semantic confirmation.

Do not skip expressions because they look rare, unfamiliar, or insignificant.

---

# 15. Pass 2 — Entity Consistency

After Pass 1, reread the same book/fragment.

Use the understanding gained during the first pass to detect missed lowercase occurrences of already-known entities.

Check:

- full name vs first name;
- surname-only mentions;
- titles plus surname;
- abbreviated institution names;
- repeated fictional place names;
- repeated organization names.

Example:

If later context establishes:

```text
Raoul -> PERSON
```

then earlier and later `raoul` occurrences inside the same book must be reviewed.

Ambiguous words must still be checked locally before capitalization.

---

# 16. Pass 3 — Missed-Entity Coverage Audit

Perform an independent third semantic audit.

For **every record**, ask:

> Does this record still contain any lowercase expression that semantically refers to a unique named entity or calendar proper name?

Review categories separately:

```text
PERSON
PLACE
ORGANIZATION
INSTITUTION
TITLE
BRAND
CALENDAR
ABBREVIATION
FICTIONAL_ENTITY
ASTRONOMICAL_ENTITY
HISTORICAL_EVENT
```

This pass is specifically designed to catch entities that were **never noticed at all** during the first two passes.

Examples of errors this pass must catch:

```text
harris
emily
raoul
oxford
```

---

# 17. Pass 4 — Calendar / Abbreviation / Proper-Place Audit

Perform another focused audit for:

- weekdays;
- months;
- abbreviations;
- geographic proper nouns;
- institutional names;
- rare one-off names.

This pass exists because these categories are easy to overlook during narrative reading.

Examples:

```text
monday -> Monday
oxford -> Oxford
nasa -> NASA
```

only where semantically correct.

---

# 18. Pass 5 — Structural Validation

After all semantic decisions have been made and applied, validate the output.

For every record:

```python
before["text"].lower() == after["text"].lower()
```

Also verify:

```text
same number of records
same JSON keys
same IDs
same record order
same punctuation
same whitespace
same words
same spelling
same token boundaries
```

Only capitalization may differ.

---

# 19. Python Restrictions

Python may only:

- read JSONL;
- preserve records;
- apply exact case changes already decided by the LLM;
- write JSONL;
- validate invariants.

Python must **not**:

- discover names;
- infer entity types;
- use regex to decide proper nouns;
- build candidate lists as a semantic detector;
- use frequencies to infer entities;
- automatically capitalize all matching tokens;
- decide casing from syntax;
- replace the LLM contextual analysis.

Python is an **application layer**, not a semantic reasoning layer.

---

# 20. Forbidden Decision Mechanisms

The following are forbidden as the primary casing decision mechanism:

- regex name detection;
- NER model inference;
- Hugging Face models;
- local language models;
- name databases;
- candidate lists;
- whitelist matching;
- frequency-based entity detection;
- capitalization dictionaries;
- global `word -> casing` tables;
- heuristics such as:

```text
X said -> X is a name
named X -> X is a name
Mr. X -> X must always be a surname everywhere
```

These patterns may provide contextual evidence to the LLM, but **must not make the final decision automatically**.

---

# 21. Text Preservation Rules

Change **only letter case**.

Do not:

- correct spelling;
- repair grammar;
- add punctuation;
- delete punctuation;
- add apostrophes;
- remove apostrophes;
- split words;
- merge words;
- normalize whitespace;
- change quotation marks;
- change wording;
- reorder tokens;
- rewrite sentences;
- alter JSON fields;
- alter IDs;
- alter record count.

Example source:

```text
ms. robertsyes
```

Allowed truecasing:

```text
Ms. Robertsyes
```

Forbidden correction:

```text
Ms. Roberts yes
```

because inserting the missing boundary changes the text.

---

# 22. First-Person Pronoun

Restore standalone lowercase:

```text
i
```

to:

```text
I
```

only when it is semantically the English first-person pronoun.

Do not blindly change embedded letter `i` inside words.

---

# 23. Sentence-Initial Capitalization

Restore normal English capitalization at the beginning of a sentence/record.

However, **sentence-initial capitalization must be applied only after semantic span decisions**.

Bad order:

```text
henry thomas
-> Henry thomas
```

then full-span matching fails.

Correct order:

```text
henry thomas
-> semantic span: Henry Thomas
-> sentence-initial handling afterward
```

---

# 24. Order of Application

Recommended application order:

```text
1. Longest confirmed semantic entity spans
2. Shorter confirmed entity spans
3. Context-specific ambiguous decisions
4. Calendar / abbreviation decisions
5. Standalone first-person I
6. Sentence-initial capitalization
7. Structural invariant validation
```

The order of **semantic reasoning**, however, is always contextual LLM analysis first.

---

# 25. Quality Gate

A file is not complete until all five passes have been performed:

```text
Pass 1: Semantic Discovery
Pass 2: Entity Consistency
Pass 3: Missed-Entity Coverage Audit
Pass 4: Calendar / Abbreviation / Proper-Place Audit
Pass 5: Structural Invariant Validation
```

Do not issue the converted file before completing all passes.

---

# 26. Coverage Is the Primary Metric

The key quality metric is not:

```text
How many known entities were replaced?
```

It is:

```text
Was every potentially named expression in every record semantically reviewed?
```

The algorithm must be optimized for **coverage**, not speed or convenience.

---

# 27. Regression Examples

The algorithm must prevent all of the following failures.

## Full name

Wrong:

```text
Henry thomas it said .
```

Correct:

```text
Henry Thomas it said .
```

## Ambiguous month/modal

Wrong:

```text
It occurred to Henry that he May have no choice but to tell the truth .
```

Correct:

```text
It occurred to Henry that he may have no choice but to tell the truth .
```

## Rare surname

Wrong:

```text
It was unfortunate that harris had been killed on the docks .
```

Correct:

```text
It was unfortunate that Harris had been killed on the docks .
```

## One-off first name

Wrong:

```text
A baby girl named emily ; she died birthing her third child .
```

Correct:

```text
A baby girl named Emily ; she died birthing her third child .
```

## Weekday

Wrong:

```text
But well be leaving next monday .
```

Correct:

```text
But well be leaving next Monday .
```

## Rare character name

Wrong:

```text
I look up and raoul signals the other grays to leave the area .
```

Correct:

```text
I look up and Raoul signals the other grays to leave the area .
```

## Proper institution/place

Wrong:

```text
That lab-grown kidney they say theyve perfected at oxford ?
```

Correct:

```text
That lab-grown kidney they say theyve perfected at Oxford ?
```

---

# 28. Output Filename

For a source file such as:

```text
bookcorpus_part_01130(4).jsonl
bookcorpus_part_01131(3).jsonl
```

the output must be:

```text
bookcorpus_part_01130_truecased.jsonl
bookcorpus_part_01131_truecased.jsonl
```

Do not preserve source suffixes such as:

```text
(1)
(2)
(3)
(4)
```

in the output filename.

---

# 29. Final Operational Rule

The LLM must never silently replace this workflow with an easier implementation.

If there is a conflict between:

```text
speed / convenience
```

and:

```text
full contextual LLM review
```

choose:

```text
full contextual LLM review
```

If that cannot be done, report the limitation instead of substituting a dictionary-driven or heuristic method.

---

# 30. Execution Compliance Protocol

The rules in this document are not advisory.

They define the exact execution algorithm and MUST be followed literally.

This protocol exists to prevent silent replacement of the required semantic workflow with a faster dictionary-driven, candidate-driven, heuristic, regex-based, frequency-based, or otherwise approximate implementation.

## 30.1 Mandatory Chunk Execution

The file MUST be processed sequentially in bounded chunks.

Recommended working chunk:

- 50–100 target rows;
- plus overlapping surrounding context sufficient to understand those rows;
- default local semantic context of approximately 5–8 neighboring rows around the currently reviewed material;
- expand context whenever semantic interpretation requires it.

For every chunk:

1. The LLM must read the actual text of **every target row**.
2. The LLM must semantically inspect **every target row**.
3. Candidate preselection is forbidden.
4. A row may not be marked complete merely because no already-known entity was found.
5. Every potentially referential lexical span must receive an explicit semantic decision.
6. New and one-off entities must be discoverable directly from the row even if they have never appeared before.
7. Only after all target rows have been semantically reviewed may Python apply the casing changes.
8. Python may not generate additional semantic casing decisions.
9. The next chunk must not begin until the current target rows have completed semantic review.

The mandatory direction is:

```text
full target rows
    -> LLM reads every row
    -> semantic inspection of the complete row
    -> identify all potentially referential expressions
    -> explicit casing decisions
    -> Python applies those exact decisions
```

Never:

```text
known-entity list
    -> candidate extraction
    -> selected matches only
    -> bulk replacement
```

Never:

```text
Python scans file
    -> Python proposes likely names
    -> LLM reviews only those candidates
```

Never:

```text
existing Entity Ledger
    -> find matching strings
    -> assume remaining text contains no entities
```

---

## 30.2 Mandatory Per-Row Coverage Condition

For each target row, the LLM must explicitly ask:

> Have I semantically considered every lowercase lexical expression or multi-word span in this row that could plausibly denote a named, unique, referential, calendar, institutional, geographic, fictional, branded, titled, cultural, product, work, event, astronomical, nationality/language, or abbreviated entity?

If the answer is not explicitly yes after examining the actual row text, the row is **NOT complete**.

The review must not be limited to conventional PERSON / PLACE / ORGANIZATION entities.

Potentially named expressions include, but are not limited to:

```text
PERSON
CHARACTER
FIRST_NAME
SURNAME
NICKNAME
PLACE
COUNTRY
CITY
STREET
BUILDING
ORGANIZATION
INSTITUTION
COMPANY
BRAND
PRODUCT
FOOD_OR_DRINK_NAME
TITLE
BOOK_TITLE
FILM_TITLE
SONG_TITLE
WORK_OF_ART
HISTORICAL_EVENT
ASTRONOMICAL_ENTITY
NATIONALITY
PEOPLE
LANGUAGE
CALENDAR
ABBREVIATION
FICTIONAL_RACE
FICTIONAL_ENTITY
FICTIONAL_TECHNOLOGY
NAMED_OBJECT
VEHICLE
SHIP
BUILDING
LAW
LEGAL_ACT
PROGRAM
PROJECT
MISSION
EVENT
```

This category list is a coverage reminder only.

It MUST NOT become a candidate detector or whitelist.

An expression outside this list must still be restored if semantic context shows that it is a proper name.

---

## 30.3 No Candidate-Preselection Shortcut

Do NOT first extract a subset of likely names and then review only that subset.

The direction MUST always be:

```text
full row
→ semantic inspection
→ identify named expressions
```

Never:

```text
candidate detector
→ selected expressions
→ semantic inspection
```

The LLM must inspect the **entire lexical content** of the row.

The absence of a match in:

- an Entity Ledger;
- a dictionary;
- a known-name list;
- previous rows;
- a regex;
- an NER system;
- a frequency table;

does **not** provide evidence that the row contains no proper names.

---

## 30.4 New / One-Off Entity Discovery Requirement

Every row must be capable of introducing a completely new entity.

The LLM must therefore actively consider lowercase expressions that have never appeared previously.

Examples:

```text
a baby girl named emily
-> Emily

at oxford
-> Oxford

a shirley temple he had prepared himself
-> a Shirley Temple he had prepared himself
```

The `Shirley Temple` example is especially important.

In:

```text
Eustace sat back down in his seat and took a sip from a shirley temple he had prepared himself .
```

the expression:

```text
shirley temple
```

must be semantically examined because the context:

```text
took a sip from a ...
```

indicates a named drink.

Correct:

```text
Eustace sat back down in his seat and took a sip from a Shirley Temple he had prepared himself .
```

This entity must be discovered even if:

- `Shirley` has never appeared as a person;
- `Temple` has never appeared as an entity;
- `Shirley Temple` is absent from the Entity Ledger;
- it occurs only once in the entire file.

Failure to inspect such an expression means the row was not fully reviewed.

---

## 30.5 Lexical-Span Review Requirement

Semantic review must consider both:

```text
single-token expressions
```

and:

```text
multi-token expressions
```

The LLM must not assume that entity boundaries are known in advance.

For example, in:

```text
a shirley temple
```

the relevant semantic span is:

```text
shirley temple
```

not necessarily the individual tokens:

```text
shirley
temple
```

Likewise:

```text
milky way terminal
```

must be considered as a possible complete named span before shorter alternatives.

The semantic pass should prefer the **longest contextually meaningful referential span**.

---

## 30.6 Mandatory Internal Review Record

Before declaring a chunk complete, maintain an internal review record for every target row.

Minimum conceptual structure:

```json
{
  "row_id": 11350024,
  "reviewed": true,
  "referential_spans": [
    {
      "surface": "Eustace",
      "decision": "proper_name",
      "canonical_case": "Eustace"
    },
    {
      "surface": "shirley temple",
      "decision": "named_drink",
      "canonical_case": "Shirley Temple"
    }
  ],
  "case_changes": [
    {
      "from": "shirley temple",
      "to": "Shirley Temple"
    }
  ]
}
```

This review record is **execution evidence**.

It is not:

- an Entity Ledger;
- a global replacement dictionary;
- a candidate list;
- a detection mechanism.

A row with:

```json
{"reviewed": true}
```

but no evidence that its lexical content was actually inspected is not sufficient.

---

## 30.7 Entity Ledger Separation

The Entity Ledger and the per-row review record serve different purposes.

### Per-row review record

Answers:

```text
What did the LLM inspect in this concrete row?
What semantic decisions were made here?
```

### Entity Ledger

Answers:

```text
Which entities have already been semantically confirmed in this coherent story fragment?
What canonical casing should be remembered for consistency?
```

The Entity Ledger must never replace the per-row semantic review.

Correct:

```text
read complete row
    -> discover / classify expressions semantically
    -> consult ledger for consistency where relevant
```

Forbidden:

```text
scan row for ledger matches
    -> apply matches
    -> mark row reviewed
```

---

## 30.8 Mandatory Chunk Completion Gate

A chunk may be marked complete only when all of the following are true:

```text
[ ] Every target row was actually read by the LLM.
[ ] Every target row received a semantic coverage review.
[ ] New / one-off entities were allowed to emerge from any row.
[ ] Multi-word spans were considered.
[ ] No candidate-preselection mechanism determined what the LLM inspected.
[ ] Ambiguous expressions were resolved from local context.
[ ] All semantic casing decisions were recorded before Python application.
[ ] Python only applied already-decided case changes.
[ ] The case-only invariant still holds.
```

If any item is false, the chunk is incomplete.

---

## 30.9 Independent Coverage Audit Must Re-read the Text

Pass 3 (`Missed-Entity Coverage Audit`) must be a **real independent reread of the actual rows**.

It is forbidden to implement Pass 3 merely as:

```text
search for lowercase versions of entities already found in Pass 1
```

or:

```text
search for known entity categories
```

or:

```text
check only the Entity Ledger
```

Pass 3 must independently ask of every row:

> Is there any lowercase expression in the actual row text that denotes a proper, named, unique, referential, cultural, product, work, event, calendar, institutional, geographic, fictional, or abbreviated entity that previous passes failed to identify?

The purpose of Pass 3 is specifically to discover entities that are **not yet present in the Entity Ledger**.

Examples include:

```text
Shirley Temple
Oxford
Harris
Emily
Raoul
```

---

## 30.10 No Silent Algorithm Substitution

The LLM must never silently replace this workflow with:

- a known-entity dictionary;
- a hand-built entity dictionary;
- automatic title casing;
- regex matching;
- NER;
- named candidate extraction;
- frequency analysis;
- title/name databases;
- global search-and-replace;
- a smaller subset of rows;
- representative sampling;
- spot checking;
- "likely entity" scanning;
- any other shortcut.

This prohibition applies even when the alternative:

- is faster;
- appears highly accurate;
- passes several regression examples;
- preserves the case-only invariant;
- successfully restores many known entities.

Passing regression examples does not prove semantic coverage.

---

## 30.11 Python Enforcement Boundary

Python is permitted to:

```text
read JSONL
store LLM decisions
apply exact LLM-decided case changes
write JSONL
verify IDs
verify keys
verify row order
verify row count
verify before["text"].lower() == after["text"].lower()
```

Python is forbidden to:

```text
decide that a word is a name
generate an entity dictionary from the corpus
extract likely entity candidates for the LLM
infer capitalization from syntactic position
infer capitalization from "named X"
infer capitalization from "X said"
infer capitalization from frequency
decide capitalization from regex
decide capitalization from an external name list
capitalize every occurrence of a previously seen surface form without contextual review
```

Python may mechanically apply a decision only **after** that concrete casing decision has been made semantically by the LLM.

---

## 30.12 Completion Claim Restriction

Do NOT state:

```text
full semantic pass completed
coverage audit completed
all rows reviewed
fully compliant with the rules
```

unless every target row was actually inspected under this protocol.

If only part of the file was reviewed, state that execution was partial.

If only known entities were checked, state that only an entity-consistency check was performed.

If only regression examples were checked, state that only regression verification was performed.

Never label a partial or shortcut-based process as a full semantic audit.

---

## 30.13 Failure Rule

If resource, context, execution, or tooling constraints prevent this protocol from being followed exactly:

**STOP THE CONVERSION.**

Do not silently switch to:

- dictionary replacement;
- candidate lists;
- heuristic extraction;
- regex detection;
- NER;
- bulk capitalization;
- representative sampling;
- another approximate algorithm.

Explicitly report:

```text
The required exhaustive semantic execution protocol could not be completed.
No substitute algorithm was used.
```

A partial correctly-described result is preferable to a falsely claimed complete result.

---

## 30.14 Final Compliance Principle

The execution standard is:

```text
EVERY ROW MUST BE READ.
EVERY ROW MUST BE SEMANTICALLY REVIEWED.
EVERY POTENTIALLY REFERENTIAL LOWERCASE EXPRESSION MUST BE CONSIDERED.
NEW ENTITIES MUST BE DISCOVERABLE WITHOUT BEING PRELISTED.
PYTHON MUST NEVER MAKE THE SEMANTIC DECISION.
```

A truecased output is not considered compliant merely because:

- structural validation passes;
- known regression cases pass;
- known entities are consistently capitalized;
- an Entity Ledger is comprehensive.

The primary compliance question remains:

> Was every potentially named expression in every record semantically reviewed from the actual text?

If not, the conversion is incomplete.

