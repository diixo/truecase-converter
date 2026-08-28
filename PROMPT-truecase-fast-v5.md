# Contextual Truecasing — Fast Parallel v5

Версия отражает фактический режим, использованный после перехода с медленного последовательного truecasing на быстрый алгоритм.

## Назначение

Преобразовать поле `text` в JSONL-файле в truecase, сохранив структуру файла и разрешив изменение только регистра существующих букв.

Исходный файл обычно содержит 10 000 записей. Соседние записи часто являются продолжением одного повествования.

Результирующий файл именуется:

```text
<исходное_имя>_truecased.jsonl
```

Пример:

```text
bookcorpus_part_01144_truecased.jsonl
```

## Фактическая архитектура

```text
JSONL
  → программный grammatical baseline
  → 100 независимых блоков по 100 target-записей
  → для каждого блока окно 10 + 100 + 10
  → параллельные stateless-запросы к языковой модели
  → модель возвращает только решения по сущностям
  → Python применяет решения
  → case-only и structural validation
  → JSONL
```

Настройки текущего режима:

- `BLOCK_SIZE = 100`;
- `CONTEXT_BEFORE = 10`;
- `CONTEXT_AFTER = 10`;
- `EXPANDED_CONTEXT = 40` с каждой стороны;
- до 12 блоков обрабатываются параллельно;
- каждый блок является отдельным stateless-запросом;
- модель: `gpt-5.6-sol`;
- reasoning effort: `low`;
- service tier: `priority`;
- инструменты модели отключены;
- интернет, поиск и внешние источники запрещены.

## Этап 1. Программный grammatical baseline

До обращения к модели Python изменяет только регистр и выполняет:

1. Капитализацию первого алфавитного символа записи.
2. Капитализацию первого алфавитного символа после `.`, `?`, `!`.
3. Капитализацию начала реплики после распознанной открывающей кавычки.
4. Замену отдельного местоимения `i` на `I`.
5. Капитализацию однозначных названий месяцев:

```text
january, february, april, june, july,
september, october, november, december
```

Формы `may`, `march`, `august` не исправляются автоматически и передаются модели как контекстно неоднозначные.

Python не принимает решений о том, является ли слово именем, фамилией, местом или организацией.

## Этап 2. Формирование модельного окна

Для каждого блока модель получает:

```json
{
  "mode": "base_context",
  "context_before": [
    {"id": 1000, "text": "..."}
  ],
  "targets": [
    {
      "index": 0,
      "id": 1010,
      "text": "Reed weils finger slipped off the comm button .",
      "tokens": ["reed", "weils", "finger", "slipped", "off", "the", "comm", "button"]
    }
  ],
  "context_after": [
    {"id": 1110, "text": "..."}
  ]
}
```

Где:

- `context_before` — до 10 предыдущих записей;
- `targets` — ровно 100 изменяемых записей, кроме последнего неполного блока;
- `context_after` — до 10 следующих записей;
- `index` — локальный индекс target-записи внутри блока;
- `text` — текст после grammatical baseline;
- `tokens` — все алфавитные токены исходной записи в исходном нижнем регистре.

Боковой контекст используется только для понимания. Изменять разрешено только `targets`.

## Этап 3. Фактический системный промпт модели

```text
You are the semantic entity-case stage of a fast English truecasing pipeline.
Use only the supplied local narrative. Do not browse, search, call tools, use
external facts, summarize the text, or describe characters or plot.

The technical pipeline has already handled grammatical sentence beginnings,
the standalone pronoun I, and unambiguous month names. Do not review or return
those changes. Decide casing only for contextually supported:
- person names, surnames, full names, initials, and established personal aliases;
- geographic place names, including fictional places;
- organization names, including fictional organizations;
- ambiguous calendar uses of may, march, and august;
- contextually confirmed acronyms belonging to those categories.

Do not capitalize titles, ranks, forms of address, works, chapters, headings,
nationalities, demonyms, species, common objects, or ordinary words. Position,
frequency, NER-like appearance, and the fact that a word can be a name are not
evidence. Determine each ambiguous form such as will, rose, mark, hope, may,
march, or august from its occurrence context.

Each target contains original lowercase alphabetic tokens and a provisionally
sentence-cased text. Return casing decisions, not rewritten records.

Use global_decisions only when a lowercase token is an unambiguous entity in
every occurrence within this target block. A global decision is applied only
inside this one block. If the same form can also be a common word, do not return
it globally; return only the contextually confirmed occurrences in
occurrence_decisions. For a multiword entity, return a decision for every token
that needs capitalization.

For occurrence_decisions, index is the local target-record index, token is the
zero-based alphabetic-token index, and source must be copied exactly from that
target's lowercase tokens. canonical may change only letter case: same length,
same spelling, punctuation, and symbols. Return no explanations.

If the 10+100+10 window is insufficient for an occurrence, put its local target
index in needs_context_indices instead of guessing. In expanded_context mode,
make the best final semantic decision and return an empty needs_context_indices.
```

## Разрешённые классы сущностей

Модель принимает решения только для:

- `person` — имя, фамилия, полное имя, инициалы, подтверждённый персональный псевдоним;
- `place` — конкретное географическое или вымышленное место;
- `organization` — именованная компания, учреждение или формальная группа;
- `month` — контекстно подтверждённый календарный месяц для `may`, `march`, `august`.

Не обрабатываются как сущности:

- должности, звания, титулы и обращения;
- названия книг, фильмов, глав и других произведений;
- заголовки и title case;
- национальности, демонимы, народы и виды;
- общие существительные и предметы;
- аббревиатуры без контекстного подтверждения разрешённого класса.

## Решения модели

### `global_decisions`

Используется только тогда, когда форма однозначно является сущностью во всех её употреблениях внутри текущего блока из 100 target-записей.

Решение никогда автоматически не переносится в соседние блоки или по всему файлу.

### `occurrence_decisions`

Используется для отдельного употребления неоднозначной формы. Решение адресуется локальным индексом записи и индексом токена.

### `needs_context_indices`

Если контекста `10+100+10` недостаточно, модель не угадывает, а возвращает локальные индексы соответствующих target-записей.

## Формат ответа модели

Модель возвращает только валидный JSON:

```json
{
  "global_decisions": [
    {
      "source": "reed",
      "canonical": "Reed",
      "type": "person"
    },
    {
      "source": "adriat",
      "canonical": "Adriat",
      "type": "place"
    }
  ],
  "occurrence_decisions": [
    {
      "index": 17,
      "token": 4,
      "source": "may",
      "canonical": "May",
      "type": "month"
    }
  ],
  "needs_context_indices": []
}
```

Ограничения ответа:

- `source` должен быть точно скопирован из `targets[].tokens`;
- `canonical` должен отличаться от `source` только регистром;
- длина и последовательность букв не меняются;
- модель не возвращает переписанные полные записи;
- модель не возвращает объяснения, комментарии или пересказ.

## Этап 4. Расширение контекста

Если `needs_context_indices` не пуст:

1. Повторно обрабатывается только соответствующий блок.
2. Размер бокового контекста расширяется с 10 до 40 записей с каждой стороны.
3. Запрос получает `mode = "expanded_context"`.
4. Модель должна принять лучшее окончательное контекстное решение.
5. В расширенном проходе `needs_context_indices` должен быть пустым.

## Этап 5. Применение решений

Python выполняет только техническое применение:

1. Проверяет существование `source` в токенах target-блока.
2. Проверяет соответствие `index` и `token` указанному употреблению.
3. Проверяет, что `canonical` отличается только регистром.
4. Применяет `global_decisions` только внутри текущего блока.
5. Применяет `occurrence_decisions` только к указанному употреблению.
6. Не переносит решения автоматически в другие блоки.
7. Не меняет текст бокового контекста.

Если модель вернула некорректный индекс, отсутствующий `source`, конфликтующие решения или изменение написания, блок запрашивается повторно с указанием нарушения инварианта.

## Этап 6. Финальные инварианты

После сборки результата обязательно проверяется:

- количество записей совпадает с исходным файлом;
- порядок записей не изменён;
- все `id` сохранены;
- все поля, кроме `text`, сохранены без изменений;
- длина каждого `text` сохранена;
- каждый символ либо полностью совпадает, либо отличается только регистром той же буквы;
- пробелы, пунктуация, кавычки, апострофы и написание не изменены;
- строки не добавлены и не удалены.

## Что фактически не используется

В текущем варианте не используются:

- Hugging Face и его кэш;
- локальные языковые модели;
- интернет-поиск и внешние источники;
- NER-модель;
- частотный анализ;
- предварительный список кандидатов;
- `entity_cache` между блоками;
- `negative_cache`;
- автоматическое распространение сущности по всему файлу;
- пересказ, суммаризация или описание содержания.

Все алфавитные токены target-блока доступны модели одинаково. Семантическое решение о сущности принимает языковая модель по локальному окну. Программный код отвечает только за grammatical baseline, разбиение, параллельное выполнение, применение решений и проверку инвариантов.
