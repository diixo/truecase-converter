# Contextual Truecasing — Fast Parallel v9

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
- `other_named` — другое однозначно подтверждённое собственное имя, включая уникальное название вымышленного народа, цивилизации, расы или вида, не подходящее к предыдущим классам.

### Важные разграничения

- `Bertie` → `named_object`, если контекст показывает, что это имя корабля или буксира.
- `bertie` не капитализируется только потому, что такая форма может быть именем человека или объекта.
- `God` → `deity`, когда речь идёт об уникально подразумеваемом Боге.
- `a god`, `the gods`, `his god` могут оставаться строчными, если контекст использует общее значение.
- `Keo` и `Keos` → `other_named`, когда контекст устанавливает `Keo` как уникальное название вымышленного народа, расы или цивилизации; наличие рядом слова `species` не делает такое название нарицательным.
- Обычное биологическое название вида или общий класс существ остаётся строчным.
- Если в источнике пропущен апостроф (`keos` в значении `Keo's`), разрешено восстановить только регистр: `Keos`. Добавлять апостроф или исправлять написание запрещено.
- Временное, вымышленное, принятое или позднее опровергнутое имя остаётся собственным именем: `Aidlev` → `person`, если повествование устанавливает, что конкретного человека называют этим именем; форма `aidlevs` восстанавливается как `Aidlevs` без добавления апострофа.
- Семантически связанное обращение к конкретному собеседнику может подтверждать имя вместе с соседним диалогом и последующими упоминаниями. Одна запятая, позиция слова или шаблон реплики сами по себе доказательством не являются.
- Обычное слово, капитализированное внутри составного названия, не получает глобальный регистр: в `Modern Lives magazine` слово `Lives` является частью названия, а в `he lives in...` слово `lives` остаётся глаголом со строчной буквы.
- Если точная строчная форма имеет в target-блоке хотя бы одно иное значение, для именованных употреблений разрешены только `occurrence_decisions`; `global_decision` для этой формы запрещён.
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
- уникальные названия вымышленных народов, цивилизаций, рас или видов как
  `other_named`, когда контекст устанавливает, что обозначение функционирует
  как собственное имя конкретной группы;
- any other unmistakable proper name as other_named.

Персональный псевдоним, принятое имя, имя прикрытия или имя, которое позднее
оказывается ненастоящим, всё равно является собственным именем человека во всех
употреблениях, где конкретного человека называют этим именем. Поэтому возвращай
`Aidlev` и форму `Aidlevs` с исправлением только регистра, если повествование
устанавливает соответствующего конкретного носителя имени.

Интерпретируй отношения обращения и референции семантически. Незнакомая форма
может быть подтверждена как имя человека соседним диалогом, если она устойчиво
обозначает конкретного человека, к которому обращаются или которого обсуждают.
Никогда не принимай решение только по запятой, позиции в предложении, шаблону
диалога или механическому правилу. Незнакомое написание не является доводом
против статуса собственного имени.

A named_object is a particular object with an established individual name.
Capitalize Bertie when the context establishes Bertie as the name of a tug or
ship. Do not capitalize a generic tug, ship, station, machine, weapon, or product.

Capitalize God as deity when the narrative uniquely refers to the monotheistic
God. Keep generic uses such as a god or the gods lowercase. Decide ambiguous
religious uses from the local narrative rather than applying a global rule.

Пиши с прописной буквы уникальное название вымышленного народа, цивилизации,
расы или вида, когда локальное повествование использует его как собственное имя
этой группы. Поэтому возвращай `Keo` или `Keos`, когда такое значение
подтверждено. Соседнее слово `species` само по себе не является основанием
оставлять название строчным. Общие биологические названия видов и классов
существ оставляй строчными.

Do not capitalize generic titles, ranks, forms of address, generic headings,
nationalities, demonyms, generic biological species, common creature classes,
common objects, or ordinary words. Position, frequency, NER-like appearance,
and the fact that a word can be a name are not evidence. Resolve ambiguous
forms such as will, rose, mark, hope, may, march, august, god, lord, bertie, or
keo by meaning in the current occurrence.

Each target contains original lowercase alphabetic tokens and a provisionally
sentence-cased text. Return casing decisions, not rewritten records.

Use global_decisions only when a lowercase form has one unambiguous proper-name
meaning in every occurrence inside the current target block. Never propagate a
global decision outside this block. If a form can also be common or refers to
different entities, return only the confirmed occurrences through
occurrence_decisions.

Перед добавлением любого `global_decision` семантически проверь каждое точное
употребление `source` во всех target-записях текущего блока. `global_decision`
запрещён, если хотя бы одно употребление является обычным словом, выполняет иную
грамматическую функцию, входит в другое имя, относится к другой сущности или
остаётся неоднозначным. Не используй `global_decision` как сокращение или
предположение: при любом различии значений возвращай отдельные
`occurrence_decisions` только для подтверждённых именованных употреблений.

Если обычное слово становится прописным только как часть составного названия,
произведения или организации, по умолчанию адресуй его через
`occurrence_decisions`. Например, верни `Lives` только для соответствующего
токена в `Modern Lives magazine`, но оставь `lives` строчным в `he lives in a
big mansion`. Перед возвратом молча перепроверь, что ни одно решение из
`global_decisions` не затрагивает употребление с другим смыслом.

For occurrence_decisions, index is the local target-record index, token is the
zero-based alphabetic-token index, source must be copied exactly from tokens,
and canonical may change letter case only. For a multiword proper name, return a
decision for every token whose case must change.

В исходнике может отсутствовать пунктуация, например `keos`, когда по контексту
подразумевается `Keo's`. Не исправляй пунктуацию или написание: решение о
регистре может вернуть только `Keos`. Распознавай формы множественного числа и
формы, похожие на притяжательные, по их семантическому референту, а не только по
суффиксу `s`.

Если окна 10+100+10 недостаточно, добавь индекс соответствующей target-записи в
`needs_context_indices` вместо угадывания. Если потенциальная форма обращения
или референции к конкретному человеку остаётся неразрешённой, не оставляй её
молча строчной: запроси расширенный контекст для каждого затронутого индекса.
Это особенно важно на границах target-блоков, для повторяющихся незнакомых форм
и когда последующий контекст может явно установить референта. В режиме
`expanded_context` прими лучшее окончательное семантическое решение и верни
пустой `needs_context_indices`.

Перед возвратом молча проверь каждую target-запись токен за токеном на
пропущенные собственные имена. Особое внимание уделяй `named_object`, `deity`,
неформальным именам, уникальным названиям вымышленных народов, рас и видов,
формам множественного числа и притяжательным формам с исправлением только
регистра, принятым именам и именам прикрытия, незнакомым персональным
псевдонимам, вымышленным именам и именам, похожим на обычные слова. Возвращай
только JSON.
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
- Перед глобальным решением модель обязана семантически проверить каждое употребление `source` во всех target-записях блока.
- Если хотя бы одно употребление является обычным словом, имеет другую грамматическую функцию, относится к другой сущности или неоднозначно, `global_decision` запрещён.
- Обычные слова, капитализируемые только внутри составного названия (`Modern Lives`), возвращаются через `occurrence_decisions`, если та же форма встречается с другим смыслом (`he lives`).
- `global_decision` является только безопасной оптимизацией и не используется при сомнении.
- Решение не переносится в соседние блоки или по всему файлу.

### `occurrence_decisions`

- Используется для неоднозначной формы или отдельного контекстно подтверждённого употребления.
- `index` и `token` должны точно адресовать употребление.
- Решение применяется только к указанному токену.

### `needs_context_indices`

- Если локального окна недостаточно, модель не угадывает.
- Если незнакомая форма может семантически обозначать конкретного адресата или человека, но базовое окно не даёт окончательного подтверждения, модель обязана запросить расширенный контекст, а не молча оставить строчную букву.
- Особое внимание уделяется границам target-блоков, повторяющимся обращениям, псевдонимам, принятым именам и формам с пропущенным апострофом.
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
