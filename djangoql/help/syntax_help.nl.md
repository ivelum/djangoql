# DjangoQL zoeksyntaxis

## Zoekcondities

Een zoekconditie is de basiscomponent van een zoekopdracht. Ze bestaat altijd uit
3 elementen: `field`, `comparison operator` en `value`, in precies deze volgorde
van links naar rechts.

Hier een voorbeeld: zoeken naar gebruikers met de voornaam "John". In het
onderstaande voorbeeld is `first_name` een `field`, `=` een `comparison operator`
en `"John"` een `value`:

```
first_name = "John"
```

Een ander voorbeeld: zoeken naar gebruikers die zich in 2017 of later hebben
geregistreerd:

```
date_joined >= "2017-01-01"
```

Nog een voorbeeld: zoeken naar supergebruikers:

```
is_superuser = True
```

En nog één: alle gebruikers vinden waarvan de naam in een gegeven lijst staat:

```
first_name in ("John", "Jack", "Jason")
```

## Meerdere zoekcondities

U kunt meerdere zoekcondities combineren met de logische operatoren
`and` (beide condities moeten waar zijn) en `or` (ten minste één van de condities
moet waar zijn, ongeacht welke). Belangrijk: logische operatoren moeten in kleine
letters worden geschreven: `and` en `or` is correct, maar `AND` of `OR` is
onjuist en geeft een fout.

Voorbeeld: zoeken naar gebruikers met de voornaam "John" `and` geregistreerd in
2017 of later. Let op: hier zijn 2 zoekcondities, verbonden met `and`:

```
first_name = "John" and date_joined >= "2017-01-01"
```

Nog een voorbeeld: zoeken naar gebruikers die óf supergebruiker zijn `or`
het "Staff"-vinkje hebben:

```
is_superuser = True or is_staff = True
```

Logische operatoren kunnen erg krachtig zijn, omdat u er complexe
zoekopdrachten mee kunt bouwen. Als u een complexe query opstelt, is er een
belangrijke tip: als uw query zowel `and`- als `or`-operatoren bevat, raden
we u sterk aan haakjes te gebruiken om de prioriteit van operatoren aan te geven.
Hier een voorbeeld om te laten zien waarom dit belangrijk is. Stel dat u
gebruikers wilt ophalen die óf supergebruiker zijn `or` het Staff-vinkje hebben,
`and` geregistreerd zijn in 2017 of later. Het is verleidelijk om een query als
deze te schrijven:

```
is_superuser = True or is_staff = True and date_joined > "2017-01-01"
```

Het probleem met bovenstaande query is dat deze niet doet wat u verwacht, omdat
de `and`-operator als eerste wordt geëvalueerd. In feite worden gebruikers
opgehaald die óf supergebruiker zijn (ongeacht wanneer ze zich registreerden)
`or` gebruikers die zowel Staff zijn `and` na 2017 zijn geregistreerd. Dit
probleem kunt u oplossen met haakjes: plaats ze rondom de zoekcondities die
als eerste moeten worden geëvalueerd, zoals hier:

```
(is_superuser = True or is_staff = True) and date_joined > "2017-01-01"
```

Haakjes worden alleen aanbevolen als uw query zowel `and`- als `or`-operatoren
bevat. Als uw query meerdere logische operatoren van slechts één soort bevat
(ofwel `and` ofwel `or`), kunt u de haakjes veilig weglaten en werkt alles
zoals verwacht.

## Velden

In een zoekopdracht dient u te verwijzen naar de velden van het huidige model
precies zoals ze zijn gedefinieerd in de Python-code van dat specifieke
Django-model. Het zoekinvoerveld beschikt over een automatische aanvulling die
vanzelf verschijnt en alle beschikbare opties suggereert. Als u niet zeker weet
hoe het veldnaam luidt, kiest u gewoon een van de weergegeven opties (voorbeeld):

![Voorbeeld van DjangoQL-aanvulling](COMPLETION_EXAMPLE_IMG)

In de meeste gevallen lijken interne Django-modelvelden op wat u ziet in de
Django-beheerdersinterface, maar dan in kleine letters en met `_` in plaats van
spaties. In de standaard gebruikersbeheerinterface wordt het interne veld
`first_name` bijvoorbeeld weergegeven als `First name`, het veld `email` als
`Email address`, enzovoort. Er kunnen echter uitzonderingen zijn als ontwikkelaars
aangepaste weergavenamen hebben gedefinieerd die sterk afwijken van hun interne
naam. In dergelijke gevallen kan het nuttig zijn om ontwikkelaars te vragen dit
help-sjabloon te overschrijven en hier een overzicht te bieden van de
"interne naam → weergavenaam"-koppeling.

Houd er rekening mee dat sommige velden die u in de Django-beheerder ziet,
mogelijk niet doorzoekbaar zijn. Dit geldt voor berekende velden, dat wil zeggen
velden die niet als enkelvoudige waarde in de database zijn opgeslagen, maar
worden berekend op basis van andere waarden in de code.

## Gerelateerde modellen

DjangoQL stelt u ook in staat te zoeken op gerelateerde modellen (het zet
relaties automatisch om naar SQL-joins achter de schermen). Gebruik de `.`
puntscheider om gerelateerde modellen en hun velden aan te duiden.
Bijvoorbeeld:

```
groups.name in ("Marketing", "Support")
```

Ziet u de `.` in het bovenstaande voorbeeld? Die geeft aan dat `groups` een
gerelateerd model is en `name` een veld van dat model. Zoals gewoonlijk biedt
de DjangoQL-aanvulling suggesties voor alle beschikbare gerelateerde modellen
en hun velden. Voor complexe gegevensstructuren kunt u meerdere relatieniveaus
gebruiken, d.w.z. een gerelateerd model opgeven, dan diens gerelateerde model,
enzovoort.

In de meeste gevallen moet de zoekconditie met een gerelateerd model het exacte
veld van dat model opgeven, niet het gerelateerde model zelf. Zo werkt
`groups in ("Marketing", "Support")` bijvoorbeeld niet, omdat `groups` een model
is en geen veld. Modellen kunnen veel velden hebben, en de server weet niet op
welk veld u de vergelijking wilt uitvoeren. Er is echter één belangrijke
uitzondering: als u records wilt vinden die gekoppeld zijn aan (of juist niet
gekoppeld zijn aan) gerelateerde modellen van dat type. In dat geval dient u het
gerelateerde model te vergelijken met de speciale waarde `None`, zoals hier:

```
groups = None
```

Het bovenstaande voorbeeld zoekt naar gebruikers die aan geen enkele groep
behoren. Als u in plaats daarvan alle gebruikers wilt vinden die tot ten minste
één groep behoren, gebruikt u `!= None`:

```
groups != None
```

## Vergelijkingsoperatoren

| Operator | Betekenis | Voorbeeld |
| --- | --- | --- |
| `=` | is gelijk aan | `first_name = "John"` |
| `!=` | is niet gelijk aan | `id != 42` |
| `~` | bevat een deelstring | `email ~ "@gmail.com"` |
| `!~` | bevat geen deelstring | `username !~ "test"` |
| `startswith` | begint met een deelstring | `last_name startswith "do"` |
| `not startswith` | begint niet met een deelstring | `last_name not startswith "do"` |
| `endswith` | eindigt met een deelstring | `last_name endswith "oe"` |
| `not endswith` | eindigt niet met een deelstring | `last_name not endswith "oe"` |
| `>` | groter dan | `date_joined > "2017-02-28"` |
| `>=` | groter dan of gelijk aan | `id >= 9000` |
| `<` | kleiner dan | `id < 9000` |
| `<=` | kleiner dan of gelijk aan | `last_login <= "2017-02-28 14:53"` |
| `in` | waarde staat in de lijst | `first_name in ("John", "Jack", "Jason")` |
| `not in` | waarde staat niet in de lijst | `id not in (42, 9000)` |

Opmerkingen:

1. De operatoren `~` en `!~` kunnen alleen worden toegepast op string- en
   datum/datetime-velden. Een datum/datetime-veld wordt dan behandeld als een
   stringveld (bijv. `payment_date ~ "2020-12-01"`)
2. `startswith`, `not startswith`, `endswith` en `not endswith` kunnen alleen
   worden toegepast op stringvelden;
3. De waarden `True`, `False` en `None` kunnen alleen worden gecombineerd met `=` en `!=`;
4. De operatoren `in` en `not in` moeten in kleine letters worden geschreven.
   `IN` of `NOT IN` is onjuist en geeft een fout.

## Waarden

| Type | Voorbeelden | Opmerkingen |
| --- | --- | --- |
| string | `"this is a string"` `'another string'` | Strings kunnen worden omsloten door dubbele aanhalingstekens, zoals `"this"`, of enkele aanhalingstekens, zoals `'this'`. Als uw string hetzelfde type aanhalingsteken bevat als het omsluiting-teken, dient u die tekens te escapen met een backslash, bijvoorbeeld `"this is a string with \"quoted\" text"` of `'this is a string with \'quoted\' text'`. |
| int | `42`, `0`, `-9000` | Gehele getallen zijn gewoon cijfers met een optioneel unair minteken. Gebruik bij grote getallen geen duizendscheidingstekens; DjangoQL begrijpt ze niet. |
| float | `3.14`, `-0.5`, `5.972e24` | Zwevendekommagetallen lijken op gehele getallen met een optioneel fractioneel deel gescheiden door een punt. U kunt ook de `e`-notatie gebruiken voor machten van tien. Zo betekent `5.972e24` bijvoorbeeld 5,972 × 10^24. |
| bool | `True`, `False` | Boolean is een speciaal type dat slechts twee waarden accepteert: `True` of `False`. Deze waarden zijn hoofdlettergevoelig; schrijf `True` of `False` precies zo, met de eerste letter in hoofdletters en de overige in kleine letters, zonder aanhalingstekens. |
| date | `"2017-02-28"` | Datums worden weergegeven als strings in het formaat `"YYYY-MM-DD"`. |
| datetime | `"2017-02-28 14:53"` `"2017-02-28 14:53:07"` | Datum en tijd kunnen worden weergegeven als een string in het formaat `"YYYY-MM-DD HH:MM"`, of optioneel met seconden in het formaat `"YYYY-MM-DD HH:MM:SS"` (24-uursklok). Vergelijkingen met datum en tijd worden uitgevoerd in de tijdzone van de server, wat doorgaans UTC is. |
| null | `None` | Dit is een speciale waarde die de afwezigheid van enige waarde aangeeft: `None`. Schrijf het precies zo, met de eerste letter in hoofdletters en de overige in kleine letters, zonder aanhalingstekens. Gebruik het wanneer een veld in de database nullable is (d.w.z. NULL kan bevatten in SQL-termen) en u wilt zoeken naar records die ofwel geen waarde hebben (`some_field = None`) ofwel een waarde hebben (`some_field != None`). |
