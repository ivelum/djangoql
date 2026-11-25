# Language reference

DjangoQL is shipped with comprehensive Syntax Help, which can be found in Django admin (see the Syntax Help link in auto-completion popup). Here's a quick summary:

DjangoQL's syntax resembles Python's, with some minor differences. Basically you just reference model fields as you would in Python code, then apply comparison and logical operators and parenthesis. DjangoQL is case-sensitive.

- model fields: exactly as they are defined in Python code. Access nested properties via `.`, for example `author.last_name`;
- strings can be enclosed in either double quotes or single quotes. To escape a quote, use `\"` for double quotes or `\'` for single quotes. You can also use single quotes to enclose strings containing double quotes, and vice versa;
- boolean and null values: `True`, `False`, `None`. Please note that they can be combined only with equality operators, so you can write `published = False or date_published = None`, but `published > False` will cause an error;
- logical operators: `and`, `or`;
- comparison operators: `=`, `!=`, `<`, `<=`, `>`, `>=`
  - work as you expect;
- string-specific comparison operators: `startswith`, `not startswith`, `endswith`, `not endswith` - work as you expect. Test whether or not a string contains a substring: `~` and `!~` (translated into `__icontains` under the hood). Example: `name endswith "peace" or author.last_name ~ "tolstoy"`;
- date-specific comparison operators, compare by date part: `~` and `!~`. Example: `date_published ~ "2021-11"` - find books published in Nov, 2021;
- test a value vs. list: `in`, `not in`. Example: `pk in (2, 3)`.
