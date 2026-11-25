# DjangoQL-Suchsyntax

## Suchbedingungen

Eine Suchbedingung ist der grundlegende Baustein einer Suchanfrage. Sie besteht
immer aus genau 3 Elementen: `field` (Feld), `comparison operator`
(Vergleichsoperator) und `value` (Wert), in genau dieser Reihenfolge von links
nach rechts.

Ein Beispiel – die Suche nach Benutzern mit dem Vornamen „John". Im folgenden
Beispiel ist `first_name` das `field`, `=` der `comparison operator` und
`"John"` der `value`:

```
first_name = "John"
```

Ein weiteres Beispiel – die Suche nach Benutzern, die sich 2017 oder später
registriert haben:

```
date_joined >= "2017-01-01"
```

Noch ein Beispiel – die Suche nach Superusern:

```
is_superuser = True
```

Und noch eines – die Suche nach allen Benutzern, deren Namen in einer
bestimmten Liste enthalten sind:

```
first_name in ("John", "Jack", "Jason")
```

## Mehrere Suchbedingungen

Mehrere Suchbedingungen lassen sich mit den logischen Operatoren `and` (beide
Bedingungen müssen wahr sein) und `or` (mindestens eine der Bedingungen muss
wahr sein, egal welche) verknüpfen. Wichtig: logische Operatoren müssen
kleingeschrieben werden – `and` und `or` sind korrekt, `AND` und `OR` hingegen
sind falsch und führen zu einem Fehler.

Beispiel: Suche nach Benutzern mit dem Vornamen „John" `and` Registrierung im
Jahr 2017 oder später. Beachten Sie, dass hier 2 Suchbedingungen mit `and`
verknüpft werden:

```
first_name = "John" and date_joined >= "2017-01-01"
```

Noch ein Beispiel – Suche nach Benutzern, die entweder Superuser `or` mit dem
Flag „Staff" markiert sind:

```
is_superuser = True or is_staff = True
```

Logische Operatoren sind sehr mächtig, da sie den Aufbau komplexer Suchanfragen
ermöglichen. Beim Erstellen komplexer Anfragen gibt es einen wichtigen Hinweis:
Enthält Ihre Anfrage sowohl `and`- als auch `or`-Operatoren, empfehlen wir
dringend, Klammern zu verwenden, um die Auswertungsreihenfolge festzulegen.
Nachfolgendes Beispiel verdeutlicht, warum dies wichtig ist. Angenommen, Sie
möchten Benutzer abrufen, die entweder Superuser `or` mit dem Staff-Flag
markiert sind, `and` sich 2017 oder später registriert haben. Es könnte
verlockend sein, folgende Anfrage zu schreiben:

```
is_superuser = True or is_staff = True and date_joined > "2017-01-01"
```

Das Problem mit dieser Anfrage ist, dass sie nicht das tut, was Sie erwarten,
weil der `and`-Operator zuerst ausgewertet wird. Tatsächlich werden damit
Benutzer abgerufen, die entweder Superuser sind (unabhängig vom
Registrierungsdatum) `or` Benutzer, die sowohl Staff `and` nach 2017
registriert sind. Dieses Problem lässt sich durch Klammern beheben –
setzen Sie diese einfach um die Suchbedingungen, die zuerst ausgewertet
werden sollen:

```
(is_superuser = True or is_staff = True) and date_joined > "2017-01-01"
```

Die Verwendung von Klammern wird nur dann empfohlen, wenn Ihre Anfrage sowohl
`and`- als auch `or`-Operatoren mischt. Enthält Ihre Anfrage mehrere logische
Operatoren nur einer Art (ausschließlich `and` oder ausschließlich `or`),
können Sie Klammern problemlos weglassen, und die Anfrage verhält sich wie
erwartet.

## Felder

In einer Suchanfrage sollten Sie die Felder des aktuellen Modells genau so
referenzieren, wie sie im Python-Code für das jeweilige Django-Modell definiert
sind. Das Sucheingabefeld verfügt über eine Auto-Vervollständigung, die
automatisch erscheint und alle verfügbaren Optionen vorschlägt. Falls Sie den
Feldnamen nicht kennen, wählen Sie einfach eine der angezeigten Optionen
(Beispiel):

![DjangoQL-Vervollständigungsbeispiel](COMPLETION_EXAMPLE_IMG)

In den meisten Fällen sehen interne Django-Modellfelder ähnlich aus wie das,
was Sie in der Django-Adminoberfläche sehen – nur in Kleinbuchstaben und mit
`_` anstelle von Leerzeichen. In der Standard-Benutzeradminoberfläche wird das
interne Feld `first_name` beispielsweise als `First name`, das Feld `email`
als `Email address` angezeigt usw. Es kann jedoch Ausnahmen geben, wenn
Entwickler benutzerdefinierte Anzeigenamen vergeben haben, die sich stark von
der internen Bezeichnung unterscheiden. In solchen Fällen wäre es sinnvoll,
die Entwickler zu bitten, dieses Hilfe-Template anzupassen und hier eine
Zuordnung „interner Name → Anzeigename" der Felder bereitzustellen.

Beachten Sie, dass einige in der Django-Adminoberfläche sichtbare Felder
möglicherweise nicht durchsuchbar sind. Dazu gehören berechnete Felder, also
Felder, die nicht als einfacher Wert in der Datenbank gespeichert, sondern im
Code aus anderen Werten berechnet werden.

## Verwandte Modelle

DjangoQL ermöglicht auch die Suche über verwandte Modelle (im Hintergrund
werden Relationen automatisch in SQL-Joins umgewandelt). Verwenden Sie den
Punkt `.` als Trennzeichen, um verwandte Modelle und deren Felder anzugeben.
Zum Beispiel:

```
groups.name in ("Marketing", "Support")
```

Sehen Sie den `.` im obigen Beispiel? Er bedeutet, dass `groups` ein
verwandtes Modell und `name` ein Feld dieses Modells ist. Wie gewohnt bietet
die DjangoQL-Auto-Vervollständigung Vorschläge für alle verfügbaren verwandten
Modelle und deren Felder. Bei komplexen Datenstrukturen können Sie mehrere
Beziehungsebenen verwenden, also ein verwandtes Modell angeben, dann dessen
verwandtes Modell usw.

In den meisten Fällen muss eine Suchbedingung mit einem verwandten Modell das
konkrete Feld dieses Modells angeben, nicht das verwandte Modell selbst.
`groups in ("Marketing", "Support")` funktioniert zum Beispiel nicht, weil
`groups` ein Modell und kein Feld ist. Modelle können viele Felder haben, und
der Server weiß nicht, mit welchem Feld Sie einen Vergleich durchführen
möchten. Es gibt jedoch eine nennenswerte Ausnahme: wenn Sie Datensätze suchen
möchten, die mit einem (oder keinem) verwandten Modell dieser Art verknüpft
sind. In diesem Fall sollten Sie das verwandte Modell mit dem speziellen Wert
`None` vergleichen:

```
groups = None
```

Das obige Beispiel sucht nach Benutzern, die keiner Gruppe angehören. Wenn Sie
stattdessen alle Benutzer finden möchten, die mindestens einer Gruppe angehören,
verwenden Sie `!= None`:

```
groups != None
```

## Vergleichsoperatoren

| Operator | Bedeutung | Beispiel |
| --- | --- | --- |
| `=` | gleich | `first_name = "John"` |
| `!=` | ungleich | `id != 42` |
| `~` | enthält eine Teilzeichenkette | `email ~ "@gmail.com"` |
| `!~` | enthält keine Teilzeichenkette | `username !~ "test"` |
| `startswith` | beginnt mit einer Teilzeichenkette | `last_name startswith "do"` |
| `not startswith` | beginnt nicht mit einer Teilzeichenkette | `last_name not startswith "do"` |
| `endswith` | endet mit einer Teilzeichenkette | `last_name endswith "oe"` |
| `not endswith` | endet nicht mit einer Teilzeichenkette | `last_name not endswith "oe"` |
| `>` | größer als | `date_joined > "2017-02-28"` |
| `>=` | größer als oder gleich | `id >= 9000` |
| `<` | kleiner als | `id < 9000` |
| `<=` | kleiner als oder gleich | `last_login <= "2017-02-28 14:53"` |
| `in` | Wert ist in der Liste enthalten | `first_name in ("John", "Jack", "Jason")` |
| `not in` | Wert ist nicht in der Liste enthalten | `id not in (42, 9000)` |

Hinweise:

1. Die Operatoren `~` und `!~` können nur auf Zeichenketten- und
   Datums-/Datums-Zeit-Felder angewendet werden. Ein Datums-/Datums-Zeit-Feld
   wird dabei wie ein Zeichenkettenfeld behandelt (z. B.
   `payment_date ~ "2020-12-01"`)
2. `startswith`, `not startswith`, `endswith` und `not endswith` können nur auf
   Zeichenkettenfelder angewendet werden;
3. Die Werte `True`, `False` und `None` können nur mit `=` und `!=` kombiniert
   werden;
4. Die Operatoren `in` und `not in` müssen kleingeschrieben werden. `IN` oder
   `NOT IN` ist falsch und führt zu einem Fehler.

## Werte

| Typ | Beispiele | Kommentare |
| --- | --- | --- |
| string | `"this is a string"` `'another string'` | Zeichenketten können entweder in doppelte Anführungszeichen wie `"this"` oder in einfache Anführungszeichen wie `'this'` eingeschlossen werden. Enthält Ihre Zeichenkette denselben Anführungszeichentyp wie den verwendeten Begrenzer, müssen Sie diese Zeichen mit einem Backslash maskieren, zum Beispiel `"this is a string with \"quoted\" text"` oder `'this is a string with \'quoted\' text'`. |
| int | `42`, `0`, `-9000` | Ganzzahlen sind reine Ziffernfolgen mit optionalem unärem Minuszeichen. Verwenden Sie bei großen Zahlen bitte keine Tausendertrennzeichen – DjangoQL versteht diese nicht. |
| float | `3.14`, `-0.5`, `5.972e24` | Gleitkommazahlen sehen wie Ganzzahlen aus, mit einem optionalen Nachkommateil, der durch einen Punkt getrennt wird. Sie können auch die `e`-Notation verwenden, um eine Zehnerpotenz anzugeben. `5.972e24` bedeutet beispielsweise 5,972 × 10^24. |
| bool | `True`, `False` | Boolean ist ein spezieller Typ, der nur zwei Werte akzeptiert: `True` oder `False`. Diese Werte sind Groß-/Kleinschreibungs-sensitiv – schreiben Sie `True` oder `False` genau so, mit dem ersten Buchstaben in Großbuchstaben und den übrigen in Kleinbuchstaben, ohne Anführungszeichen. |
| date | `"2017-02-28"` | Datumsangaben werden als Zeichenketten im Format `"YYYY-MM-DD"` dargestellt. |
| datetime | `"2017-02-28 14:53"` `"2017-02-28 14:53:07"` | Datum und Uhrzeit können als Zeichenkette im Format `"YYYY-MM-DD HH:MM"` oder optional mit Sekunden im Format `"YYYY-MM-DD HH:MM:SS"` dargestellt werden (24-Stunden-Format). Bitte beachten Sie, dass Vergleiche mit Datum und Uhrzeit in der Zeitzone des Servers durchgeführt werden, die in der Regel UTC ist. |
| null | `None` | Dies ist ein spezieller Wert, der das Fehlen eines Wertes repräsentiert: `None`. Er muss genau so geschrieben werden – mit dem ersten Buchstaben in Großbuchstaben und den übrigen in Kleinbuchstaben, ohne Anführungszeichen. Verwenden Sie ihn, wenn ein Datenbankfeld nullable ist (d. h. in SQL NULL enthalten kann) und Sie nach Datensätzen suchen möchten, die entweder keinen Wert haben (`some_field = None`) oder einen Wert haben (`some_field != None`). |
