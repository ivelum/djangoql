# Sintaxis de búsqueda de DjangoQL

## Condiciones de búsqueda

Una condición de búsqueda es el bloque básico para construir consultas de búsqueda. Siempre consta de
3 elementos: `field`, `comparison operator` y `value`, colocados exactamente en este
orden de izquierda a derecha.

A continuación se muestra un ejemplo: buscar usuarios con el nombre "John". En el ejemplo
`first_name` es el `field`, `=` es el `comparison operator` y `"John"` es
el `value`:

```
first_name = "John"
```

Otro ejemplo, buscar usuarios que se registraron en 2017 o después:

```
date_joined >= "2017-01-01"
```

Un ejemplo más, buscar superusuarios:

```
is_superuser = True
```

Y uno más: encontrar todos los usuarios cuyos nombres están en una lista dada:

```
first_name in ("John", "Jack", "Jason")
```

## Múltiples condiciones de búsqueda

Puede combinar varias condiciones de búsqueda usando los operadores lógicos
`and` (ambas condiciones deben ser verdaderas) y `or` (al menos una de las condiciones
debe ser verdadera, sin importar cuál). Importante: los operadores lógicos deben escribirse
en minúsculas: `and` y `or` son correctos, mientras que `AND` o `OR` son incorrectos y
producirán un error.

Ejemplo: buscar usuarios con el nombre "John" `and` registrados en 2017 o
después. Tenga en cuenta que aquí hay 2 condiciones de búsqueda unidas con `and`:

```
first_name = "John" and date_joined >= "2017-01-01"
```

Un ejemplo más, buscar usuarios que son superusuarios `or` están marcados con
el indicador "Staff":

```
is_superuser = True or is_staff = True
```

Los operadores lógicos pueden ser muy potentes, ya que permiten construir consultas de búsqueda
complejas. Si está construyendo una consulta compleja, hay un consejo importante a tener
en cuenta: si su consulta contiene tanto `and` como `or`, recomendamos
encarecidamente usar paréntesis para especificar la precedencia de los operadores. A
continuación se muestra un ejemplo que ilustra por qué esto es importante. Suponga que desea
obtener usuarios que son superusuarios `or` están marcados con el indicador Staff, `and`
se registraron en 2017 o después. Podría ser tentador escribir una consulta como esta:

```
is_superuser = True or is_staff = True and date_joined > "2017-01-01"
```

El problema con la consulta anterior es que no hará lo que usted espera, porque
el operador `and` se evalúa primero. En realidad, obtiene usuarios que son
superusuarios (sin importar cuándo se registraron) `or` usuarios que son Staff `and`
se registraron después de 2017. Este problema se puede resolver con paréntesis: colóquelos
alrededor de las condiciones de búsqueda que deben evaluarse primero, así:

```
(is_superuser = True or is_staff = True) and date_joined > "2017-01-01"
```

El uso de paréntesis se recomienda solo cuando la consulta mezcla `and` y `or`.
Si su consulta contiene múltiples operadores lógicos de un solo tipo
(ya sea `and` u `or`), puede omitir los paréntesis con seguridad y funcionará
como se espera.

## Campos

En una consulta de búsqueda, debe hacer referencia a los campos del modelo actual exactamente como
están definidos en el código Python para ese modelo de Django. La entrada de la consulta de búsqueda
tiene una función de autocompletado que aparece automáticamente y sugiere todas las opciones
disponibles. Si no está seguro de cuál es el nombre del campo, elija una de las opciones
mostradas (ejemplo):

![Ejemplo de autocompletado de DjangoQL](COMPLETION_EXAMPLE_IMG)

En la mayoría de los casos, los campos internos del modelo de Django se parecen a lo que se ve en
la interfaz de administración de Django, solo en minúsculas y con `_` en lugar de espacios. Por
ejemplo, en la interfaz de administración estándar de usuarios, el campo interno `first_name`
se muestra como `First name`, el campo `email` se muestra como `Email address` y así
sucesivamente. Sin embargo, puede haber excepciones a esto si los desarrolladores han definido
nombres de visualización personalizados que se ven muy diferentes de su representación interna.
En tales casos, podría ser una buena idea pedirle a los desarrolladores que
sobrescriban esta plantilla de ayuda y proporcionen un mapa de campos "nombre interno -> nombre
de visualización" aquí mismo.

Tenga en cuenta que algunos campos que ve en el administrador de Django pueden no ser
buscables. Esto incluye los campos calculados, es decir, campos que no se almacenan en la
base de datos como un valor simple, sino que se calculan a partir de otros valores en el código.

## Modelos relacionados

DjangoQL también permite buscar por modelos relacionados (convierte automáticamente las
relaciones en JOINs de SQL de forma transparente). Use el separador `.` para designar modelos
relacionados y sus campos. Por ejemplo:

```
groups.name in ("Marketing", "Support")
```

¿Ve el `.` en el ejemplo anterior? Significa que `groups` es un modelo relacionado y
`name` es un campo de ese modelo. Como siempre, el autocompletado de DjangoQL proporciona
sugerencias para todos los modelos relacionados disponibles y sus campos. Para estructuras de
datos complejas, puede usar múltiples niveles de relación, es decir, especificar un modelo
relacionado, luego su modelo relacionado, y así sucesivamente.

En la mayoría de los casos, la condición de búsqueda con un modelo relacionado debe especificar el
campo exacto de ese modelo, no el modelo relacionado en sí. Por ejemplo, `groups in
("Marketing", "Support")` no funcionará, porque `groups` es un modelo y no un campo.
Los modelos pueden tener muchos campos y el servidor no sabe contra qué campo desea
realizar la comparación. Sin embargo, hay una excepción notable: cuando desea encontrar
registros que estén vinculados (o no vinculados) a cualquier modelo relacionado de ese tipo.
En tal caso, debe comparar el modelo relacionado con el valor especial `None`, así:

```
groups = None
```

El ejemplo anterior buscaría usuarios que no pertenecen a ningún grupo. Si
desea encontrar todos los usuarios que pertenecen a al menos un grupo, use
`!= None`:

```
groups != None
```

## Operadores de comparación

| Operador | Significado | Ejemplo |
| --- | --- | --- |
| `=` | igual a | `first_name = "John"` |
| `!=` | no igual a | `id != 42` |
| `~` | contiene una subcadena | `email ~ "@gmail.com"` |
| `!~` | no contiene una subcadena | `username !~ "test"` |
| `startswith` | comienza con una subcadena | `last_name startswith "do"` |
| `not startswith` | no comienza con una subcadena | `last_name not startswith "do"` |
| `endswith` | termina con una subcadena | `last_name endswith "oe"` |
| `not endswith` | no termina con una subcadena | `last_name not endswith "oe"` |
| `>` | mayor que | `date_joined > "2017-02-28"` |
| `>=` | mayor o igual que | `id >= 9000` |
| `<` | menor que | `id < 9000` |
| `<=` | menor o igual que | `last_login <= "2017-02-28 14:53"` |
| `in` | el valor está en la lista | `first_name in ("John", "Jack", "Jason")` |
| `not in` | el valor no está en la lista | `id not in (42, 9000)` |

Notas:

1. Los operadores `~` y `!~` solo se pueden aplicar a campos de tipo string y
   date/datetime. Un campo date/datetime se tratará como string (por ejemplo,
   `payment_date ~ "2020-12-01"`)
2. `startswith`, `not startswith`, `endswith` y `not endswith` solo se pueden aplicar
   a campos de tipo string;
3. Los valores `True`, `False` y `None` solo se pueden combinar con `=` y `!=`;
4. Los operadores `in` y `not in` deben escribirse en minúsculas. `IN` o `NOT IN` son
   incorrectos y producirán un error.

## Valores

| Tipo | Ejemplos | Comentarios |
| --- | --- | --- |
| string | `"this is a string"` `'another string'` | Las cadenas pueden encerrarse entre comillas dobles, como `"this"`, o comillas simples, como `'this'`. Si su cadena contiene el mismo tipo de comilla usada para encerrarla, debe escapar esos caracteres con una barra invertida, por ejemplo `"this is a string with \"quoted\" text"` o `'this is a string with \'quoted\' text'`. |
| int | `42`, `0`, `-9000` | Los números enteros son simplemente dígitos con un signo menos unario opcional. Si escribe números grandes, no use separadores de miles, DjangoQL no los reconoce. |
| float | `3.14`, `-0.5`, `5.972e24` | Los números de punto flotante son como los enteros con una parte fraccionaria opcional separada por un punto. También puede usar la notación `e` para especificar potencias de diez. Por ejemplo, `5.972e24` significa 5.972 * 10^24. |
| bool | `True`, `False` | Booleano es un tipo especial que acepta solo dos valores: `True` o `False`. Estos valores distinguen mayúsculas de minúsculas; debe escribir `True` o `False` exactamente así, con la primera letra en mayúscula y las demás en minúscula, sin comillas. |
| date | `"2017-02-28"` | Las fechas se representan como cadenas en formato `"YYYY-MM-DD"`. |
| datetime | `"2017-02-28 14:53"` `"2017-02-28 14:53:07"` | La fecha y la hora pueden representarse como una cadena en formato `"YYYY-MM-DD HH:MM"`, o de forma opcional con segundos en formato `"YYYY-MM-DD HH:MM:SS"` (reloj de 24 horas). Tenga en cuenta que las comparaciones con fecha y hora se realizan en la zona horaria del servidor, que generalmente es UTC. |
| null | `None` | Este es un valor especial que representa la ausencia de cualquier valor: `None`. Debe escribirse exactamente así, con la primera letra en mayúscula y las demás en minúscula, sin comillas. Úselo cuando algún campo de la base de datos admita valores nulos (es decir, puede contener NULL en términos SQL) y desee buscar registros que no tengan valor (`some_field = None`) o que tengan algún valor (`some_field != None`). |
