# AutocompleteField `lookup_name` + idiom `<fk>__rel` (relacja + picker obok)

Date: 2026-06-04
Status: **Do akceptacji.**

## Problem

`AutocompleteField` (0.22) wystawia FK jako **liść-picker**: pod jego nazwą
filtrujesz po pk wybranego obiektu, ale **nie** trawersujesz już w podpola
(`author.name`). Dokumentacja mówi: *„Need both → use a second field name"*
(`docs/integrating-django-autocomplete-light.md:37-39`).

Brakuje dwóch rzeczy, żeby ten „drugi nazwany picker" był ergonomiczny:

1. **Remap nazwy → realny FK.** Picker pod nazwą np. `author__rel` buduje lookup
   z `get_lookup_name()`, który zwraca `self.name` → `author__rel`. To **nie
   jest** kolumna w bazie, więc filtr `author__rel = pk` wywala się
   (`FieldError`). Jedyne dziś wyjście to podklasa nadpisująca
   `get_lookup_name()` — boilerplate kopiowany w każdym projekcie.
2. **Brak udokumentowanego idiomu.** Wzorzec „zostaw relację z kropką do
   trawersacji, a picker dodaj pod `<fk>__rel`" jest tylko wspomniany jednym
   zdaniem, bez działającego przykładu pokazującego współistnienie
   `author.name` (trawersacja) i `author__rel = …` (picker).

Realny use-case: BPP chce `autorzy.autor.nazwisko` (trawersacja) **oraz**
`autorzy.autor__rel = "Kowalski, Jan [42]"` (picker) jednocześnie.

## Decyzja

Zmiana **wyłącznie addytywna, non-breaking** (to NIE jest „jedna nazwa robi
oba" — to ergonomia wzorca dwóch nazw):

1. **Kwarg `lookup_name` na `AutocompleteField`.** Domyślnie `None` →
   `get_lookup_name()` zwraca `self.name` (zachowanie identyczne jak dziś). Gdy
   podany — `get_lookup_name()` zwraca `lookup_name`, więc pole pod nazwą
   `author__rel` filtruje realny FK `author` (i `author__<search_field>` w
   fallbacku free-text).
2. **Sekcja w docach** z idiomem `<fk>__rel` i działającym przykładem
   współistnienia trawersacji i pickera.

Konwencja nazwy `<fk>__rel` (podwójny underscore — spójnie z rodziną pól
pochodnych `__count`/`__sum`/…; `rel` = „filtruj po całym obiekcie powiązanym")
jest **rekomendacją w docach**, nie wymuszeniem w kodzie — `lookup_name` działa
z dowolną nazwą pola.

## Architektura

### `djangoql/extras.py`

`AutocompleteField.__init__` przyjmuje `lookup_name=None`, zapisuje
`self._lookup_name`. Nowa metoda:

```python
def get_lookup_name(self):
    return self._lookup_name or self.name
```

To wystarczy: `get_lookup()` (filtr po pk) i `_free_text_lookup()` (fallback
icontains) już budują ścieżkę z `path + [self.get_lookup_name()]`, więc oba
trafią na realny FK. `parse_id`, `validate`, providery — bez zmian.

### `docs/integrating-django-autocomplete-light.md`

Nowa sekcja „Exposing a FK as both a navigable relation and a value picker":
- relacja zostaje pod naturalną nazwą (trawersacja: `author.name`,
  `author.country.code`, derived `author__count`…);
- picker pod `<fk>__rel`, z `lookup_name` wskazującym realny FK;
- przykład: `get_fields()` dorzuca syntetyczną nazwę `author__rel`, mapa
  `autocomplete` mapuje ją na `AutocompleteField(lookup_name='author', url=…)`;
- pokazać, że oba zapytania działają jednocześnie:
  `author.last_name = "Kowalski"` (trawersacja) i
  `author__rel = "Jan Kowalski [42]"` (picker).
- zaznaczyć: to nadal dwie nazwy (świadomie), a `__rel` to konwencja.

Dopisać `lookup_name` do tabeli „Configuration reference".

### `CHANGES.rst`

Wpis pod kolejną wersją: addytywny `lookup_name` + udokumentowany idiom
`<fk>__rel`. Non-breaking.

## Plan testów (TDD)

- **default**: `AutocompleteField(name='x')` → `get_lookup_name() == 'x'`
  (regresja: brak `lookup_name` nie zmienia niczego; istniejące testy pickera
  dalej zielone).
- **remap pk**: pole `name='author__rel', lookup_name='author'`,
  `get_lookup([], '=', 'Jan [42]')` → `Q(author=42)` (nie `author__rel`).
- **remap free-text**: to samo pole, `get_lookup([], '=', 'kow')` (bez `[id]`,
  `search_fields=['last_name']`) → `Q(author__last_name__icontains='kow')`.
- **remap z path**: `get_lookup(['memberships'], '=', 'X [7]')` →
  `Q(memberships__author=7)`.
- **idiom end-to-end**: schemat z relacją `author` (RelationField, trawersacja)
  + `author__rel` (AutocompleteField, `lookup_name='author'`) na tym samym
  modelu; `resolve_name('author.last_name')` zwraca leaf StrField,
  `resolve_name('author__rel')` zwraca AutocompleteField; oba lookupy poprawne.
- **serializacja**: `author__rel` async → `options: true` (bez zmian względem
  obecnego pickera).

## Poza zakresem

- „Jedna nazwa robi oba" (relacja-terminal porównywalna jako picker bez drugiej
  nazwy) — to byłaby zmiana `resolve_name`/`validate` w core; odrzucona.
- Zmiany w completion-widgecie (JS).
