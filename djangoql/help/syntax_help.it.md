# Sintassi di ricerca DjangoQL

## Condizioni di ricerca

Una condizione di ricerca è il blocco fondamentale di una query di ricerca. È sempre composta da
3 elementi: `field`, `comparison operator` e `value`, disposti esattamente in questo
ordine da sinistra a destra.

Ecco un esempio: ricerca di utenti con nome "John". Nell'esempio
seguente `first_name` è il `field`, `=` è il `comparison operator` e `"John"` è
il `value`:

```
first_name = "John"
```

Un altro esempio: ricerca di utenti che si sono registrati nel 2017 o successivamente:

```
date_joined >= "2017-01-01"
```

Un altro esempio ancora: ricerca dei super-utenti:

```
is_superuser = True
```

E un ultimo esempio: trovare tutti gli utenti i cui nomi sono contenuti in un elenco dato:

```
first_name in ("John", "Jack", "Jason")
```

## Condizioni di ricerca multiple

È possibile combinare più condizioni di ricerca utilizzando gli operatori logici
`and` (entrambe le condizioni devono essere vere) e `or` (almeno una delle condizioni
deve essere vera, indipendentemente da quale). Importante: gli operatori logici devono essere scritti
in minuscolo: `and` e `or` sono corretti, mentre `AND` o `OR` sono errati e causeranno
un errore.

Esempio: ricerca di utenti con nome "John" `and` registrati nel 2017 o
successivamente. Si noti che in questo caso abbiamo 2 condizioni di ricerca, unite con `and`:

```
first_name = "John" and date_joined >= "2017-01-01"
```

Un altro esempio: ricerca di utenti che sono super-utenti `or` contrassegnati con
il flag "Staff":

```
is_superuser = True or is_staff = True
```

Gli operatori logici possono essere molto potenti, poiché consentono di costruire query di ricerca
complesse. Se si sta costruendo una query complessa, c'è un suggerimento importante da tenere
a mente: se la query contiene sia operatori `and` che `or`, si consiglia
vivamente di usare le parentesi per specificare la precedenza degli operatori. Ecco
un esempio per illustrare perché questo è importante. Supponiamo di voler
ottenere gli utenti che sono super-utenti `or` contrassegnati con il flag Staff, `and`
registrati nel 2017 o successivamente. Potrebbe essere allettante scrivere una query come questa:

```
is_superuser = True or is_staff = True and date_joined > "2017-01-01"
```

Il problema con la query precedente è che non farà quello che ci si aspetta, perché
l'operatore `and` viene valutato per primo. In realtà restituisce gli utenti che sono
super-utenti (indipendentemente da quando si sono registrati) `or` gli utenti che sono sia Staff `and`
registrati dopo il 2017. Questo problema può essere risolto con le parentesi: basta inserirle
attorno alle condizioni di ricerca che devono essere valutate per prime, in questo modo:

```
(is_superuser = True or is_staff = True) and date_joined > "2017-01-01"
```

L'uso delle parentesi è raccomandato solo quando la query mescola operatori `and` e `or`.
Se la query contiene più operatori logici di un solo tipo
(solo `and` o solo `or`), è possibile omettere le parentesi e la query funzionerà come
previsto.

## Campi

In una query di ricerca, è necessario fare riferimento ai campi del modello corrente esattamente come
sono definiti nel codice Python per quel particolare modello Django. Il campo di input della query di ricerca
dispone di una funzionalità di completamento automatico che si attiva automaticamente e suggerisce tutte
le opzioni disponibili. Se non si è sicuri del nome del campo, selezionare una delle
opzioni visualizzate (esempio):

![Esempio di completamento DjangoQL](COMPLETION_EXAMPLE_IMG)

Nella maggior parte dei casi, i campi interni dei modelli Django sono simili a ciò che si vede
nell'interfaccia di amministrazione di Django, ma in minuscolo e con `_` al posto degli spazi. Ad
esempio, nell'interfaccia di amministrazione standard degli utenti, il campo interno `first_name`
viene visualizzato come `First name`, il campo `email` viene visualizzato come `Email address` e
così via. Tuttavia potrebbero esserci eccezioni, nel caso in cui gli sviluppatori abbiano definito
nomi visualizzati personalizzati che differiscono molto dalla loro rappresentazione interna.
In questi casi potrebbe essere una buona idea chiedere agli sviluppatori di
sovrascrivere questo template di aiuto e fornire una mappatura dei campi "nome interno -> nome visualizzato"
direttamente qui.

Si noti che alcuni campi visibili nell'amministrazione di Django potrebbero non essere ricercabili. Questo
include i campi calcolati, ovvero i campi che non sono memorizzati nel database come un
valore semplice, ma vengono calcolati a partire da altri valori nel codice.

## Modelli correlati

DjangoQL consente di effettuare ricerche anche su modelli correlati (converte automaticamente
le relazioni in JOIN SQL). Utilizzare il separatore `.` (punto) per
designare i modelli correlati e i loro campi. Ad esempio:

```
groups.name in ("Marketing", "Support")
```

Si vede il `.` nell'esempio precedente? Significa che `groups` è un modello correlato e
`name` è un campo di quel modello. Come sempre, il completamento automatico di DjangoQL fornisce
suggerimenti per tutti i modelli correlati disponibili e i loro campi. Per strutture dati complesse
è possibile utilizzare più livelli di relazione, ovvero specificare un modello correlato,
poi il suo modello correlato, e così via.

Nella maggior parte dei casi, la condizione di ricerca con un modello correlato deve specificare il campo
esatto di quel modello, non il modello correlato stesso. Ad esempio, `groups in
("Marketing", "Support")` non funzionerà, perché `groups` è un modello e non
un campo. I modelli possono avere molti campi e il server non sa con quale
campo si desidera eseguire il confronto. Esiste tuttavia una notevole
eccezione: quando si desidera trovare i record che sono collegati (o non
collegati) a qualsiasi modello correlato di quel tipo. In tal caso, è necessario confrontare
il modello correlato con il valore speciale `None`, in questo modo:

```
groups = None
```

L'esempio precedente cerca gli utenti che non appartengono ad alcun gruppo. Se
si desidera invece trovare tutti gli utenti che appartengono ad almeno un gruppo, usare
`!= None`:

```
groups != None
```

## Operatori di confronto

| Operatore | Significato | Esempio |
| --- | --- | --- |
| `=` | uguale | `first_name = "John"` |
| `!=` | diverso | `id != 42` |
| `~` | contiene una sottostringa | `email ~ "@gmail.com"` |
| `!~` | non contiene una sottostringa | `username !~ "test"` |
| `startswith` | inizia con una sottostringa | `last_name startswith "do"` |
| `not startswith` | non inizia con una sottostringa | `last_name not startswith "do"` |
| `endswith` | termina con una sottostringa | `last_name endswith "oe"` |
| `not endswith` | non termina con una sottostringa | `last_name not endswith "oe"` |
| `>` | maggiore | `date_joined > "2017-02-28"` |
| `>=` | maggiore o uguale | `id >= 9000` |
| `<` | minore | `id < 9000` |
| `<=` | minore o uguale | `last_login <= "2017-02-28 14:53"` |
| `in` | il valore è nell'elenco | `first_name in ("John", "Jack", "Jason")` |
| `not in` | il valore non è nell'elenco | `id not in (42, 9000)` |

Note:

1. Gli operatori `~` e `!~` possono essere applicati solo a campi di tipo stringa e data/datetime.
   Un campo data/datetime verrà trattato come stringa (es.,
   `payment_date ~ "2020-12-01"`)
2. `startswith`, `not startswith`, `endswith` e `not endswith` possono essere applicati
   solo a campi di tipo stringa;
3. I valori `True`, `False` e `None` possono essere combinati solo con `=` e `!=`;
4. Gli operatori `in` e `not in` devono essere scritti in minuscolo. `IN` o `NOT IN` è
   errato e causerà un errore.

## Valori

| Tipo | Esempi | Commenti |
| --- | --- | --- |
| string | `"this is a string"` `'another string'` | Le stringhe possono essere racchiuse tra virgolette doppie, come `"this"`, o virgolette singole, come `'this'`. Se la stringa contiene lo stesso tipo di virgolette utilizzate per racchiuderla, è necessario eseguire l'escape di quei caratteri con una barra rovesciata, ad esempio `"this is a string with \"quoted\" text"` o `'this is a string with \'quoted\' text'`. |
| int | `42`, `0`, `-9000` | I numeri interi sono semplicemente cifre con un meno unario opzionale. Se si digitano numeri grandi, non utilizzare i separatori delle migliaia: DjangoQL non li interpreta. |
| float | `3.14`, `-0.5`, `5.972e24` | I numeri in virgola mobile assomigliano ai numeri interi con una parte frazionaria opzionale separata da un punto. È anche possibile usare la notazione `e` per specificare la potenza di dieci. Ad esempio, `5.972e24` significa 5,972 * 10^24. |
| bool | `True`, `False` | Il booleano è un tipo speciale che accetta solo due valori: `True` o `False`. Questi valori sono sensibili alle maiuscole/minuscole: è necessario scrivere `True` o `False` esattamente così, con la prima lettera maiuscola e le altre minuscole, senza virgolette. |
| date | `"2017-02-28"` | Le date sono rappresentate come stringhe nel formato `"YYYY-MM-DD"`. |
| datetime | `"2017-02-28 14:53"` `"2017-02-28 14:53:07"` | La data e l'ora possono essere rappresentate come stringa nel formato `"YYYY-MM-DD HH:MM"`, o facoltativamente con i secondi nel formato `"YYYY-MM-DD HH:MM:SS"` (orologio a 24 ore). Si noti che i confronti con data e ora vengono eseguiti nel fuso orario del server, che di solito è UTC. |
| null | `None` | Questo è un valore speciale che rappresenta l'assenza di qualsiasi valore: `None`. Deve essere scritto esattamente così, con la prima lettera maiuscola e le altre minuscole, senza virgolette. Usarlo quando un campo nel database è nullable (ovvero può contenere NULL in termini SQL) e si desidera cercare i record che non hanno alcun valore (`some_field = None`) o che hanno un valore (`some_field != None`). |
