# Design: wzbogacony schemat dla LLM (metadane, choices, wartości FK)

Data: 2026-07-04
Moduł: `djangoql/llm.py`, `djangoql/management/commands/djangoql_describe_schema_for_llm.py`
Dokumentacja: `docs/llm-schema.md`

> Zrewidowano po niezależnym review (Fable 5) — patrz sekcja „Rozstrzygnięcia
> z review" na końcu.

## Cel

`describe_schema_for_llm` obecnie opisuje strukturę i składnię (typ, nullable,
operatory, przykłady, `suggested_values` tylko dla pól z `suggest_options`).
Brakuje **sygnału semantycznego**: do czego pole służy i jaka jest dziedzina
jego wartości. To najtańsza rzecz, która podnosi trafność generowanego DjangoQL.

Rozszerzamy opis o trzy aspekty, wszystkie **defensywne** (żaden brak metadanej
ani wyjątek DB nie może wywalić opisu schematu — wzorzec z `_field_options`).

## Aspekt 1 — Metadane nazewnicze (`label`, `help_text`)

Źródło: `field.model._meta.get_field(field.name)` (idiom już używany w
`schema.py:56`).

- `label` ← `verbose_name`. **Pomijamy, gdy równa się autogenerowanej
  domyślnej** Django, czyli `field.name` z `_`→spacja (porównanie
  case-insensitive po strip). Sens: emitować tylko labelki wnoszące treść,
  nie dublować nazwy technicznej.
- `help_text` ← emitowany, gdy niepusty (po strip).
- Dotyczy też relacji (`verbose_name` pola FK).
- **Defensywność:** cały odczyt w `try/except (FieldDoesNotExist,
  AttributeError)`. `AttributeError` jest istotny — relacje odwrotne i M2M
  zwracają z `_meta.get_field` obiekt `ManyToOneRel`/`ManyToManyRel` bez
  `verbose_name`. Pola bez realnego pola modelu (`CountField`, `AggregateField`,
  brak `self.model`) → cicho pomijane.

## Aspekt 2 — Choices zawsze

DjangoQL dopasowuje choices po **etykiecie** (`c[1]`), nie po wartości z bazy —
`get_lookup_value` (`schema.py:85-97`) tłumaczy etykietę na wartość DB, a
`get_options('')` (`schema.py:74`) już zwraca etykiety. Czyli istniejąca ścieżka
emituje poprawne stringi do zapytania (działa też dla int-choices, np.
`Book.genre` — `IntField.validate` przepuszcza etykiety przez `get_lookup_value`).

- Pole, którego model field ma `choices` → **zawsze** emituje warianty,
  niezależnie od flagi `suggest_options` (choices są statyczne i darmowe —
  zero SQL, `super().get_options()` czyta je z `_meta`).
- Osobny klucz `choices` (zbiór **zamknięty**) zamiast `suggested_values`
  (otwarte podpowiedzi), plus `note`: wartość **powinna** być jedną z
  wymienionych (uwaga: `StrField.validate` nie egzekwuje wartości spoza choices —
  przejdzie walidację i zwróci 0 wyników; dla int-choices jest egzekwowane).
- Cap defensywny: stała `MAX_CHOICE_VALUES` (domyślnie 100). Większy niż
  `MAX_SUGGESTED_VALUES` (20), bo zbiór zamknięty — LLM powinien znać całą
  dziedzinę, nie próbkę.
- Istniejące `suggested_values` (distinct z DB dla pól tekstowych oflagowanych
  `suggest_options`) zostaje bez zmian — dla otwartych pól tekstowych.

## Aspekt 3 — Wartości FK (auto wg progu + `fk_options`)

W DjangoQL relacji nie porównuje się jako całości (`publisher = X` jest
nielegalne poza `= None`; potwierdzone w `schema.py:649-661`) — przechodzi się
kropką: `publisher.name = "Manning"`. Dlatego „wartości FK" znaczą:
distinct-wartości pola identyfikującego modelu docelowego, podane razem ze
ścieżką traversalu, pod kluczem **`related_values`** (osobnym od
`suggested_values`, które znaczy „wartości własnego pola").

### Sterowanie

- Globalny próg (distinct wartości pola identyfikującego):
  `describe_schema_for_llm(schema, max_fk_options=50)`; flaga `--max-fk-options`
  w komendzie. Domyślnie 50. **`max_fk_options=0` = całkowicie wyłącz auto-tryb**
  (zero zapytań; wartości tylko dla jawnych wpisów `fk_options`).
- Słownik na klasie schematu:

  ```python
  class MySchema(DjangoQLSchema):
      fk_options = {
          Book: {
              'publisher': 'name',              # publisher.name in (...)
              'author': ['last_name', 'skrot'], # wiele pól
              'category': '__str__',            # str(obj) jako przykłady
              'tag': False,                     # nigdy (zero SQL)
              'status': True,                   # wymuś, pole domyślne, ignoruj próg
          }
      }
  ```

### Znaczenie `spec` (wartość per relacja w `fk_options`)

| `spec`              | Zachowanie |
|---------------------|-----------|
| `'name'` (str)      | Emituj distinct-wartości `related.name` jako `match_field` + `related_values`; `note: "publisher.name = <value>"`. Podlega progowi. |
| `['a', 'b']` (list) | Wiele pól identyfikujących: `match_fields` + `related_values` jako dict `{pole: [wartości]}`. Każde pole bramkowane progiem osobno. |
| `'__str__'`         | `str(obj)` wierszy jako `related_examples` (przybliżone — gdy identyfikuje kombinacja pól, np. nazwa/skrót). Bramka: `COUNT(*)`. |
| `False`             | Nigdy nie emituj. Zero zapytań DB. |
| `True`              | Wymuś emisję polem domyślnym, **ignorując próg bramkujący**; lista i tak ucięta do `MAX_SUGGESTED_VALUES`. |

Jawny wpis w `fk_options` **nadpisuje** domyślne wykluczenie modeli wrażliwych
(niżej) — świadoma decyzja autora schematu.

### Tryb auto (relacja bez wpisu w `fk_options`)

- **Domyślnie włączony** (potwierdzona decyzja). Dla relacji bez wpisu:
  1. Wyznacz pole identyfikujące heurystyką (niżej).
  2. Pobierz `related.objects.values_list(pole, flat=True).distinct()
     [:max_fk_options + 1]`. Jedno zapytanie zamiast osobnego COUNT.
  3. Jeśli zwróciło `<= max_fk_options` wartości → emituj `match_field` +
     `related_values`; jeśli więcej → pomiń (sam traversal jak dziś).
- **Heurystyka pola identyfikującego — TYLKO spośród pól widocznych w schemacie**
  (`schema.models[label]`), nie surowych pól modelu. To krytyczne: DjangoQL
  wycina `password` w `get_fields` (`schema.py:435-437`), więc wybór z pól
  schematu automatycznie chroni przed zrzuceniem hashy haseł. Kolejność:
  pole o nazwie `name` → pierwsze pole typu `str` (`field.type == 'str'`) →
  fallback `str(obj)` przez `related_examples` z bramką `COUNT(*)`.
- **Wykluczenie modeli wrażliwych:** relacje, których model docelowy należy do
  wrażliwych app-labeli, są w trybie auto **pomijane** (bez zapytań). Domyślna
  lista (stała `SENSITIVE_TARGET_APP_LABELS`): `auth`, `admin`, `contenttypes`,
  `sessions` (obejmuje `User`, `Group`, `Permission`, `LogEntry`,
  `ContentType`, `Session`). Nadpisywalna jawnym wpisem w `fk_options`.

### Koszt i bezpieczeństwo

- Tryb auto: 1× zapytanie `values_list(...).distinct()[:max+1]` na relację
  (poza wrażliwymi i `False` — zero zapytań), **przy generowaniu opisu**
  (operacja jednorazowa / cache'owalna, nie per-request).
- Wszystkie dostępy do DB w `try/except` — brak wartości nigdy nie przerywa
  opisu schematu.
- **Uwaga prywatności (do docs):** auto-tryb emituje distinct-wartości pól
  widocznych w schemacie także dla relacji nieoflagowanych — to odejście od
  dzisiejszego „nic bez `suggest_options`". Modele wrażliwe są domyślnie
  wyłączone, ale np. distinct wartości pola tekstowego innego modelu mogą trafić
  do promptu. Wyłączenie: `fk_options={Model: {rel: False}}` lub globalnie
  `max_fk_options=0`.

## Format wyjścia

Pojedyncze pole identyfikujące (`spec='name'` lub auto):

```jsonc
"publisher": {
  "type": "relation",
  "relates_to": "core.Publisher",
  "nullable": true,
  "operators": ["= None", "!= None", "<relation>.<field> (traverse with a dot)"],
  "label": "Wydawca",
  "help_text": "Podmiot wydający książkę",
  "match_field": "name",
  "related_values": ["Manning", "O'Reilly", "PWN"],
  "note": "match by traversal: publisher.name = <value>"
}
```

Wiele pól (`spec=['last_name', 'skrot']`):

```jsonc
"author": {
  "type": "relation", "relates_to": "auth.User",
  "match_fields": ["last_name", "skrot"],
  "related_values": {
    "last_name": ["Lem", "Tolkien"],
    "skrot": ["SL", "JRRT"]
  },
  "note": "match by traversal, e.g. author.last_name = <value>"
}
```

`spec='__str__'` lub fallback heurystyki: klucz `related_examples` (lista
`str(obj)`) + `note` o traversalu do pola identyfikującego, zamiast
`match_field`/`related_values`.

> Uwaga: nazwy `core.Publisher`, `publisher`, `tag`, `status`, `skrot` są
> **czysto ilustracyjne** — nie występują w `test_project`. Testy używają
> realnych modeli (niżej).

## Testy (TDD — testy przed implementacją)

Plik `test_project/core/tests/test_llm.py`. Modele: `test_project/core/models.py`
(`Book` z `name`, `genre` = PositiveIntegerField z choices Drama/Comics/Other,
FK `author → auth.User`, M2M `similar_books → Book`).

- **FK auto + `password` (pierwszy test):** relacja `author → User` przy ≤ progu
  userach NIE może wyemitować pola `password` — dowód, że heurystyka bierze pola
  ze schematu. Zarazem `User` jest w modelach wrażliwych → auto pomija go
  całkowicie; test pilnuje obu warstw obrony.
- `label`/`help_text`: pole z jawnym `verbose_name`/`help_text`; pomijanie
  autogenerowanego `verbose_name`; pole custom (bez modelu) nie wywala opisu;
  relacja odwrotna/M2M nie wywala opisu (`AttributeError` złapany).
- choices: `Book.genre` emituje `choices` zawsze (bez `suggest_options`),
  wartości = etykiety; cap `MAX_CHOICE_VALUES` (pole ze 100+ choices przez
  custom `DjangoQLField` w teście, bez migracji).
- FK próg: relacja poniżej progu distinct emituje `match_field`+`related_values`;
  powyżej pomija; `max_fk_options` respektowany; `max_fk_options=0` = off.
- `fk_options`: `'name'`, lista pól (`related_values` jako dict), `'__str__'`
  (`related_examples`), `False` (zero zapytań), `True` (ignoruje próg, cap
  `MAX_SUGGESTED_VALUES`), wpis nadpisuje wykluczenie wrażliwego modelu.
- defensywność: błąd DB / brak pola nie przerywa `describe_schema_for_llm`.

**Pewny dodatek do modeli testowych:** żadne pole w `models.py` nie ma
`verbose_name`/`help_text` — dołożymy pole (lub atrybuty na istniejącym) +
migrację, by przetestować Aspekt 1. Heurystykę `name` testujemy na
`Book.name` przez relację `similar_books → Book`.

## Dokumentacja użytkownika (twardy deliverable)

Rozszerzyć istniejące `docs/llm-schema.md`:

- Sekcja o `label`/`help_text` (skąd, kiedy pomijane).
- Sekcja o choices (zamknięty zbiór, emitowane etykiety, cap 100).
- Sekcja o wartościach FK: `max_fk_options` (w tym `=0` = off), słownik
  `fk_options` z tabelą znaczeń `spec`, tryb auto + heurystyka + wykluczenie
  modeli wrażliwych, **ostrzeżenie o prywatności**, jak wyłączyć.
- Zaktualizować przykładowy JSON o nowe klucze (`label`, `help_text`, `choices`,
  `match_field`/`match_fields`, `related_values`, `related_examples`).
- Zweryfikować `mkdocs build --strict`.

## Poza zakresem (YAGNI)

- Konfigurowalny cap dla choices per pole (globalna stała wystarcza).
- Emisja wartości FK po pk / `object_reference` (semantyka bez zmian).
- Cache wyników zapytań między wywołaniami (opis jest jednorazowy).
- Zawężanie operatorów dla pól z choices (pozostają per-typ).

## Rozstrzygnięcia z review (Fable 5)

1. **Bezpieczeństwo `password`** → heurystyka wybiera tylko spośród pól
   widocznych w schemacie (dziedziczy wykluczenia DjangoQL).
2. **Prywatność / auto-tryb** → auto ON, ale modele wrażliwych app-labeli
   (`auth`/`admin`/`contenttypes`/`sessions`) domyślnie wyłączone; jawny wpis
   `fk_options` nadpisuje.
3. **Semantyka progu** → distinct wartości pola identyfikującego
   (`values_list(f).distinct()[:max+1]`), nie `COUNT(*)` tabeli; ujednolica też
   mechanizm bramkowania (jedno zapytanie). `__str__`/fallback: `COUNT(*)`.
4. **Nazwa klucza** → `related_values` (osobny od `suggested_values`).
5. **`True` a cap** → ignoruje próg bramkujący, ale tnie do `MAX_SUGGESTED_VALUES`.
6. **`AttributeError`** w except (reverse/M2M relacje).
7. **`note` choices** → „powinna", nie „musi" (StrField nie egzekwuje).
8. **Testy** → pole z `verbose_name`/`help_text` to pewny dodatek; test
   `password` pierwszy; przykłady `Publisher`/`skrot` oznaczone ilustracyjnie.
