// Markup of one completion suggestion, with every piece of data escaped.
//
// Upstream renders a suggestion with `li.innerHTML = highlight(suggestionText,
// prefix)`, and `suggestionText` is the suggested text as it came from the
// server -- a field name, or a value such as the name of a database object --
// optionally followed by a hint wrapped in `<i>…</i>`. Nothing is escaped on
// the way, so a value containing markup was parsed as markup by whoever opened
// the completion popup.
//
// `suggestionMarkup` is a drop-in replacement for `highlight`: it takes the
// same string apart into the label and the trailing hint, escapes both, and
// marks the typed prefix inside the label. The only markup in its output is the
// `<b>` and `<i>` it adds itself.

var ESCAPES = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, function (c) {
    return ESCAPES[c];
  });
}

// A hint is the `<i>…</i>` the widget itself appends: last thing in the
// string, no markup inside. Anything else that looks like a tag is data.
var HINT = /<i>([^<]*)<\/i>$/;

export function splitSuggestion(suggestionText) {
  var text = String(suggestionText == null ? '' : suggestionText);
  var m = HINT.exec(text);
  if (!m) {
    return { label: text, hint: null };
  }
  return { label: text.slice(0, m.index), hint: m[1] };
}

export function markPrefix(label, prefix, caseSensitive) {
  if (!prefix) {
    return escapeHtml(label);
  }
  var haystack = caseSensitive ? label : label.toLowerCase();
  var needle = caseSensitive ? prefix : prefix.toLowerCase();
  if (!needle || haystack.length !== label.length) {
    // Lower-casing changed the length (a few Unicode letters do that), so
    // offsets in `haystack` no longer point into `label`: skip the marking.
    return escapeHtml(label);
  }
  var out = '';
  var pos = 0;
  var found = haystack.indexOf(needle, pos);
  while (found !== -1) {
    out += escapeHtml(label.slice(pos, found));
    out += '<b>' + escapeHtml(label.slice(found, found + needle.length)) + '</b>';
    pos = found + needle.length;
    found = haystack.indexOf(needle, pos);
  }
  return out + escapeHtml(label.slice(pos));
}

export function suggestionMarkup(suggestionText, prefix, caseSensitive) {
  var parts = splitSuggestion(suggestionText);
  var html = markPrefix(parts.label, prefix, caseSensitive);
  if (parts.hint !== null) {
    html += '<i>' + escapeHtml(parts.hint) + '</i>';
  }
  return html;
}
