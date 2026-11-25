"""
The completion widget must never treat suggested text as markup.

Suggestions are rendered with ``innerHTML``. Their text comes from the server
-- field names, and values such as the names of database objects -- so it has
to be escaped on the way in. ``completion-widget/safe-markup.js`` does that;
these tests run it under Node (it is plain, DOM-free JavaScript) and also check
that the shipped bundle was rebuilt with it.
"""

import json
import pathlib
import shutil
import subprocess
import tempfile

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCE = REPO_ROOT / 'completion-widget' / 'safe-markup.js'
BUNDLE = REPO_ROOT / 'djangoql' / 'static' / 'djangoql' / 'js' / 'completion.js'

HOSTILE = '<img src=x onerror=alert(1)>'


def markup(text, prefix='', case_sensitive=True):
    node = shutil.which('node')
    if node is None:
        pytest.skip('node is not installed')
    with tempfile.TemporaryDirectory() as tmp:
        # The source is an ES module with a .js name (that is what webpack
        # bundles); Node only loads it as a module from an .mjs file.
        module = pathlib.Path(tmp) / 'safe-markup.mjs'
        shutil.copy(SOURCE, module)
        script = (
            'import { suggestionMarkup } from %s;'
            'const [text, prefix, cs] = JSON.parse(process.argv[1]);'
            'process.stdout.write(suggestionMarkup(text, prefix, cs));'
        ) % json.dumps(module.as_uri())
        result = subprocess.run(
            [
                node,
                '--input-type=module',
                '-e',
                script,
                json.dumps([text, prefix, case_sensitive]),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    return result.stdout


def test_markup_in_a_value_is_escaped():
    out = markup(HOSTILE)
    assert '<img' not in out
    assert out == '&lt;img src=x onerror=alert(1)&gt;'


def test_markup_in_a_value_is_escaped_around_the_highlight():
    # The typed prefix is marked with <b>; the rest stays escaped, and so does
    # the marked part itself.
    out = markup(HOSTILE, prefix='img')
    assert out == '&lt;<b>img</b> src=x onerror=alert(1)&gt;'
    assert markup('a<b', prefix='<') == 'a<b>&lt;</b>b'


def test_typed_prefix_is_not_markup_either():
    # The prefix used to be spliced into the markup unescaped as well.
    assert markup('x<u>y', prefix='<u>') == 'x<b>&lt;u&gt;</b>y'


def test_hint_is_kept_as_a_hint():
    # The widget's own trailing <i>…</i> (operator hints, "#<id>" of object
    # pickers) still renders as an element.
    assert markup('!=<i>is not equal to</i>') == '!=<i>is not equal to</i>'
    assert markup('Ada <i>#12</i>', prefix='Ad') == '<b>Ad</b>a <i>#12</i>'


def test_markup_before_a_hint_is_escaped():
    out = markup(HOSTILE + ' <i>#7</i>')
    assert out == '&lt;img src=x onerror=alert(1)&gt; <i>#7</i>'


def test_a_hint_cannot_carry_markup():
    # Only a tag-free trailing <i>…</i> counts as a hint; anything else is data.
    out = markup('x<i><img src=x onerror=alert(1)></i>')
    assert '<img' not in out and '<i>' not in out


def test_case_insensitive_highlight():
    assert markup('Poland', prefix='po', case_sensitive=False) == (
        '<b>Po</b>land'
    )
    assert markup('Poland', prefix='po', case_sensitive=True) == 'Poland'


def test_plain_text_is_unchanged():
    assert markup('author') == 'author'
    assert markup('author', prefix='au') == '<b>au</b>thor'
    assert markup('') == ''


def test_bundle_was_rebuilt_with_the_escaping():
    # The package ships the built bundle, not the sources: a fix that never
    # made it through `yarn build` protects no one.
    bundle = BUNDLE.read_text(encoding='utf-8')
    assert 'escapesSuggestions' in bundle
    assert '&lt;' in bundle
