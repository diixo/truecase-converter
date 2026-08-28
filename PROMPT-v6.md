# Contextual Truecasing — Fast Parallel v6

## Цель

Преобразовать поле `text` в JSONL-файле в truecase. Разрешено изменять только регистр существующих букв. Порядок записей, `id`, остальные поля, написание, пробелы и пунктуация должны сохраняться.

Результат именуется:

```text
<source_name>_truecased.jsonl
```

## Быстрый алгоритм

1. Python выполняет grammatical baseline:
   - первый алфавитный символ записи;
   - начало предложения после `.`, `?`, `!`;
   - начало реплики после открывающей кавычки;
   - отдельное местоимение `i` → `I`;
   - однозначные месяцы: `january`, `february`, `april`, `june`, `july`, `september`, `october`, `november`, `december`.
2. Файл делится на stateless-блоки по 100 target-записей.
3. Каждый модельный запрос получает `10 context_before + 100 targets + 10 context_after`.
4. До 12 независимых блоков обрабатываются параллельно.
5. Модель возвращает только решения о регистре собственных имён.
6. Если контекста мало, соответствующий блок повторяется с 40 записями до и после.
7. Python применяет решения и проверяет case-only инвариант.

## Разрешённые типы

- `person` — имя, фамилия, полное имя, инициалы, подтверждённый персональный псевдоним;
- `place` — конкретное географическое или вымышленное место;
- `organization` — именованная компания, учреждение или формальная группа;
- `month` — контекстно подтверждённый календарный месяц для `may`, `march`, `august`;
- `deity` — собственное имя божества или уникально подразумеваемого Бога;
- `named_object` — собственное имя объекта: корабля, буксира, автомобиля, поезда, самолёта, космического аппарата, станции, машины, оружия, артефакта или именованного продукта;
- `work` — контекстно подтверждённое собственное название произведения;
- `event` — собственное название конкретного события;
- `other_named` — другое однозначно подтверждённое собственное имя, не подходящее к предыдущим классам.

### Важные разграничения

- `Bertie` → `named_object`, если контекст показывает, что это имя корабля или буксира.
- `bertie` не капитализируется только потому, что такая форма может быть именем человека или объекта.
- `God` → `deity`, когда речь идёт об уникально подразумеваемом Боге.
- `a god`, `the gods`, `his god` могут оставаться строчными, если контекст использует общее значение.
- `Rose`, `Will`, `Hope`, `Mark`, `May`, `March`, `August`, `Lord` и похожие формы решаются отдельно по контексту.
- Общее слово, звание, обращение или название предмета не становится собственным именем только из-за частоты либо позиции.

## Вход модели

```json
{
  "mode": "base_context",
  "context_before": [
    {"id": 11440187, "text": "..."}
  ],
  "targets": [
    {
      "index": 0,
      "id": 11440197,
      "text": "Buckman returned to bertie .",
      "tokens": ["buckman", "returned", "to", "bertie"]
    }
  ],
  "context_after": [
    {"id": 11440207, "text": "..."}
  ]
}
```

- `text` уже содержит grammatical baseline.
- `tokens` содержит все исходные алфавитные токены записи.
- `index` — локальный индекс target-записи внутри блока.
- Боковой контекст разрешено только читать; решения применяются только к `targets`.

## Системный промпт модели

```text
You are the semantic proper-name casing stage of a fast English truecasing pipeline.
Use only the supplied local narrative. Do not browse, search, call tools, use
external facts, summarize the text, or describe characters or plot.

The technical pipeline has already handled grammatical sentence beginnings,
the standalone pronoun I, and unambiguous month names. Do not review or return
those changes.

Examine every alphabetic token in every target record. Return casing decisions
for all proper names that are semantically established by the supplied context:

- person names, surnames, full names, initials, and established personal aliases
  as person;
- geographic and fictional place names as place;
- organization names as organization;
- contextually calendar uses of may, march, and august as month;
- proper divine names as deity;
- names of ships, vehicles, spacecraft, stations, machines, weapons, artifacts,
  and named products as named_object;
- specific work titles as work;
- specific named events as event;
- any other unmistakable proper name as other_named.

A named_object is a particular object with an established individual name.
Capitalize Bertie when the context establishes Bertie as the name of a tug or
ship. Do not capitalize a generic tug, ship, station, machine, weapon, or product.

Capitalize God as deity when the narrative uniquely refers to the monotheistic
God. Keep generic uses such as a god or the gods lowercase. Decide ambiguous
religious uses from the local narrative rather than applying a global rule.

Do not capitalize generic titles, ranks, forms of address, generic headings,
nationalities, demonyms, species, common objects, or ordinary words. Position,
frequency, NER-like appearance, and the fact that a word can be a name are not
evidence. Resolve ambiguous forms such as will, rose, mark, hope, may, march,
august, god, lord, or bertie by meaning in the current occurrence.

Each target contains original lowercase alphabetic tokens and a provisionally
sentence-cased text. Return casing decisions, not rewritten records.

Use global_decisions only when a lowercase form has one unambiguous proper-name
meaning in every occurrence inside the current target block. Never propagate a
global decision outside this block. If a form can also be common or refers to
different entities, return only the confirmed occurrences through
occurrence_decisions.

For occurrence_decisions, index is the local target-record index, token is the
zero-based alphabetic-token index, source must be copied exactly from tokens,
and canonical may change letter case only. For a multiword proper name, return a
decision for every token whose case must change.

If the 10+100+10 window is insufficient, put the affected target index in
needs_context_indices instead of guessing. In expanded_context mode, make the
best final semantic decision and return an empty needs_context_indices.

Before returning, silently audit every target record token by token for missed
proper names. Pay special attention to named_object, deity, informal names,
fictional names, and names that resemble ordinary words. Return only JSON.
```

## Ответ модели

```json
{
  "global_decisions": [
    {
      "source": "bertie",
      "canonical": "Bertie",
      "type": "named_object"
    }
  ],
  "occurrence_decisions": [
    {
      "index": 42,
      "token": 3,
      "source": "god",
      "canonical": "God",
      "type": "deity"
    }
  ],
  "needs_context_indices": []
}
```

Разрешённые значения `type`:

```text
person
place
organization
month
deity
named_object
work
event
other_named
```

## Правила решений

### `global_decisions`

- Решение применяется ко всем точным употреблениям `source` только внутри текущих 100 target-записей.
- Решение разрешено только при одном однозначном значении формы во всём блоке.
- Решение не переносится в соседние блоки или по всему файлу.

### `occurrence_decisions`

- Используется для неоднозначной формы или отдельного контекстно подтверждённого употребления.
- `index` и `token` должны точно адресовать употребление.
- Решение применяется только к указанному токену.

### `needs_context_indices`

- Если локального окна недостаточно, модель не угадывает.
- Блок повторяется в `expanded_context` с 40 записями до и после.

## Инварианты

- `source` точно копируется из `targets[].tokens`.
- `canonical` имеет ту же длину и совпадает с `source` без учёта регистра.
- Нельзя менять написание, буквы, цифры, символы, пробелы и пунктуацию.
- Нельзя добавлять апострофы или исправлять опечатки.
- Нельзя менять `id`, порядок или остальные поля JSONL.
- Нельзя возвращать переписанный текст, объяснения либо суммаризацию.

После применения проверяется каждый символ: он должен либо совпадать с исходным, либо отличаться только регистром той же буквы.

## Запрещено

- Hugging Face и его кэш;
- локальные языковые модели;
- интернет и внешние источники;
- перенос сущностей по всему файлу;
- подтверждение имени только по частоте, позиции, NER или шаблону вроде `X said`;
- пересказ или описание содержания файла.
