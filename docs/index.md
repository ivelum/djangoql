# DjangoQL

[![Tests](https://github.com/iplweb/djangoql-iplweb/actions/workflows/tests.yaml/badge.svg)](https://github.com/iplweb/djangoql-iplweb/actions/workflows/tests.yaml)
[![PyPI](https://img.shields.io/pypi/v/djangoql-iplweb)](https://pypi.org/project/djangoql-iplweb/)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://github.com/iplweb/djangoql-iplweb)
[![Django Version](https://img.shields.io/badge/django-5.2%20%7C%206.0%20%7C%206.1-blue)](https://github.com/iplweb/djangoql-iplweb)
[![License](https://img.shields.io/github/license/iplweb/djangoql-iplweb)](https://github.com/iplweb/djangoql-iplweb/blob/master/LICENSE)

Advanced search language for Django, with auto-completion. Supports logical operators, parenthesis, table joins, and works with any Django model. Tested on Python 3.10–3.14, Django 5.2, 6.0 and 6.1. The auto-completion feature has been tested in Chrome, Firefox, Safari, IE9+.

> **This is a community fork.** `djangoql-iplweb` is a fork of the original
> [**DjangoQL** by ivelum](https://github.com/ivelum/djangoql) — install the
> upstream package from [`djangoql` on PyPI](https://pypi.org/project/djangoql/).
> This fork adds internationalization (i18n) of error messages and modernized
> packaging/tooling.
>
> These changes are offered back to the upstream project. **If the original
> maintainers merge them, please switch back to the upstream
> [`djangoql`](https://pypi.org/project/djangoql/) package** — this fork exists
> only to make the improvements available in the meantime, and will defer to
> upstream once they land there.
>
> It is published on PyPI as **`djangoql-iplweb`**, but the import name stays
> `djangoql` (so `INSTALLED_APPS` and `import djangoql` are unchanged).

See a video: [DjangoQL demo](https://youtu.be/oKVff4dHZB8)

![DjangoQL auto-completion example](https://raw.githubusercontent.com/iplweb/djangoql-iplweb/master/djangoql/static/djangoql/img/completion_example_scaled.png)

## Features

- Python-like query syntax: logical operators (`and`, `or`), parenthesis, and the full set of comparison operators
- Searches across model relations via joins, e.g. `author.last_name = "Tolstoy"`
- Works with any Django model and drops into the Django admin with a single mixin
- Live auto-completion of model field names and values in the admin
- Configurable schema to restrict searchable models/fields and provide suggestion options
- Custom search fields for annotations and fully custom search logic
- Internationalized error messages with translation catalogs for 11 locales
- Usable outside the Django admin, including a standalone JavaScript completion widget

## Supported versions

DjangoQL is tested against the following Django × Python combinations:

| Django  | 3.10 | 3.11 | 3.12 | 3.13 | 3.14 |
|---------|:----:|:----:|:----:|:----:|:----:|
| 5.2 LTS |  ✓   |  ✓   |  ✓   |  ✓   |  ✓   |
| 6.0     |  —   |  —   |  ✓   |  ✓   |  ✓   |
| 6.1     |  —   |  —   |  ✓   |  ✓   |  ✓   |

## Supported by

This fork is graciously supported and maintained by **[iplweb](https://www.iplweb.pl/)**.

<a href="https://www.iplweb.pl/"><img src="https://avatars.githubusercontent.com/iplweb" alt="iplweb" width="96" /></a>

## License

MIT

See [Installation](installation.md) to get started.
