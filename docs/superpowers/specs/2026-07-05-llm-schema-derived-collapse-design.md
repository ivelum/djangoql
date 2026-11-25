# Design: collapse derived fields into type-level "lookups" in the LLM schema

Data: 2026-07-05
Moduł: `djangoql/llm.py`
Dokumentacja: `docs/llm-schema.md`
Gałąź: `feat/llm-schema-derived-collapse` (od `master`; PR #14 już zmergowany)

## Problem

Fork-owe mixiny rozwijają pola: `DatePartsSchemaMixin` dokłada dla każdego pola
`date`/`datetime` komplet `<field>__year … __iso_week_day` (+ `__hour/__minute/
__second`, `__date`, `__time` dla datetime) — ~13 pól **na każde pole daty**;
`AggregateSchemaMixin` dokłada `<rel>__count` na każdą relację do-wielu. W realnej
aplikacji (BPP) to ~55-60 dodatkowych pól na jednym modelu — największy pojedynczy
żłób w opisie dla LLM. Kompresja (operatory w legendzie) skróciła *wiersz* pola,
ale nie zmniejszyła ich *liczby*: każde `utworzono__year` to wciąż osobny wpis.

## Cel

Opisać *możliwość* pól pochodnych **raz** w legendzie typu, zamiast wyliczać ją
przy każdym polu. Pole bazowe (`utworzono: datetime`) i relacja (`autorzy`)
pojawiają się raz; LLM z legendy wie, że może dokleić `__year`, `__count`,
agregaty. Zero utraty możliwości, ~13× mniej wpisów dla dat.

## Fakty o kodzie (zweryfikowane)

- Pola pochodne mają własne klasy (`djangoql/extras.py`): `DatePartField(IntField)`
  (ma atrybut `.part`), `DateExtractField(DateField)` (`__date`),
  `TimeExtractField` (`__time`), `AggregateField(IntField)` z podklasą
  `CountField` (`__count`).
- **Wszystkie te klasy mają domyślnie `suggested = False`** (ukryte z
  autocomplete; extras.py). Ponieważ `_build_schema_ir` emituje tylko pola z
  `field.suggested`, w stockowym schemacie te pola **już są nieobecne** w opisie
  dla LLM — ale nadal **istnieją w `schema.models`** (pełny słownik pól,
  niefiltrowany po `suggested`; potwierdzone schema.py:601-605). Wniosek:
  - **Wykrywanie** zdolności musi skanować `schema.models` (WSZYSTKIE pola,
    także `suggested=False`), nie przefiltrowany zbiór emisji.
  - Dla stockowego schematu wartością funkcji jest **udostępnienie w legendzie
    możliwości, której dziś LLM w ogóle nie widzi** (`__year`/`__count` są
    ukryte, więc model nie wie, że może ich użyć).
  - Dla schematu, który *pokazuje* te pola (ustawia `suggested=True`, jak w
    aplikacji BPP), dochodzi **odchudzenie** — dlatego emisja musi **jawnie
    wykluczać** instancje tych klas (a nie polegać wyłącznie na `suggested`).
- **Tylko `<rel>__count` jest realnym polem** w schemacie
  (`AggregateSchemaMixin.get_fields`, extras.py:288-300). Numeryczne agregaty
  (`__sum/avg/min/max`) NIE są polami — są syntetyzowane na żądanie przez
  `resolve_unknown` i **nie występują dziś w opisie dla LLM**.
- Składnia agregatów (potwierdzona `_aggregate_hint_examples`, extras.py:410):
  - liczność: `<rel>__count` (np. `autorzy__count >= 2`),
  - numeryczne przez kropkę: `<rel>.<numeric_field>__{sum,avg,min,max}`
    (np. `autorzy.rating__avg`).
- Zestaw części dat: `DatePartsSchemaMixin.DATE_PARTS` + `.TIME_PARTS`
  (extras.py:436-446); time-parts to `hour/minute/second`.

## Architektura (na bazie IR z kompresji)

1. **`_build_schema_ir`** — dwie zmiany:
   - **Emisja**: warunek zmienia się z `if field.suggested` na
     `if field.suggested and not isinstance(field, _DERIVED_FIELD_CLASSES)`, gdzie
     `_DERIVED_FIELD_CLASSES = (DatePartField, DateExtractField,
     TimeExtractField, AggregateField)`. Jawnie wyklucza pola pochodne także,
     gdy schemat ustawił im `suggested=True`.
   - **Wykrywanie**: osobny przebieg po **WSZYSTKICH** polach `schema.models`
     (nie po zbiorze emisji) zbiera **fakty o zdolnościach** do nowej gałęzi IR
     `capabilities`:
   - `date_parts`: zbiór nazw części z obecnych `DatePartField.part`, które NIE
     są time-parts;
   - `time_parts`: zbiór obecnych części z `hour/minute/second`;
   - `has_date_extract` / `has_time_extract`: czy występuje `DateExtractField` /
     `TimeExtractField`;
   - `relation_count`: czy występuje `AggregateField`/`CountField`.
   Klasyfikacja time-part vs date-part: stała `_TIME_PART_NAMES =
   frozenset({'hour','minute','second'})` (semantycznie stała, niezależna od
   mixina). Listy pochodzą **z faktycznie obecnych** pól, nie z importu stałych —
   wierne także dla custom-subclass.
2. **`_render_json`** — dokłada do legendy **tylko gdy wykryto** daną zdolność:
   - `operators_by_type['date']['lookups']` — gdy `date_parts` niepuste;
   - `operators_by_type['datetime']['lookups']` — gdy są date/time parts lub
     extracts (opis = date-parts + time-parts + `__date`/`__time`);
   - `operators_by_type['relation']['aggregates']` — gdy `relation_count` — opis
     obejmuje `<rel>__count` ORAZ wzorzec numeryczny przez kropkę.
3. **`_render_compact`** — analogiczne linie w nagłówku (raz), gated tak samo.

### Kształt wyjścia (json)

```jsonc
"operators_by_type": {
  "date": {
    "operators": ["=","!=",">",">=","<","<=","in","not in"],
    "example": "x = \"2021-06-01\"",
    "lookups": "also <field>__<part> (integer): year, month, day, week_day, quarter, week, iso_year, iso_week_day. e.g. utworzono__year = 2021"
  },
  "datetime": {
    "operators": ["=","!=",">",">=","<","<=","~","!~","in","not in"],
    "example": "x = \"2021-06-01 14:30\"",
    "lookups": "as date, plus hour, minute, second; and <field>__date (date), <field>__time (time)"
  },
  "relation": {
    "operators": ["= None","!= None","<relation>.<field> (traverse with a dot)"],
    "aggregates": "to-many relation: <rel>__count (integer), e.g. autorzy__count >= 2. Numeric aggregates via dot: <rel>.<numeric_field>__sum|avg|min|max, e.g. autorzy.rating__avg"
  }
}
```
`models` zawiera `"utworzono": "datetime?"` raz; **brak** `utworzono__year`
… `utworzono__time`; `"autorzy": {"type":"relation", ...}` raz, **brak**
`autorzy__count`.

Listy części w `lookups` budowane z faktycznie obecnych `date_parts`/`time_parts`
(kolejność stabilna wg kanonicznej listy części, przecięta z obecnymi).

## Zakres (decyzje potwierdzone z użytkownikiem)

1. **Klucze legendy per typ**: `lookups` (dla `date`/`datetime`), `aggregates`
   (dla `relation`).
2. **Fakty czerpane z obecnych instancji**, nie z importu stałych mixina.
3. **Tylko zwinięte** — brak furtki `expand_derived`; jeden format.
4. **Agregaty numeryczne opisane** w legendzie (wzorzec `<rel>.<numfield>__agg`)
   — LLM zyskuje możliwość, której dziś w opisie nie ma.
5. **Gating**: sekcje `lookups`/`aggregates` pojawiają się wyłącznie, gdy
   schemat realnie ma te pola.

## Testy

Plik `test_project/core/tests/test_llm.py`. Wykorzystać schematy z
`DatePartsSchemaMixin` / `AggregateSchemaMixin` (wzorce w `test_extras.py`;
w razie potrzeby zdefiniować lokalny schemat testowy na `Book`, który ma pola
daty — `written`/`published_date` — i relację do-wielu — `similar_books`):

- Schemat z mixinami (pola pochodne `suggested=False`): legenda `date`/
  `datetime` ma klucz `lookups` z obecnymi częściami; `relation` ma
  `aggregates` z `__count` i wzorcem numerycznym — czyli **możliwość zostaje
  udostępniona**, mimo że same pola były i pozostają ukryte.
- Pole bazowe `written` (datetime) i relacja `similar_books` **są** obecne raz;
  pochodne (`written__year`, `similar_books__count`) **NIE** są w `models`.
- **Jawne wykluczenie**: schemat, który ustawia pochodnej `suggested=True`
  (np. `DatePartField('written','year')` z `suggested=True` doklejone w
  `get_fields`), i tak **nie** ma jej w `models` (wykluczenie przez isinstance,
  nie przez `suggested`).
- Schemat BEZ tych mixinów (`DjangoQLSchema(Book)`) **nie** dostaje sekcji
  `lookups`/`aggregates` (gating — puste `capabilities`).
- Compact: możliwości opisane w nagłówku raz; brak linii `written__year` /
  `similar_books__count`.
- `capabilities`/klasyfikacja: time-parts (`hour/minute/second`) trafiają do
  opisu `datetime`, nie `date`.

## Dokumentacja

`docs/llm-schema.md`: nowa sekcja „Derived fields (date parts, aggregates)" —
dlaczego pola pochodne nie są wyliczane, jak LLM konstruuje `<field>__year` /
`<rel>__count` / `<rel>.<num>__avg` z legendy; zaktualizowane przykłady json i
compact. Zweryfikować `mkdocs build --strict`.

## Poza zakresem (YAGNI)

- Furtka pełnego rozwinięcia (`expand_derived`).
- Emisja numerycznych agregatów jako realnych pól (pozostają on-demand).
- Per-pole flaga „obsługuje lookups" (legenda per typ wystarcza; gating na
  poziomie schematu).
