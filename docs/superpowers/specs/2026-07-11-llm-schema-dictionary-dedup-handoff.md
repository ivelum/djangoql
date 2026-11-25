# Handoff: deduplikacja wartości słowników w schemacie LLM

Data: 2026-07-11
Repo: `djangoql-iplweb` (`/Users/mpasternak/Programowanie/djangoql-iplweb`)
Moduł: `djangoql/llm.py`
Wersja startowa: `0.30.3` (docelowo → `0.31.0`, bo zmienia się kształt IR/JSON)
Zgłaszający downstream: BPP (`bpp-schema-for-llm`), artefakt
`src/bpp/data/rekord_djangoql_schema.compact.txt`

> Ten dokument to **handoff dla nowej sesji**. Jest samowystarczalny: opisuje
> problem, dowody z realnego artefaktu, dokładne miejsca w kodzie, rekomendowany
> projekt, plan TDD, kompatybilność wsteczną, kroki wydania oraz robotę
> downstream w BPP. Zacznij od sekcji „Zanim zaczniesz kodować" i trzymaj się
> TDD (`superpowers:test-driven-development`).

---

## Problem (co użytkownik zgłosił)

> „Grzecznie i kulturalnie prosiłem, żeby OGRANICZYĆ ilość emitowanych danych.
> Skróty dla pola »język« widzę WIELOKROTNIE w pliku, tak samo wielokrotnie dla
> pola charakter formalny... to chyba w djangoql-iplweb trzeba poprawić."

`describe_schema_for_llm(..., format='compact')` **wkleja pełną listę wartości
słownika przy KAŻDEJ relacji FK do tego słownika**. Ten sam słownik jest
powtarzany tyle razy, ile jest do niego kluczy obcych w całym grafie schematu.

### Dowód (realny artefakt BPP, 2026-07-11)

Plik: `bpp-schema-for-llm/src/bpp/data/rekord_djangoql_schema.compact.txt`

- Lista wartości `bpp.jezyk` (`match nazwa in ("abchaski", "Achinese", …,
  "angielski", "Angika")`, ucięta do `MAX_SUGGESTED_VALUES=20`) występuje
  **~14 razy** — bo `jezyk`, `jezyk_alt`, `jezyk_orig`, `jezyk_streszczenia`
  pojawiają się na wielu typach rekordów (`wydawnictwo_ciagle`,
  `wydawnictwo_zwarte`, `patent`, `praca_doktorska`, …).
- W całym pliku jest **75 linii** typu `match … in (…)` — spora część to
  powtórzenia tego samego słownika (`bpp.jezyk`, `bpp.charakter_formalny`,
  `bpp.typ_kbn`, `bpp.status_korekty`, `bpp.jezyk` streszczenia itd.).
- Każde powtórzenie to ~250–400 bajtów zmarnowanego promptu; przy dużym
  schemacie to kilobajty czystej redundancji.

Kluczowe: **słownik-cel i tak ma własną sekcję** w wyjściu (np. `bpp.jezyk:`
w linii 123 artefaktu, ze swoimi polami). Wartości są więc emitowane raz „u
siebie" jako model **i** dodatkowo inline przy każdym FK — czysta duplikacja.

---

## Root cause (dokładnie gdzie w kodzie)

Wszystko w `djangoql/llm.py`:

1. `_field_ir(name, field, schema, max_fk_options)` (l. 502) woła
   `_relation_values(...)` dla **każdego** pola relacyjnego z osobna (l. 515).
2. `_relation_values(schema, field, name, max_fk_options)` (l. 451) dla każdego
   FK niezależnie odpytuje `_distinct_values` / `_str_examples` i zwraca
   `{'match_field': …, 'related_values': [ …pełna lista… ]}`.
3. Renderery wklejają tę listę inline:
   - compact: `_compact_field` (l. 626) → `match {field} in ({vals})` (l. 637–647),
   - json: `_json_field` (l. 578) → klucz `related_values` per pole.

Nigdzie nie ma pamięci „ten (model-cel, match_field) już był wyemitowany".
Emisja jest **per-FK**, nie **per-słownik**.

---

## Cel

Emitować listę wartości danego słownika **raz** i przy kolejnych FK do tego
samego celu **referować**, nie powtarzać. Bez utraty semantyki: LLM nadal wie,
jakich wartości użyć dla `jezyk` — tylko czyta je z jednego miejsca.

Zakres: dotyczy **obu** formatów (`compact` i `json`) — wspólne IR, więc naprawa
w warstwie IR + drobne zmiany w obu rendererach.

---

## Rekomendowany projekt (Opcja A — „dictionaries" jako single source of truth)

### Idea

Dodać do IR nowy, górnopoziomowy blok `dictionaries` (roboczo; można też
`related_values_by_model`): mapę
`{ model_label: { match_field: [ …wartości… ] } }` — **jeden wpis na (model-cel,
match_field)**. Pole relacyjne w IR przestaje nosić `related_values`; zamiast
tego dostaje lekki znacznik, że wartości są „w słowniku".

Renderery:
- **compact**: FK renderuje się jako `-> bpp.jezyk` (bez inline `match … in`);
  na górze (albo tuż przy sekcji modelu `bpp.jezyk:`) wypisujemy słownik raz,
  np. jako komentarz `# values (nazwa): "abchaski", …, "Angika"`.
- **json**: dodać górnopoziomowy klucz `dictionaries`; pole niesie
  `match_field` + flagę `values_in: "<model_label>"` (albo po prostu sam
  `match_field`, a konsument szuka wartości w `dictionaries[relates_to]`).

### Klucz deduplikacji

Dedup po **(model_label, frozenset(match_fields))**. Uwaga na przypadki brzegowe:
- różne FK do tego samego modelu mogą używać **różnych** match_fieldów
  (np. jeden `True`→`nazwa`, inny `'skrot'`) — wtedy to **osobne** wpisy słownika
  (klucz zawiera match_field), oba emitowane raz.
- `__str__` / `related_examples` (nie ma stałego match_fielda) — traktuj
  `related_examples` analogicznie: dedup po `(model_label, '__str__')`.

### Fallback, gdy cel NIE ma własnej sekcji

Model-cel bywa poza `ir['models']` (relacja wychodzi do modelu spoza schematu,
ale wartości i tak emitowane przez `fk_options`/auto). Blok `dictionaries` jest
**górnopoziomowy i niezależny** od `models`, więc to działa bez wyjątków:
wartości lądują w `dictionaries`, FK referuje po `relates_to`. Nie trzeba
warunkować emisji obecnością sekcji modelu.

### Dlaczego Opcja A, a nie inne

- **Opcja B (back-reference inline):** zostaw inline przy pierwszym wystąpieniu,
  a kolejne → `-> bpp.jezyk (values as above)`. Mniejsza zmiana, ale wyjście
  zależne od kolejności iteracji (kruche testy), „as above" jest mniej
  maszynowo-czytelne niż nazwany blok. Odrzucone.
- **Opcja C (memoizacja tylko zapytań DB):** cache’uje `_distinct_values`, więc
  oszczędza zapytania, ale **nie zmniejsza pliku** — a użytkownik skarży się na
  ROZMIAR/powtórzenia w pliku, nie na czas generacji. Niewystarczające samo w
  sobie (choć warto dołożyć przy okazji: patrz „Przy okazji").

---

## Architektura zmian (konkretnie)

1. **Zbierz słowniki raz.** Nowa funkcja, np.
   `_collect_dictionaries(schema, max_fk_options)`:
   - iteruj `schema.models` → pola relacyjne,
   - dla każdego policz spec (`_fk_spec`) i match_field (`_default_match_field`
     lub jawny spec), pobierz wartości (`_distinct_values` /
     `_match_fields_entry` / `_examples_entry`) **z memoizacją po kluczu
     (model_label, match_key)**,
   - zbuduj mapę `dictionaries`.
   To centralizuje dzisiejsze wywołania z `_relation_values`.
2. **Odchudź `_relation_values` / `_field_ir`.** Pole relacyjne nie kopiuje już
   `related_values`; niesie `match_field`/`match_fields` (dla renderu etykiety)
   + wskaźnik na słownik. Wariant minimalny: zostaw `match_field`, usuń
   `related_values`, a renderer bierze wartości z `dictionaries[relates_to]`.
3. **`_build_schema_ir`** (l. 561) dokłada `ir['dictionaries']`.
4. **`_render_compact`** (l. 692): wypisz blok słowników raz (u góry lub przy
   sekcji modelu); `_compact_field` przestaje wklejać `match … in (…)`.
5. **`_render_json`** (l. 772): dodaj `dictionaries` do zwracanego dicta;
   `_json_field` bez `related_values`.
6. **`no_value_targets` / `_is_sensitive_target`** — bez zmian semantyki: model
   z denylisty po prostu nie trafia do `dictionaries` (ten sam warunek co dziś
   na wejściu do `_relation_values`, tylko przeniesiony do `_collect_dictionaries`).

> Uwaga na `MAX_SUGGESTED_VALUES=20` / `MAX_CHOICE_VALUES=100` (l. 87–92) — to
> istniejące capy; zostają. `choices` (zamknięte zbiory z definicji pola, l. 247)
> to osobny mechanizm i **nie** jest przedmiotem tej deduplikacji (nie odpytuje
> DB, nie duplikuje się per-FK — pojawia się raz na polu z choices).

---

## Zanim zaczniesz kodować

1. **Wejdź w worktree** (zgodnie z globalnym CLAUDE.md — katalog-rodzeństwo,
   nigdy w `/tmp` ani w drzewie repo):
   ```bash
   git worktree add ~/Programowanie/djangoql-iplweb-llm-dict-dedup \
     -b feat/llm-schema-dictionary-dedup
   ```
2. **Odtwórz dowód**: `test_project` ma model `library.book` z self-M2M
   `similar_books` i relacjami — patrz `test_project/core/tests/test_llm.py`
   (klasa `NoValueTargetsTest` i sąsiednie). Testy djangoql-iplweb są
   **unittest-style** (`django.test.TestCase`), NIE pytest — trzymaj konwencję
   repo (inaczej niż w BPP).
3. Przeczytaj `docs/superpowers/specs/2026-07-05-llm-schema-compression-design.md`
   (kształt IR + oba renderery) i `docs/llm-schema.md` (kontrakt publiczny).

---

## Plan TDD (kolejność RED→GREEN)

Pisz test PRZED implementacją, oglądaj czerwień. W `test_project/core/tests/test_llm.py`:

1. **compact: słownik raz.** Zbuduj schemat, w którym ≥2 pola relacyjne celują
   w ten sam model z wartościami (np. dwa FK do `library.author`, albo self-M2M
   + zwykły FK do tego samego modelu). Asercja: pełna lista wartości pojawia się
   w tekście **dokładnie raz** (policz wystąpienia charakterystycznej wartości).
2. **compact: FK referuje, nie wkleja.** Linia FK to `-> app.model` (opcjonalnie
   ze wskazaniem match_fielda), BEZ `match … in (…)` przy drugim i kolejnym FK.
3. **json: blok `dictionaries`.** `result['dictionaries']['app.model']['<match>']`
   == oczekiwana lista; żadne pole w `models` nie ma już `related_values`.
4. **Różne match_fieldy → osobne wpisy.** FK z `fk_options=True` (default
   `nazwa`) i drugi z `fk_options='skrot'` do tego samego modelu → dwa wpisy
   w `dictionaries`, każdy raz.
5. **Regresje (muszą przejść bez zmian semantyki):**
   - `no_value_targets` nadal twardo blokuje (model z denylisty NIE ma wpisu w
     `dictionaries` ani inline) — istniejąca `NoValueTargetsTest` dostosowana do
     nowego kształtu.
   - `_is_sensitive_target` (auth/admin/User) nadal pomijane.
   - `max_fk_options=0` → brak `dictionaries` w trybie auto (jak dziś brak
     wartości).
   - `choices` bez zmian (dalej per-pole).
6. **Oba formaty:** `format='compact'` → `str`, `format='json'` → dict z kluczem
   `dictionaries`; nieznany format → `ValueError`.

Po zieleni: pełna suita repo (`uv run pytest` w djangoql-iplweb) — nie zostaw
złamanych testów enrichment/compression.

---

## Kompatybilność wsteczna (WAŻNE — bump minor)

- **Zmienia się kształt JSON** (znika `related_values` z pól, dochodzi górny
  `dictionaries`). To breaking dla konsumentów parsujących `related_values`
  per-pole → **wersja `0.31.0`**, nie patch. Zaktualizuj `docs/llm-schema.md`
  (opis `dictionaries`, przykłady obu formatów) i `mkdocs build --strict`.
- **Compact** też zmienia wygląd (mniej inline), ale to prompt dla LLM, nie
  kontrakt maszynowy — akceptowalne w minorze.
- BPP downstream: artefakt się **skurczy**, a testy BPP asertują na jego treść
  (`test_djangoql_schema_llm.py`: `test_committed_artifact_has_no_institution_data_leak`
  sprawdza brak wycieków — to nadal przejdzie; ale regeneracja zmieni plik).

---

## Wydanie (po zielonych testach i docs)

Wzoruj się na ostatnim wydaniu 0.30.3 (obserwacje w pamięci projektu:
`uv build` → `uv publish`, token w środowisku). Kroki:

1. `bumpver update` lub ręcznie: `djangoql/__init__.py` (`__version__`),
   `pyproject.toml` (`current_version`) → `0.31.0`.
2. Wpis w `CHANGES.rst` (sekcja 0.31.0: deduplikacja wartości słowników;
   breaking change kształtu JSON — `dictionaries` zamiast per-pole
   `related_values`).
3. `uv build && uv publish` (token w env — nie sprawdzać/nie logować).
   **Uwaga z historii:** 0.30.3 raz „po cichu" nie doszło mimo komunikatów
   sukcesu (obs. 22175) — zweryfikuj, że wersja jest na PyPI (simple index
   synchronizuje się szybciej niż JSON API, obs. 22177) zanim ruszysz downstream.
4. `git commit` + tag `0.31.0`, merge do master (użytkownik przy 0.30.3 wybrał
   „merge do master + push, bez PR" — potwierdź analogicznie).

---

## Downstream w BPP (po wydaniu 0.31.0)

W worktree `bpp-schema-for-llm` (gałąź `feat-schema-for-llm`):

1. `pyproject.toml`: `djangoql-iplweb>=0.31.0`; `uv lock`.
2. Regeneruj artefakt z dumpu (dev stack musi biegać — `run-site --from-dump`):
   ```bash
   export DJANGO_BPP_SKIP_DOTENV=1 \
     DJANGO_BPP_DB_HOST=localhost DJANGO_BPP_DB_PORT=$(cat .dev_helpers_pg_port) \
     DJANGO_BPP_DB_NAME=bpp DJANGO_BPP_DB_USER=bpp DJANGO_BPP_DB_PASSWORD=password \
     DJANGO_BPP_REDIS_HOST=localhost DJANGO_BPP_REDIS_PORT=$(cat .dev_helpers_redis_port)
   uv run python src/manage.py opisz_schemat_djangoql_dla_llm
   ```
3. Sprawdź redukcję: `grep -c 'match .* in (' …compact.txt` powinno drastycznie
   spaść (dziś 75; po fixie ~ tyle, ile unikatowych słowników).
4. Testy BPP: `uv run pytest src/bpp/tests/test_djangoql_schema_llm.py`
   (+ multiseek/zapytanie/djangoql jak w tej sesji). Jeśli któryś asertuje na
   dokładny inline-format wartości — dostosuj do nowego kształtu.
5. Commit artefaktu + bump zależności.

---

## Poza zakresem (YAGNI)

- Konfigurowalny próg „ile FK do tego samego modelu, zanim dedup" — dedup zawsze.
- Zmiana `MAX_SUGGESTED_VALUES` / `MAX_CHOICE_VALUES`.
- Deduplikacja `choices` (osobny, niezduplikowany mechanizm).
- Cache’owanie zapytań DB jako osobna funkcja publiczna (patrz niżej — robimy to
  wewnętrznie „przy okazji", bez API).

## Przy okazji (nice-to-have, jeśli tanie)

- `_collect_dictionaries` naturalnie memoizuje `_distinct_values` po
  `(model_label, match_field)` — to **efekt uboczny** dedupu i redukuje liczbę
  zapytań DB (dziś: jedno `SELECT DISTINCT` per FK; po fixie: per unikatowy
  słownik). Zero dodatkowego API, sam zysk.
