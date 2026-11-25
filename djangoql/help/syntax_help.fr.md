# Syntaxe de recherche DjangoQL

## Conditions de recherche

Une condition de recherche est le bloc de construction de base d'une requête de
recherche. Elle se compose toujours de 3 éléments : `field` (champ),
`comparison operator` (opérateur de comparaison) et `value` (valeur), placés
exactement dans cet ordre de gauche à droite.

Voici un exemple — rechercher des utilisateurs dont le prénom est "John". Dans
l'exemple ci-dessous, `first_name` est le `field`, `=` est l'`comparison operator`
et `"John"` est la `value` :

```
first_name = "John"
```

Autre exemple, rechercher des utilisateurs qui se sont inscrits en 2017 ou
plus tard :

```
date_joined >= "2017-01-01"
```

Encore un exemple, rechercher les super-utilisateurs :

```
is_superuser = True
```

Et un dernier — trouver tous les utilisateurs dont les noms figurent dans une
liste donnée :

```
first_name in ("John", "Jack", "Jason")
```

## Conditions de recherche multiples

Vous pouvez combiner plusieurs conditions de recherche en utilisant les
opérateurs logiques `and` (les deux conditions doivent être vraies) et `or`
(au moins l'une des conditions doit être vraie, peu importe laquelle). Important
— les opérateurs logiques doivent être écrits en minuscules : `and` et `or` sont
corrects, tandis que `AND` ou `OR` sont incorrects et provoqueront une erreur.

Exemple : rechercher des utilisateurs dont le prénom est "John" `and` qui se sont
inscrits en 2017 ou plus tard. Notez que nous avons ici 2 conditions de
recherche, reliées par `and` :

```
first_name = "John" and date_joined >= "2017-01-01"
```

Encore un exemple, rechercher des utilisateurs qui sont soit des
super-utilisateurs `or` marqués avec l'indicateur "Staff" :

```
is_superuser = True or is_staff = True
```

Les opérateurs logiques peuvent être très puissants, car ils vous permettent de
construire des requêtes de recherche complexes. Si vous construisez une requête
complexe, voici un conseil important à garder à l'esprit : si votre requête
contient à la fois des opérateurs `and` et `or`, nous vous encourageons
vivement à utiliser des parenthèses pour spécifier la priorité des opérateurs.
Voici un exemple pour illustrer pourquoi c'est important. Supposons que vous
vouliez récupérer les utilisateurs qui sont soit des super-utilisateurs `or`
marqués avec l'indicateur Staff, `and` qui se sont inscrits en 2017 ou plus
tard. Il pourrait être tentant d'écrire une requête comme celle-ci :

```
is_superuser = True or is_staff = True and date_joined > "2017-01-01"
```

Le problème avec la requête ci-dessus est qu'elle ne fera pas ce que vous
attendez, car l'opérateur `and` est évalué en premier. En réalité, elle
récupère les utilisateurs qui sont soit des super-utilisateurs (quelle que soit
la date d'inscription) `or` les utilisateurs qui sont à la fois Staff `and`
inscrits après 2017. Ce problème peut être résolu avec des parenthèses — il
suffit de les placer autour des conditions de recherche qui doivent être
évaluées en premier, comme ceci :

```
(is_superuser = True or is_staff = True) and date_joined > "2017-01-01"
```

L'utilisation des parenthèses est recommandée uniquement lorsque votre requête
mélange à la fois des opérateurs `and` et `or`. Si votre requête contient
plusieurs opérateurs logiques d'un seul type (soit `and` soit `or`), vous
pouvez omettre les parenthèses en toute sécurité et elle fonctionnera comme
prévu.

## Champs

Dans une requête de recherche, vous devez référencer les champs du modèle
actuel exactement tels qu'ils sont définis dans le code Python pour ce modèle
Django particulier. La saisie de la requête de recherche dispose d'une fonction
d'auto-complétion qui s'affiche automatiquement et suggère toutes les options
disponibles. Si vous n'êtes pas sûr du nom du champ, choisissez l'une des
options affichées (exemple) :

![Exemple d'auto-complétion DjangoQL](COMPLETION_EXAMPLE_IMG)

Dans la plupart des cas, les champs internes des modèles Django ressemblent à ce
que vous voyez dans l'interface d'administration Django, simplement en minuscules
et avec `_` à la place des espaces. Par exemple, dans l'interface d'administration
standard des utilisateurs, le champ interne `first_name` est affiché comme
`First name`, le champ `email` est affiché comme `Email address`, etc. Cependant,
il peut y avoir des exceptions à cela si les développeurs ont défini des noms
d'affichage personnalisés très différents de leur représentation interne. Dans ces
cas, il peut être judicieux de demander aux développeurs de remplacer ce modèle
d'aide et de fournir ici un mapping "nom interne -> nom d'affichage" des champs.

Notez que certains champs que vous voyez dans l'administration Django peuvent ne
pas être interrogeables. Cela inclut les champs calculés, c'est-à-dire les champs
qui ne sont pas stockés dans la base de données comme valeur brute, mais plutôt
calculés à partir d'autres valeurs dans le code.

## Modèles associés

DjangoQL vous permet également de rechercher par modèles associés (il convertit
automatiquement les relations en jointures SQL en coulisses). Utilisez le
séparateur `.` (point) pour désigner les modèles associés et leurs champs. Par
exemple :

```
groups.name in ("Marketing", "Support")
```

Vous voyez le `.` dans l'exemple ci-dessus ? Il signifie que `groups` est un
modèle associé et `name` est un champ de ce modèle. Comme d'habitude,
l'auto-complétion DjangoQL fournit des suggestions pour tous les modèles associés
disponibles et leurs champs. Pour les structures de données complexes, vous
pouvez utiliser plusieurs niveaux de relation, c'est-à-dire spécifier un modèle
associé, puis son modèle associé, et ainsi de suite.

Dans la plupart des cas, la condition de recherche avec un modèle associé doit
spécifier le champ exact de ce modèle, et non le modèle associé lui-même. Par
exemple, `groups in ("Marketing", "Support")` ne fonctionnera pas, car `groups`
est un modèle et non un champ. Les modèles peuvent avoir de nombreux champs, et
le serveur ne sait pas avec quel champ vous souhaitez effectuer une comparaison.
Cependant, il existe une exception notable à cela — lorsque vous souhaitez
trouver des enregistrements qui sont liés (ou non liés) à n'importe quel modèle
associé de ce type. Dans ce cas, vous devez comparer le modèle associé à la
valeur spéciale `None`, comme ceci :

```
groups = None
```

L'exemple ci-dessus rechercherait les utilisateurs qui n'appartiennent à aucun
groupe. Si vous souhaitez à la inverse trouver tous les utilisateurs qui
appartiennent à au moins un groupe, utilisez `!= None` :

```
groups != None
```

## Opérateurs de comparaison

| Opérateur | Signification | Exemple |
| --- | --- | --- |
| `=` | égal à | `first_name = "John"` |
| `!=` | différent de | `id != 42` |
| `~` | contient une sous-chaîne | `email ~ "@gmail.com"` |
| `!~` | ne contient pas une sous-chaîne | `username !~ "test"` |
| `startswith` | commence par une sous-chaîne | `last_name startswith "do"` |
| `not startswith` | ne commence pas par une sous-chaîne | `last_name not startswith "do"` |
| `endswith` | se termine par une sous-chaîne | `last_name endswith "oe"` |
| `not endswith` | ne se termine pas par une sous-chaîne | `last_name not endswith "oe"` |
| `>` | supérieur à | `date_joined > "2017-02-28"` |
| `>=` | supérieur ou égal à | `id >= 9000` |
| `<` | inférieur à | `id < 9000` |
| `<=` | inférieur ou égal à | `last_login <= "2017-02-28 14:53"` |
| `in` | la valeur est dans la liste | `first_name in ("John", "Jack", "Jason")` |
| `not in` | la valeur n'est pas dans la liste | `id not in (42, 9000)` |

Remarques :

1. Les opérateurs `~` et `!~` ne peuvent être appliqués qu'aux champs de type
   chaîne de caractères et date/datetime. Un champ date/datetime sera traité
   comme un champ chaîne (ex., `payment_date ~ "2020-12-01"`)
2. `startswith`, `not startswith`, `endswith` et `not endswith` ne peuvent être
   appliqués qu'aux champs de type chaîne de caractères ;
3. Les valeurs `True`, `False` et `None` ne peuvent être combinées qu'avec `=`
   et `!=` ;
4. Les opérateurs `in` et `not in` doivent être écrits en minuscules. `IN` ou
   `NOT IN` est incorrect et provoquera une erreur.

## Valeurs

| Type | Exemples | Commentaires |
| --- | --- | --- |
| string | `"this is a string"` `'another string'` | Les chaînes de caractères peuvent être entourées soit de guillemets doubles, comme `"this"`, soit de guillemets simples, comme `'this'`. Si votre chaîne contient le même type de guillemet utilisé pour l'encadrer, vous devez échapper ces caractères avec une barre oblique inverse, par exemple `"this is a string with \"quoted\" text"` ou `'this is a string with \'quoted\' text'`. |
| int | `42`, `0`, `-9000` | Les nombres entiers sont simplement des chiffres avec un signe moins unaire optionnel. Si vous saisissez de grands nombres, n'utilisez pas de séparateurs de milliers, DjangoQL ne les reconnaît pas. |
| float | `3.14`, `-0.5`, `5.972e24` | Les nombres à virgule flottante ressemblent aux nombres entiers avec une partie fractionnaire optionnelle séparée par un point. Vous pouvez également utiliser la notation `e` pour spécifier une puissance de dix. Par exemple, `5.972e24` signifie 5,972 * 10^24. |
| bool | `True`, `False` | Le booléen est un type spécial qui accepte uniquement deux valeurs : `True` ou `False`. Ces valeurs sont sensibles à la casse — vous devez écrire `True` ou `False` exactement ainsi, avec la première lettre en majuscule et les autres en minuscules, sans guillemets. |
| date | `"2017-02-28"` | Les dates sont représentées sous forme de chaînes au format `"YYYY-MM-DD"`. |
| datetime | `"2017-02-28 14:53"` `"2017-02-28 14:53:07"` | La date et l'heure peuvent être représentées sous forme de chaîne au format `"YYYY-MM-DD HH:MM"`, ou optionnellement avec les secondes au format `"YYYY-MM-DD HH:MM:SS"` (horloge 24 heures). Veuillez noter que les comparaisons avec la date et l'heure sont effectuées dans le fuseau horaire du serveur, qui est généralement UTC. |
| null | `None` | Il s'agit d'une valeur spéciale qui représente l'absence de toute valeur : `None`. Elle doit être écrite exactement ainsi, avec la première lettre en majuscule et les autres en minuscules, sans guillemets. Utilisez-la lorsqu'un champ dans la base de données est nullable (c'est-à-dire qu'il peut contenir NULL en termes SQL) et que vous souhaitez rechercher des enregistrements qui soit n'ont aucune valeur (`some_field = None`) soit ont une valeur (`some_field != None`). |
