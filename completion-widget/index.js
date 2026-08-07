import DjangoQL from 'djangoql-completion';

import 'djangoql-completion/dist/completion.css';

// Translate the upstream operator hint labels through Django's JS gettext
// catalog when one is present (the admin loads it via `djangoql-i18n/`). Falls
// back to the English source string off-admin, where no catalog is loaded.
function gettext(s) {
  return window.gettext ? window.gettext(s) : s;
}

// The completion popup's "Syntax Help" link is built by upstream with a
// hard-coded English string baked into the bundle (createCompletionElement),
// so it never passes through Django's JS gettext catalog and stays English even
// in a translated admin. Re-render its text via gettext after the upstream
// method runs. Same approach as the operator hints below: override the
// prototype method, let upstream do its work, then localise the result.
var createCompletionElement = DjangoQL.prototype.createCompletionElement;
DjangoQL.prototype.createCompletionElement = function () {
  createCompletionElement.apply(this, arguments);
  if (this.completion) {
    var link = this.completion.querySelector('p.syntax-help a');
    if (link) {
      link.textContent = gettext('Syntax Help');
    }
  }
};

// The three comparison operators that upstream renders with a human-readable
// hint (e.g. "!=  is not equal to"). Mapped operator text -> English source
// string so we can re-render the hint via gettext. The other operators (=, >,
// startswith, in, ...) carry no hint and are left untouched.
var OP_HINTS = {
  '!=': 'is not equal to',
  '~': 'contains',
  '!~': 'does not contain',
};

// When a suggestion is picked, the upstream widget writes the new value
// straight to `textarea.value`. Assigning `.value` does NOT fire an `input`
// event, so anything listening for one — notably the highlight overlay
// (highlight.js repaints its coloured backdrop on `input`) — never learns the
// text changed. The result is invisible "white-on-white" text for everything
// chosen from the popup, until the next keystroke repaints it.
//
// Fix it at the single source every integration shares: dispatch a bubbling
// `input` event after `selectCompletion` runs, exactly as real typing would.
var selectCompletion = DjangoQL.prototype.selectCompletion;
DjangoQL.prototype.selectCompletion = function () {
  selectCompletion.apply(this, arguments);
  if (this.textarea) {
    var event;
    try {
      event = new Event('input', { bubbles: true });
    } catch (e) {
      // Legacy browsers without the Event constructor (e.g. IE).
      event = document.createEvent('Event');
      event.initEvent('input', true, false);
    }
    this.textarea.dispatchEvent(event);
  }
};

// Object-picker value suggestions arrive as "Label #<id>" (the id is the filter
// key). Render that trailing " #<id>" as a muted, display-only part so it reads
// as metadata, not a count — the inserted value (s.text) keeps the id, so pk
// filtering is unaffected.
var populateFieldOptions = DjangoQL.prototype.populateFieldOptions;
DjangoQL.prototype.populateFieldOptions = function () {
  populateFieldOptions.apply(this, arguments);
  var suggestions = this.suggestions || [];
  for (var i = 0; i < suggestions.length; i++) {
    var s = suggestions[i];
    if (s && typeof s.suggestionText === 'string') {
      var m = /^(.*\S)\s+(#\d+)$/.exec(s.suggestionText);
      if (m) {
        s.suggestionText = m[1] + ' <i>' + m[2] + '</i>';
      }
    }
  }
};

// An object-picker field (object_reference) points at a related object, so only
// equality and membership are meaningful. The widget treats it as a string
// field (so the value is quoted) and would otherwise also offer ~ / !~ /
// startswith / endswith — strip those, leaving "=  !=  in  not in".
var generateSuggestions = DjangoQL.prototype.generateSuggestions;
var REF_OPERATORS = { '=': 1, '!=': 1, in: 1, 'not in': 1 };
DjangoQL.prototype.generateSuggestions = function () {
  generateSuggestions.apply(this, arguments);
  if (!this.completionEnabled || !this.currentModel || !this.textarea) {
    return;
  }
  var textarea = this.textarea;
  if (textarea.selectionStart !== textarea.selectionEnd) {
    return;
  }
  var context = this.getContext(textarea.value, textarea.selectionStart);
  if (context.scope !== 'comparison') {
    return;
  }
  // Localise the operator hint labels. Rebuild suggestionText from the operator
  // text + translated hint so we don't depend on upstream's exact markup.
  for (var k = 0; k < this.suggestions.length; k++) {
    var sug = this.suggestions[k];
    if (sug && OP_HINTS[sug.text]) {
      sug.suggestionText =
        sug.text + '<i>' + gettext(OP_HINTS[sug.text]) + '</i>';
    }
  }
  var model = this.models[context.model];
  var field = model && context.field && model[context.field];
  if (field && field.object_reference) {
    this.suggestions = this.suggestions.filter(function (s) {
      return REF_OPERATORS[s.text] === 1;
    });
    this.selected = this.suggestions.length === 1 ? 0 : null;
  }
};

// Value autocomplete inside an `in ( ... )` list. The upstream widget detects
// value scope only right after a binary operator, not inside an IN list. When
// the caret sits inside `<field> in ( ... |` (or `not in ( ... |`), resolve
// <field> and switch to value scope so its suggestions appear; the widget's
// existing value selection/insertion then works unchanged.
function inListField(djangoql, text, pos) {
  var before = text.slice(0, pos);
  var tokens = djangoql.lexer.setInput(before).lexAll();
  var depth = 0;
  for (var i = tokens.length - 1; i >= 0; i--) {
    var name = tokens[i].name;
    if (name === 'PAREN_R') {
      depth += 1;
    } else if (name === 'PAREN_L') {
      if (depth > 0) {
        depth -= 1;
      } else {
        // Unclosed '(' — an IN-list opener is "<NAME> [not] in (".
        if (tokens[i - 1] && tokens[i - 1].name === 'IN') {
          var j = i - 2;
          if (tokens[j] && tokens[j].name === 'NOT') {
            j -= 1;
          }
          var nameToken = tokens[j];
          if (nameToken && nameToken.name === 'NAME') {
            var last = tokens[tokens.length - 1];
            var prefix = before.slice(last.end).replace(/^\s+/, '');
            if (prefix.charAt(0) === '"' || prefix.charAt(0) === "'") {
              prefix = prefix.slice(1);
            }
            return { name: nameToken.value, prefix: prefix };
          }
        }
        return null;
      }
    }
  }
  return null;
}

var getContext = DjangoQL.prototype.getContext;
DjangoQL.prototype.getContext = function (text, pos) {
  var context = getContext.call(this, text, pos);
  try {
    if (context.scope !== 'value' && this.currentModel) {
      var inList = inListField(this, text, pos);
      if (inList) {
        var resolved = this.resolveName(inList.name);
        if (resolved.model && resolved.field) {
          context.scope = 'value';
          context.model = resolved.model;
          context.field = resolved.field;
          context.modelStack = resolved.modelStack;
          context.prefix = inList.prefix;
        }
      }
    }
  } catch (e) {
    // In-list value scope is a best-effort enhancement on top of the base
    // completion; never let it break the base behavior. Surface the cause for
    // debugging instead of swallowing it silently.
    if (window.console && window.console.debug) {
      window.console.debug('djangoql: in-list completion skipped', e);
    }
  }
  return context;
};

window.DjangoQL = DjangoQL;
