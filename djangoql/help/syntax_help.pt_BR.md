# Sintaxe de busca do DjangoQL

## Condições de busca

Uma condição de busca é o bloco fundamental para construir uma consulta. Ela sempre é
composta por 3 elementos: `field`, `comparison operator` e `value`, dispostos exatamente
nesta ordem, da esquerda para a direita.

Veja um exemplo — buscando usuários com o primeiro nome "John". No exemplo abaixo,
`first_name` é o `field`, `=` é o `comparison operator` e `"John"` é o `value`:

```
first_name = "John"
```

Outro exemplo, buscando usuários que se registraram em 2017 ou depois:

```
date_joined >= "2017-01-01"
```

Mais um exemplo, buscando super-usuários:

```
is_superuser = True
```

E mais um — encontrando todos os usuários cujos nomes estão em uma lista:

```
first_name in ("John", "Jack", "Jason")
```

## Múltiplas condições de busca

Você pode combinar várias condições de busca usando os operadores lógicos
`and` (ambas as condições precisam ser verdadeiras) e `or` (pelo menos uma das
condições precisa ser verdadeira, não importa qual). Importante — os operadores
lógicos devem ser escritos em minúsculas: `and` e `or` estão corretos, enquanto
`AND` ou `OR` estão incorretos e causarão um erro.

Exemplo: buscando usuários com o primeiro nome "John" `and` que se registraram em
2017 ou depois. Observe que temos 2 condições de busca aqui, unidas com `and`:

```
first_name = "John" and date_joined >= "2017-01-01"
```

Mais um exemplo, buscando usuários que são super-usuários `or` marcados com a
flag "Staff":

```
is_superuser = True or is_staff = True
```

Os operadores lógicos podem ser bastante poderosos, pois permitem construir consultas
complexas. Se você estiver construindo uma consulta complexa, há uma dica importante a
ter em mente: se sua consulta contém tanto `and` quanto `or`, recomendamos fortemente
o uso de parênteses para especificar a precedência dos operadores. Veja um exemplo
que ilustra por que isso é importante. Suponha que você queira buscar usuários que
sejam super-usuários `or` marcados com a flag Staff, `and` que tenham se registrado
em 2017 ou depois. Pode ser tentador escrever uma consulta assim:

```
is_superuser = True or is_staff = True and date_joined > "2017-01-01"
```

O problema com a consulta acima é que ela não fará o que você espera, pois o
operador `and` é avaliado primeiro. Na prática, ela retorna usuários que são
super-usuários (independentemente de quando se registraram) `or` usuários que são
Staff `and` se registraram após 2017. Esse problema pode ser resolvido com
parênteses — basta colocá-los ao redor das condições que devem ser avaliadas
primeiro, assim:

```
(is_superuser = True or is_staff = True) and date_joined > "2017-01-01"
```

O uso de parênteses é recomendado somente quando sua consulta mistura `and` e `or`.
Se sua consulta contém múltiplos operadores lógicos de apenas um tipo (somente `and`
ou somente `or`), você pode omitir os parênteses com segurança e a consulta
funcionará como esperado.

## Campos

Em uma consulta de busca, você deve referenciar os campos do modelo atual exatamente
como estão definidos no código Python para aquele modelo Django específico. O campo
de entrada da consulta possui um recurso de autocompletar que aparece automaticamente
e sugere todas as opções disponíveis. Se você não tiver certeza sobre o nome do
campo, escolha uma das opções exibidas (exemplo):

![Exemplo de autocompletar do DjangoQL](COMPLETION_EXAMPLE_IMG)

Na maioria dos casos, os campos internos de modelos Django são semelhantes ao que
você vê na interface do Django admin, apenas em minúsculas e com `_` no lugar de
espaços. Por exemplo, na interface padrão do admin de Usuários, o campo interno
`first_name` é exibido como `First name`, o campo `email` é exibido como
`Email address` e assim por diante. No entanto, podem existir exceções, caso
os desenvolvedores tenham definido nomes de exibição personalizados que sejam
muito diferentes de sua representação interna. Nesse caso, pode ser uma boa ideia
pedir aos desenvolvedores que substituam este template de ajuda e forneçam um
mapeamento "nome interno → nome de exibição" dos campos aqui mesmo.

Observe que alguns campos visíveis no Django admin podem não ser pesquisáveis. Isso
inclui campos calculados, ou seja, campos que não são armazenados no banco de dados
como um valor simples, mas calculados a partir de outros valores no código.

## Modelos relacionados

O DjangoQL permite buscar por modelos relacionados também (ele converte
automaticamente as relações em JOINs SQL internamente). Use o separador `.` ponto
para designar modelos relacionados e seus campos. Por exemplo:

```
groups.name in ("Marketing", "Support")
```

Viu o `.` no exemplo acima? Ele indica que `groups` é um modelo relacionado e
`name` é um campo desse modelo. Como de costume, o autocompletar do DjangoQL
fornece sugestões para todos os modelos relacionados disponíveis e seus campos.
Para estruturas de dados complexas, você pode usar múltiplos níveis de relação,
ou seja, especificar um modelo relacionado, depois o modelo relacionado a ele, e
assim por diante.

Na maioria dos casos, a condição de busca com um modelo relacionado deve especificar
o campo exato desse modelo, e não o modelo relacionado em si. Por exemplo,
`groups in ("Marketing", "Support")` não funcionará, porque `groups` é um modelo
e não um campo. Modelos podem ter muitos campos, e o servidor não sabe com qual
campo você deseja realizar a comparação. No entanto, há uma exceção notável — quando
você deseja encontrar registros que estejam vinculados (ou não vinculados) a algum
modelo relacionado desse tipo. Nesse caso, você deve comparar o modelo relacionado
ao valor especial `None`, assim:

```
groups = None
```

O exemplo acima buscaria usuários que não pertencem a nenhum grupo. Se você quiser
encontrar todos os usuários que pertencem a pelo menos algum grupo, use `!= None`:

```
groups != None
```

## Operadores de comparação

| Operador | Significado | Exemplo |
| --- | --- | --- |
| `=` | igual a | `first_name = "John"` |
| `!=` | diferente de | `id != 42` |
| `~` | contém uma substring | `email ~ "@gmail.com"` |
| `!~` | não contém uma substring | `username !~ "test"` |
| `startswith` | começa com uma substring | `last_name startswith "do"` |
| `not startswith` | não começa com uma substring | `last_name not startswith "do"` |
| `endswith` | termina com uma substring | `last_name endswith "oe"` |
| `not endswith` | não termina com uma substring | `last_name not endswith "oe"` |
| `>` | maior que | `date_joined > "2017-02-28"` |
| `>=` | maior ou igual a | `id >= 9000` |
| `<` | menor que | `id < 9000` |
| `<=` | menor ou igual a | `last_login <= "2017-02-28 14:53"` |
| `in` | valor está na lista | `first_name in ("John", "Jack", "Jason")` |
| `not in` | valor não está na lista | `id not in (42, 9000)` |

Notas:

1. Os operadores `~` e `!~` podem ser aplicados apenas a campos do tipo string e
   date/datetime. Um campo date/datetime será tratado como string (ex.:
   `payment_date ~ "2020-12-01"`)
2. `startswith`, `not startswith`, `endswith` e `not endswith` podem ser aplicados
   somente a campos do tipo string;
3. Os valores `True`, `False` e `None` podem ser combinados apenas com `=` e `!=`;
4. Os operadores `in` e `not in` devem ser escritos em minúsculas. `IN` ou `NOT IN`
   estão incorretos e causarão um erro.

## Valores

| Tipo | Exemplos | Comentários |
| --- | --- | --- |
| string | `"this is a string"` `'another string'` | Strings podem ser delimitadas por aspas duplas, como `"this"`, ou aspas simples, como `'this'`. Se sua string contiver o mesmo tipo de aspas usado para delimitá-la, você deve escapar esses caracteres com uma barra invertida, por exemplo `"this is a string with \"quoted\" text"` ou `'this is a string with \'quoted\' text'`. |
| int | `42`, `0`, `-9000` | Números inteiros são apenas dígitos com sinal de menos unário opcional. Se você estiver digitando números grandes, não use separadores de milhar — o DjangoQL não os reconhece. |
| float | `3.14`, `-0.5`, `5.972e24` | Números de ponto flutuante parecem números inteiros com parte fracionária opcional separada por ponto. Você também pode usar a notação `e` para especificar potência de dez. Por exemplo, `5.972e24` significa 5,972 × 10^24. |
| bool | `True`, `False` | Boolean é um tipo especial que aceita apenas dois valores: `True` ou `False`. Esses valores diferenciam maiúsculas de minúsculas — você deve escrevê-los exatamente assim, com a primeira letra em maiúscula e as demais em minúscula, sem aspas. |
| date | `"2017-02-28"` | Datas são representadas como strings no formato `"YYYY-MM-DD"`. |
| datetime | `"2017-02-28 14:53"` `"2017-02-28 14:53:07"` | Data e hora podem ser representadas como string no formato `"YYYY-MM-DD HH:MM"`, ou opcionalmente com segundos no formato `"YYYY-MM-DD HH:MM:SS"` (relógio de 24 horas). Observe que as comparações com data e hora são realizadas no fuso horário do servidor, que normalmente é UTC. |
| null | `None` | Este é um valor especial que representa a ausência de qualquer valor: `None`. Deve ser escrito exatamente assim, com a primeira letra em maiúscula e as demais em minúscula, sem aspas. Use-o quando algum campo no banco de dados for anulável (ou seja, puder conter NULL em termos SQL) e você quiser buscar registros que não possuam valor (`some_field = None`) ou que possuam algum valor (`some_field != None`). |
