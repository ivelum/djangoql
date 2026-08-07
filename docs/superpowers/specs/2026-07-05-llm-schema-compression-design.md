# Design: kompresja schematu LLM (tryby `json` / `compact`)

Data: 2026-07-05
Moduł: `djangoql/llm.py`, `djangoql/management/commands/djangoql_describe_schema_for_llm.py`
Dokumentacja: `docs/llm-schema.md`
Gałąź: `feat/llm-schema-enrichment` (wcielone do PR #14 — nigdy nie wypuszczamy rozwlekłego formatu)

## Problem

Obecny `describe_schema_for_llm` emituje dla **każdego** pola pełną listę
operatorów i przykład — a jedno i drugie wynika wyłącznie z `type`. Przy 50
polach lista operatorów jest przepisywana ~50 razy. Plain scalar ≈ 130 bajtów,
gdy realna informacja to `rating: float` ≈ 15 bajtów (~8× narzutu, zanim dojdą
metadane). Dla większych projektów schemat staje się „przepotężny".

## Cel

Zdeduplikować to, co wynika z typu, do **legendy raz na górze**, a pola sprowadzić
do **terse** postaci (tylko treść niosąca informację). Udostępnić dwa tryby
wyjścia przez parametr `format`:

- `'json'` (domyślny) — znormalizowany JSON: legenda operatorów + terse pola.
- `'compact'` — zwarty tekst/DSL, linia na pole, jeszcze mniejszy.

Stary rozwlekły per-pole format **znika** (nie ma trybu verbose). Semantyka nie
ubywa — tylko deduplikacja.

## Architektura

Rozdzielić budowę faktów od renderowania (czysta granica, łatwe testy):

1. **IR (intermediate representation)** — `_build_schema_ir(schema, max_fk_options)`
   zwraca neutralną strukturę: `start_model`, per model lista pól z faktami
   (`name`, `type`, `nullable`, opcjonalnie `label`, `help_text`, `choices`,
   `suggested_values`, `relates_to`, `match_field`/`match_fields`,
   `related_values`, `related_examples`, `object_reference`). To jest dzisiejsza
   logika Aspektów 1–3 z PR #14, wydzielona z renderowania.
2. **Renderery** — `_render_json(ir)` i `_render_compact(ir)` zamieniają IR na
   wyjście. `describe_schema_for_llm` wybiera renderer po `format`.

Operatory i przykłady per typ są danymi **typu**, nie pola — żyją w rendererze
(legenda), nie w IR pola.

## Sekcja 1 — Struktura `json` (znormalizowana)

```jsonc
{
  "start_model": "core.book",
  "grammar": { ...dotychczasowe reguły... , "operators": "look up a field's
     operators in operators_by_type by its type; a field with relates_to uses
     the 'relation' entry; a field with object_reference:true uses the
     'object_reference' entry" },
  "operators_by_type": {
    "int":      {"operators": ["=","!=",">",">=","<","<=","in","not in"], "example": "x = 42"},
    "float":    {"operators": ["=","!=",">",">=","<","<=","in","not in"], "example": "x = 4.5"},
    "date":     {"operators": ["=","!=",">",">=","<","<=","in","not in"], "example": "x = \"2021-06-01\""},
    "datetime": {"operators": ["=","!=",">",">=","<","<=","~","!~","in","not in"], "example": "x = \"2021-06-01 14:30\""},
    "str":      {"operators": ["=","!=","~","!~","startswith","endswith","not startswith","not endswith","in","not in"], "example": "x ~ \"text\""},
    "bool":     {"operators": ["=","!="], "example": "x = True"},
    "relation":         {"operators": ["= None","!= None","<relation>.<field> (traverse with a dot)"]},
    "object_reference": {"operators": ["=","!=","in","not in"]}
  },
  "models": { "core.book": { ...terse pola... } },
  "examples": [ "id = 1", "id > 10 and id < 100", ... bez zmian ... ]
}
```

Legenda emitowana **raz**. `operators_by_type` zawiera wszystkie standardowe typy
(stała, mała) plus pseudo-typy `relation` i `object_reference`. Reguła lookupu
w `grammar`.

## Sekcja 2 — Terse kodowanie pola (json)

- **Pole bez dodatków → goły string** `"name": "type"`, np. `"id": "int"`.
- **Nullable → sufiks `?`** na tokenie typu, wszędzie: `"published_date": "date?"`
  (bare) albo `{"type": "str?", ...}`. Konsument obcina `?` przed lookupem
  operatorów; `?` sygnalizuje, że porównanie do `None` ma sens. Nullable-only
  pole zostaje gołym stringiem.
- **Pole z metadanymi → obiekt** z kluczem `type` (zawsze — dla parsera i lookupu)
  oraz tylko obecnymi z: `label`, `help_text`, `choices`, `suggested_values`,
  `relates_to`, `match_field`/`match_fields`, `related_values`,
  `related_examples`, `object_reference`.
- **Znika z pól**: `operators`, `example`, `nullable: false`, generyczny
  relacyjny `note`.

```jsonc
"core.book": {
  "id": "int",
  "rating": "float?",
  "name": {"type": "str", "label": "Title", "help_text": "The title of the book"},
  "genre": {"type": "int", "choices": ["Drama","Comics","Other"]},
  "author": {"type": "relation", "relates_to": "auth.user"},
  "similar_books": {"type": "relation", "relates_to": "core.book",
                    "match_field": "name", "related_values": ["Dune","Solaris"]}
}
```

Niejednorodność (pole = string ALBO obiekt) jest zaakceptowanym kompromisem:
zwięzłość kosztem jednorodności; konsument obsługuje oba (string → tylko typ).

## Sekcja 3 — Tryb `compact` (tekst)

Nagłówek: grammar + operatory-per-typ jako komentarze (raz), potem linia na pole.
Konwencje: `->` relacja (z `relates_to`), `#` object_reference, `?` nullable,
`choices:`, `match <field> in (…)` dla wartości relacji, `— <help_text>` po
etykiecie.

```
# DjangoQL schema — start model: core.book
# Query: <field> <op> <value>, combined with and/or, grouped with (). Negate with
#   != / !~ / not in / not startswith / not endswith (no standalone `not`).
# Relations: traverse with a dot (author.name = "..."), or compare to None.
# Operators by type:
#   int/float/date:  = != > >= < <=  in  not in            e.g. rating = 4.5
#   datetime:        (as above) plus ~ !~
#   str:             = != ~ !~ startswith endswith (not …) in  not in   e.g. name ~ "text"
#   bool:            = !=                                    e.g. is_published = True
#   -> relation:     = None / != None / dot-traverse
#   # object_reference: = != in not in  (match by pk)
# Suffix ? = nullable.  choices: closed set.

core.book:
  id              int
  name            str     "Title" — The title of the book
  genre           int     choices: Drama | Comics | Other
  rating          float?
  published_date  date?
  is_published    bool
  author          -> auth.user
  similar_books   -> core.book   match name in ("Dune", "Solaris")
  content_type    # str   (object_reference)

auth.user:
  id        int
  username  str
  ...
```

Wartości/etykiety cytowane tak, by były jednoznaczne. Wyrównanie kolumn dla
czytelności (best-effort, nie krytyczne).

## Sekcja 4 — API / CLI

- `describe_schema_for_llm(schema, format='json', max_fk_options=50)` — `format`
  ∈ `{'json','compact'}`, domyślnie `'json'`. Nieznana wartość → `ValueError`.
  Uwaga: `format` przesłania wbudowaną funkcję `format` w ciele — użyć innej
  nazwy zmiennej lokalnej wewnątrz, ale nazwa parametru pozostaje `format`
  (czytelna dla wołającego).
- Komenda: `--format {json,compact}` (domyślnie `json`). Dla `compact` wyjście to
  gotowy tekst (bez `json.dumps`); `--indent` dotyczy tylko `json` (dla `compact`
  ignorowany).
- **Bez trybu verbose** — brak parametru zachowującego stary format.

## Sekcja 5 — Testy

Przepisać `test_project/core/tests/test_llm.py` pod nowy kształt:

- **json — legenda i lookup:** `operators_by_type` obecne raz na górze, zawiera
  `int`/`str`/`bool`/`relation`/`object_reference`; `grammar` zawiera regułę
  lookupu; żadne pole nie ma klucza `operators` ani `example`.
- **json — terse pola:** pole bez dodatków to string (`models['core.book']['id']
  == 'int'`); nullable to sufiks `?` (`published_date` → `'date?'`); pole z
  choices/metadanymi to obiekt z `type` i bez `operators`.
- **json — zachowanie faktów (regresja z PR #14):** `label`/`help_text`
  (`name`), `choices` (`genre`), `related_values`/`match_field` (auto na
  `similar_books`), wykluczenie wrażliwych (`author`), `fk_options` specs — te
  same fakty co dziś, tylko w nowym kształcie.
- **compact:** nagłówek zawiera operatory-per-typ raz; linia na pole; relacje
  `->`, object_reference `#`, nullable `?`, choices, match-values; brak
  powtórzonych operatorów.
- **oba tryby:** `format='compact'` zwraca `str`, `format='json'` zwraca dict;
  nieznany format → `ValueError`.
- **komenda:** `--format compact` drukuje tekst; `--format json` (i domyślnie)
  drukuje JSON; nieznana wartość → `CommandError`/argparse choices.

## Sekcja 6 — Aktualizacja dokumentacji

Przepisać `docs/llm-schema.md` pod nowy format (deliverable twardy):

- Opisać **oba tryby** (`format='json'` domyślny, `format='compact'`) i flagę CLI
  `--format`.
- Wyjaśnić **legendę `operators_by_type`** i regułę lookupu operatorów po typie
  (+ pseudo-typy `relation`/`object_reference`).
- Wyjaśnić **terse kodowanie**: goły string vs obiekt, sufiks `?` = nullable,
  pominięte klucze domyślne.
- Zaktualizować **przykładowe wyjście** JSON do nowej, znormalizowanej postaci;
  dodać przykład wyjścia `compact`.
- Zachować sekcje o `label`/`help_text`, choices, wartościach FK i `fk_options`
  (z PR #14) — dostosować pola-przykłady do nowego kształtu.
- Zweryfikować `mkdocs build --strict` (bez orphanów/broken links).

## Poza zakresem (YAGNI)

- Tryb verbose / zachowanie starego formatu.
- Emisja tylko obecnych typów w legendzie (emitujemy pełny, mały, stały zestaw).
- Konfigurowalne wyrównanie/kolumny w `compact`.
- YAML/inne media (tylko json + compact-text).

## Decyzje (potwierdzone z użytkownikiem)

1. Dwa tryby przez `format`, domyślnie `json` znormalizowany; stary verbose znika.
2. Nullable jako sufiks `?` na tokenie typu (wszędzie).
3. Pole bez dodatków = goły string; z dodatkami = obiekt (niejednorodność OK).
4. `operators_by_type` z pseudo-typami `relation`/`object_reference` + reguła
   lookupu w `grammar`.
5. Wcielone do PR #14 (ta sama gałąź), z przepisaniem testów i docs.
