# Składnia zapytań DjangoQL

## Warunki wyszukiwania

Warunek wyszukiwania to podstawowy element składowy zapytania. Składa się zawsze
z 3 elementów: `field` (pola), `comparison operator` (operatora porównania) oraz
`value` (wartości), umieszczonych dokładnie w tej kolejności, od lewej do prawej.

Przykład — wyszukiwanie użytkowników o imieniu „Jan". W poniższym przykładzie
`first_name` to `field` (pole), `=` to `comparison operator` (operator
porównania), a `"John"` to `value` (wartość):

```
first_name = "John"
```

Inny przykład — wyszukiwanie użytkowników, którzy zarejestrowali się w 2017 roku
lub później:

```
date_joined >= "2017-01-01"
```

Jeszcze jeden przykład — wyszukiwanie superużytkowników:

```
is_superuser = True
```

I kolejny — znalezienie wszystkich użytkowników, których imiona znajdują się na
podanej liście:

```
first_name in ("John", "Jack", "Jason")
```

## Łączenie warunków wyszukiwania

Wiele warunków wyszukiwania można łączyć za pomocą operatorów logicznych:
`and` (oba warunki muszą być prawdziwe) oraz `or` (co najmniej jeden z warunków
musi być prawdziwy, bez względu na to który). Ważne — operatory logiczne muszą
być pisane małymi literami: `and` i `or` jest poprawne, natomiast `AND` lub `OR`
jest niepoprawne i spowoduje błąd.

Przykład: wyszukiwanie użytkowników o imieniu „Jan" `and` zarejestrowanych w
2017 roku lub później. Zwróć uwagę, że mamy tu 2 warunki wyszukiwania połączone
operatorem `and`:

```
first_name = "John" and date_joined >= "2017-01-01"
```

Kolejny przykład — wyszukiwanie użytkowników, którzy są albo superużytkownikami
`or` mają zaznaczoną flagę „Staff":

```
is_superuser = True or is_staff = True
```

Operatory logiczne mogą być bardzo przydatne, ponieważ umożliwiają budowanie
złożonych zapytań. Jeśli tworzysz złożone zapytanie, warto pamiętać o ważnej
wskazówce: jeżeli zapytanie zawiera zarówno operator `and`, jak i `or`, zdecydowanie
zalecamy użycie nawiasów w celu określenia kolejności wykonywania operatorów. Oto
przykład ilustrujący, dlaczego jest to istotne. Załóżmy, że chcesz pobrać
użytkowników, którzy są albo superużytkownikami `or` mają flagę Staff, `and`
zarejestrowali się w 2017 roku lub później. Może kusić napisanie zapytania w
tej postaci:

```
is_superuser = True or is_staff = True and date_joined > "2017-01-01"
```

Problem z powyższym zapytaniem polega na tym, że nie zadziała ono zgodnie z
oczekiwaniami, ponieważ operator `and` jest oceniany w pierwszej kolejności.
W rzeczywistości pobiera ono użytkowników, którzy są albo superużytkownikami
(bez względu na datę rejestracji) `or` użytkowników, którzy jednocześnie mają
flagę Staff `and` zarejestrowali się po 2017 roku. Problem ten można rozwiązać
za pomocą nawiasów — wystarczy otoczyć nimi warunki, które mają być oceniane
w pierwszej kolejności:

```
(is_superuser = True or is_staff = True) and date_joined > "2017-01-01"
```

Używanie nawiasów zalecane jest wyłącznie wtedy, gdy zapytanie miesza oba
operatory — `and` i `or`. Jeżeli zapytanie zawiera wiele operatorów logicznych
tylko jednego rodzaju (same `and` albo same `or`), można spokojnie pominąć
nawiasy — zapytanie zadziała zgodnie z oczekiwaniami.

## Pola

W zapytaniu wyszukiwania należy odwoływać się do pól bieżącego modelu dokładnie
tak, jak są zdefiniowane w kodzie Pythona dla danego modelu Django. Pole
wpisywania zapytania posiada funkcję automatycznego uzupełniania, która wyskakuje
automatycznie i podpowiada wszystkie dostępne opcje. Jeśli nie jesteś pewien
nazwy pola, wybierz jedną z wyświetlonych opcji (przykład):

![Przykład autouzupełniania DjangoQL](COMPLETION_EXAMPLE_IMG)

W większości przypadków wewnętrzne pola modelu Django wyglądają podobnie do tego,
co widać w interfejsie administracyjnym Django — po prostu pisane małymi literami
i z `_` zamiast spacji. Na przykład w standardowym interfejsie administracyjnym
Users wewnętrzne pole `first_name` wyświetlane jest jako `First name`, pole
`email` — jako `Email address` itd. Mogą jednak istnieć wyjątki: gdy programiści
zdefiniowali niestandardowe nazwy wyświetlane, które znacznie różnią się od ich
wewnętrznej reprezentacji. W takich przypadkach warto poprosić programistów
o nadpisanie tego szablonu pomocy i podanie tutaj mapowania „nazwa wewnętrzna →
nazwa wyświetlana" dla pól.

Należy pamiętać, że niektóre pola widoczne w panelu administracyjnym Django mogą
nie być przeszukiwalne. Dotyczy to pól obliczanych, czyli takich, które nie są
przechowywane w bazie danych jako zwykła wartość, lecz są wyliczane z innych
wartości w kodzie.

## Powiązane modele

DjangoQL umożliwia przeszukiwanie również według powiązanych modeli (automatycznie
konwertuje relacje na złączenia SQL w tle). Do wskazywania powiązanych modeli i
ich pól używaj separatora `.` (kropki). Na przykład:

```
groups.name in ("Marketing", "Support")
```

Widzisz `.` w powyższym przykładzie? Oznacza to, że `groups` jest powiązanym
modelem, a `name` to pole tego modelu. Jak zwykle autouzupełnianie DjangoQL
podpowiada wszystkie dostępne powiązane modele i ich pola. W przypadku złożonych
struktur danych można stosować wiele poziomów relacji — czyli wskazać powiązany
model, następnie jego powiązany model i tak dalej.

W większości przypadków warunek wyszukiwania z powiązanym modelem musi wskazywać
konkretne pole tego modelu, a nie sam powiązany model. Na przykład
`groups in ("Marketing", "Support")` nie zadziała, ponieważ `groups` jest
modelem, a nie polem. Modele mogą mieć wiele pól, a serwer nie wie, z którym
polem chcesz wykonać porównanie. Istnieje jednak jeden godny uwagi wyjątek —
gdy chcesz znaleźć rekordy, które są powiązane (lub nie są powiązane) z
jakimkolwiek powiązanym modelem danego rodzaju. W takim przypadku należy
porównać powiązany model ze specjalną wartością `None`, w ten sposób:

```
groups = None
```

Powyższy przykład wyszuka użytkowników, którzy nie należą do żadnej grupy. Jeśli
zamiast tego chcesz znaleźć wszystkich użytkowników należących do co najmniej
jednej grupy, użyj `!= None`:

```
groups != None
```

## Operatory porównania

| Operator | Znaczenie | Przykład |
| --- | --- | --- |
| `=` | równa się | `first_name = "John"` |
| `!=` | nie równa się | `id != 42` |
| `~` | zawiera podciąg | `email ~ "@gmail.com"` |
| `!~` | nie zawiera podciągu | `username !~ "test"` |
| `startswith` | zaczyna się od podciągu | `last_name startswith "do"` |
| `not startswith` | nie zaczyna się od podciągu | `last_name not startswith "do"` |
| `endswith` | kończy się podciągiem | `last_name endswith "oe"` |
| `not endswith` | nie kończy się podciągiem | `last_name not endswith "oe"` |
| `>` | większy | `date_joined > "2017-02-28"` |
| `>=` | większy lub równy | `id >= 9000` |
| `<` | mniejszy | `id < 9000` |
| `<=` | mniejszy lub równy | `last_login <= "2017-02-28 14:53"` |
| `in` | wartość jest na liście | `first_name in ("John", "Jack", "Jason")` |
| `not in` | wartość nie jest na liście | `id not in (42, 9000)` |

Uwagi:

1. Operatory `~` i `!~` można stosować wyłącznie do pól tekstowych (string)
   oraz pól daty/daty i czasu. Pole daty/daty i czasu jest wówczas traktowane
   jak pole tekstowe (np. `payment_date ~ "2020-12-01"`).
2. Operatory `startswith`, `not startswith`, `endswith` i `not endswith` można
   stosować wyłącznie do pól tekstowych (string).
3. Wartości `True`, `False` i `None` można łączyć wyłącznie z operatorami `=` i `!=`.
4. Operatory `in` i `not in` muszą być pisane małymi literami. `IN` lub `NOT IN`
   jest niepoprawne i spowoduje błąd.

## Wartości

| Typ | Przykłady | Komentarze |
| --- | --- | --- |
| string | `"this is a string"` `'another string'` | Ciągi tekstowe można zamknąć w cudzysłowie podwójnym, jak `"this"`, lub pojedynczym, jak `'this'`. Jeśli ciąg zawiera ten sam rodzaj cudzysłowu, który go otacza, należy poprzedzić te znaki ukośnikiem odwrotnym (backslash), na przykład `"this is a string with \"quoted\" text"` lub `'this is a string with \'quoted\' text'`. |
| int | `42`, `0`, `-9000` | Liczby całkowite to po prostu cyfry z opcjonalnym jednoargumentowym minusem. Przy wpisywaniu dużych liczb nie należy używać separatorów tysięcy — DjangoQL ich nie rozpoznaje. |
| float | `3.14`, `-0.5`, `5.972e24` | Liczby zmiennoprzecinkowe wyglądają jak liczby całkowite z opcjonalną częścią ułamkową oddzieloną kropką. Można też używać notacji `e` do podania potęgi dziesięciu. Na przykład `5.972e24` oznacza 5,972 × 10^24. |
| bool | `True`, `False` | Wartość logiczna to specjalny typ przyjmujący tylko dwie wartości: `True` lub `False`. Wartości te są rozróżniane co do wielkości liter — należy pisać `True` lub `False` dokładnie w tej formie, z pierwszą literą wielką i pozostałymi małymi, bez cudzysłowów. |
| date | `"2017-02-28"` | Daty są reprezentowane jako ciągi tekstowe w formacie `"YYYY-MM-DD"`. |
| datetime | `"2017-02-28 14:53"` `"2017-02-28 14:53:07"` | Data i godzina mogą być reprezentowane jako ciąg w formacie `"YYYY-MM-DD HH:MM"` lub opcjonalnie z sekundami w formacie `"YYYY-MM-DD HH:MM:SS"` (zegar 24-godzinny). Należy pamiętać, że porównania daty i czasu są wykonywane w strefie czasowej serwera, którą zazwyczaj jest UTC. |
| null | `None` | Jest to specjalna wartość reprezentująca brak jakiejkolwiek wartości: `None`. Należy ją pisać dokładnie w tej formie, z pierwszą literą wielką i pozostałymi małymi, bez cudzysłowów. Użyj jej, gdy jakieś pole w bazie danych dopuszcza wartość null (tzn. może zawierać NULL w terminologii SQL) i chcesz wyszukać rekordy, które albo nie mają wartości (`some_field = None`), albo mają jakąś wartość (`some_field != None`). |
