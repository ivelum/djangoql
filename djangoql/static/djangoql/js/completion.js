(function (root, factory) {
  'use strict';

  /* global define, require */

  if (typeof define === 'function' && define.amd) {
    // AMD. Register as an anonymous module.
    define('DjangoQL', ['Lexer'], factory);
  } else if (typeof exports === 'object') {
    // Node. Does not work with strict CommonJS, but
    // only CommonJS-like environments that support module.exports,
    // like Node.
    module.exports = factory(require('Lexer'));  // eslint-disable-line
  } else {
    // Browser globals (root is window)
    root.DjangoQL = factory(root.Lexer);  // eslint-disable-line
  }
}(this, function (Lexer) {
  'use strict';

  var reIntValue = '(-?0|-?[1-9][0-9]*)';
  var reFractionPart = '\\.[0-9]+';
  var reExponentPart = '[eE][+-]?[0-9]+';
  var intRegex = new RegExp(reIntValue);
  var floatRegex = new RegExp(
      reIntValue + reFractionPart + reExponentPart + '|' +
      reIntValue + reFractionPart + '|' +
      reIntValue + reExponentPart);
  var reLineTerminators = '\\n\\r\\u2028\\u2029';
  var reEscapedChar = '\\\\[\\\\"/bfnrt]';
  var reEscapedUnicode = '\\\\u[0-9A-Fa-f]{4}';
  var reStringChar = '[^\\"\\\\' + reLineTerminators + ']';
  var stringRegex = new RegExp(
      '\\"(' + reEscapedChar +
      '|' + reEscapedUnicode +
      '|' + reStringChar + ')*\\"');
  var nameRegex = /[_A-Za-z][_0-9A-Za-z]*(\.[_A-Za-z][_0-9A-Za-z]*)*/;
  var reNotFollowedByName = '(?![_0-9A-Za-z])';
  var whitespaceRegex = /[ \t\v\f\u00A0]+/;

  var lexer = new Lexer(function () {
    // Silently swallow any lexer errors
  });

  function token(name, value) {
    return { name: name, value: value };
  }

  lexer.addRule(whitespaceRegex, function () { /* ignore whitespace */ });
  lexer.addRule(/\./, function (l) { return token('DOT', l); });
  lexer.addRule(/,/, function (l) { return token('COMMA', l); });
  lexer.addRule(new RegExp('or' + reNotFollowedByName), function (l) {
    return token('OR', l);
  });
  lexer.addRule(new RegExp('and' + reNotFollowedByName), function (l) {
    return token('AND', l);
  });
  lexer.addRule(new RegExp('not' + reNotFollowedByName), function (l) {
    return token('NOT', l);
  });
  lexer.addRule(new RegExp('in' + reNotFollowedByName), function (l) {
    return token('IN', l);
  });
  lexer.addRule(new RegExp('True' + reNotFollowedByName), function (l) {
    return token('TRUE', l);
  });
  lexer.addRule(new RegExp('False' + reNotFollowedByName), function (l) {
    return token('FALSE', l);
  });
  lexer.addRule(new RegExp('None' + reNotFollowedByName), function (l) {
    return token('NONE', l);
  });
  lexer.addRule(nameRegex, function (l) { return token('NAME', l); });
  lexer.addRule(stringRegex, function (l) {
    // Trim leading and trailing quotes
    return token('STRING_VALUE', l.slice(1, l.length - 1));
  });
  lexer.addRule(intRegex, function (l) { return token('INT_VALUE', l); });
  lexer.addRule(floatRegex, function (l) { return token('FLOAT_VALUE', l); });
  lexer.addRule(/\(/, function (l) { return token('PAREN_L', l); });
  lexer.addRule(/\)/, function (l) { return token('PAREN_R', l); });
  lexer.addRule(/=/, function (l) { return token('EQUALS', l); });
  lexer.addRule(/!=/, function (l) { return token('NOT_EQUALS', l); });
  lexer.addRule(/>/, function (l) { return token('GREATER', l); });
  lexer.addRule(/>=/, function (l) { return token('GREATER_EQUAL', l); });
  lexer.addRule(/</, function (l) { return token('LESS', l); });
  lexer.addRule(/<=/, function (l) { return token('LESS_EQUAL', l); });
  lexer.addRule(/~/, function (l) { return token('CONTAINS', l); });
  lexer.addRule(/!~/, function (l) { return token('NOT_CONTAINS', l); });
  lexer.lexAll = function () {
    var match;
    var result = [];
    while (match = this.lex()) {  // eslint-disable-line no-cond-assign
      match.start = this.index - match.value.length;
      match.end = this.index;
      result.push(match);
    }
    return result;
  };

  function suggestion(text, snippetBefore, snippetAfter) {
    // text is being displayed in completion box and pasted when you hit Enter.
    // snippetBefore is an optional extra text to be pasted before main text.
    // snippetAfter is an optional text to be pasted after. It may also include
    // "|" symbol to designate desired cursor position after paste.
    return {
      text: text,
      snippetBefore: snippetBefore || '',
      snippetAfter: snippetAfter || ''
    };
  }

  // Main DjangoQL object
  return {
    currentModel: null,
    models: {},

    token: token,
    lexer: lexer,

    prefix: '',
    suggestions: [],
    selected: null,
    valuesCaseSensitive: false,
    highlightCaseSensitive: true,

    textarea: null,
    completion: null,
    completionUL: null,

    init: function (options) {
      var syntaxHelp;

      // Initialization
      if (!this.isObject(options)) {
        this.logError('Please pass an object with initialization parameters');
        return;
      }
      this.loadIntrospections(options.introspections);
      this.textarea = document.querySelector(options.selector);
      if (!this.textarea) {
        this.logError('Element not found by selector: ' + options.selector);
        return;
      }
      if (this.textarea.tagName !== 'TEXTAREA') {
        this.logError('selector must be pointing to <textarea> element, but ' +
            this.textarea.tagName + ' was found');
        return;
      }
      if (options.valuesCaseSensitive) {
        this.valuesCaseSensitive = true;
      }

      // these handlers are re-used more than once in the code below,
      // so it's handy to have them already bound
      this.onCompletionMouseClick = this.onCompletionMouseClick.bind(this);
      this.onCompletionMouseDown = this.onCompletionMouseDown.bind(this);
      this.onCompletionMouseOut = this.onCompletionMouseOut.bind(this);
      this.onCompletionMouseOver = this.onCompletionMouseOver.bind(this);
      this.popupCompletion = this.popupCompletion.bind(this);
      this.debouncedRenderCompletion = this.debounce(
          this.renderCompletion.bind(this),
          50);

      // Bind event handlers and initialize completion & textSize containers
      this.textarea.setAttribute('autocomplete', 'off');
      this.textarea.addEventListener('keydown', this.onKeydown.bind(this));
      this.textarea.addEventListener('blur', this.hideCompletion.bind(this));
      this.textarea.addEventListener('click', this.popupCompletion);
      if (options.autoResize) {
        this.textareaResize = this.textareaResize.bind(this);
        this.textarea.style.resize = 'none';
        this.textarea.style.overflow = 'hidden';
        this.textarea.addEventListener('input', this.textareaResize);
        this.textareaResize();
        // There could be a situation when fonts are not loaded yet at this
        // point. When fonts are finally loaded it could make textarea looking
        // weird - for example in Django 1.9+ last line won't fit. To fix this
        // we call .textareaResize() once again when window is fully loaded.
        window.addEventListener('load', this.textareaResize);
      } else {
        this.textareaResize = null;
        // Catch resize events and re-position completion box.
        // See http://stackoverflow.com/a/7055239
        this.textarea.addEventListener(
            'mouseup', this.renderCompletion.bind(this, true));
        this.textarea.addEventListener(
            'mouseout', this.renderCompletion.bind(this, true));
      }

      this.completion = document.createElement('div');
      this.completion.className = 'djangoql-completion';
      document.querySelector('body').appendChild(this.completion);
      this.completionUL = document.createElement('ul');
      this.completion.appendChild(this.completionUL);
      if (typeof options.syntaxHelp === 'string') {
        syntaxHelp = document.createElement('p');
        syntaxHelp.className = 'syntax-help';
        syntaxHelp.innerHTML = '<a href="' + options.syntaxHelp +
            '" target="_blank">Syntax Help</a>';
        syntaxHelp.addEventListener('mousedown', function (e) {
          // This is needed to prevent conflict with textarea.onblur event
          // handler, which tries to hide the completion box and therefore
          // makes Syntax Help link malfunctional.
          e.preventDefault();
        });
        this.completion.appendChild(syntaxHelp);
      }
    },

    loadIntrospections: function (introspections) {
      var onLoadError;
      var request;
      if (typeof introspections === 'string') {
        // treat as URL
        onLoadError = function () {
          this.logError('failed to load introspections from ' + introspections);
        }.bind(this);
        request = new XMLHttpRequest();
        request.open('GET', introspections, true);
        request.onload = function () {
          var data;
          if (request.status === 200) {
            data = JSON.parse(request.responseText);
            this.currentModel = data.current_model;
            this.models = data.models;
          } else {
            onLoadError();
          }
        }.bind(this);
        request.ontimeout = onLoadError;
        request.onerror = onLoadError;
        /* eslint-disable max-len */
        // Workaround for IE9, see
        // https://cypressnorth.com/programming/internet-explorer-aborting-ajax-requests-fixed/
        /* eslint-enable max-len */
        request.onprogress = function () {};
        window.setTimeout(request.send.bind(request));
      } else if (this.isObject(introspections)) {
        this.currentModel = introspections.current_model;
        this.models = introspections.models;
      } else {
        this.logError(
            'introspections parameter is expected to be either URL or ' +
            'object with definitions, but ' + introspections + ' was found');
      }
    },

    isObject: function (obj) {
      return (({}).toString.call(obj) === '[object Object]');
    },

    debounce: function (func, wait, immediate) {
      // Borrowed from Underscore.js
      var args;
      var context;
      var result;
      var timeout;
      var timestamp;

      var later = function () {
        var last = Date.now() - timestamp;
        if (last < wait && last >= 0) {
          timeout = setTimeout(later, wait - last);
        } else {
          timeout = null;
          if (!immediate) {
            result = func.apply(context, args);
            if (!timeout) {
              args = null;
              context = null;
            }
          }
        }
      };

      return function () {
        var callNow;
        context = this;
        args = arguments;
        timestamp = Date.now();
        callNow = immediate && !timeout;
        if (!timeout) timeout = setTimeout(later, wait);
        if (callNow) {
          result = func.apply(context, args);
          args = null;
          context = null;
        }
        return result;
      };
    },

    logError: function (message) {
      console.error('DjangoQL: ' + message);  // eslint-disable-line no-console
    },

    DOMReady: function (callback) {
      if (document.readyState !== 'loading') {
        callback();
      } else {
        document.addEventListener('DOMContentLoaded', callback);
      }
    },

    onCompletionMouseClick: function (e) {
      this.selectCompletion(parseInt(e.target.getAttribute('data-index'), 10));
    },

    onCompletionMouseDown: function (e) {
      // This is needed to prevent 'blur' event on textarea
      e.preventDefault();
    },

    onCompletionMouseOut: function () {
      this.selected = null;
      this.debouncedRenderCompletion();
    },

    onCompletionMouseOver: function (e) {
      this.selected = parseInt(e.target.getAttribute('data-index'), 10);
      this.debouncedRenderCompletion();
    },

    onKeydown: function (e) {
      switch (e.keyCode) {
        case 38:  // up arrow
          if (this.suggestions.length) {
            if (this.selected === null) {
              this.selected = this.suggestions.length - 1;
            } else if (this.selected === 0) {
              this.selected = null;
            } else {
              this.selected -= 1;
            }
            this.renderCompletion();
            e.preventDefault();
          }
          break;

        case 40:  // down arrow
          if (this.suggestions.length) {
            if (this.selected === null) {
              this.selected = 0;
            } else if (this.selected < this.suggestions.length - 1) {
              this.selected += 1;
            } else {
              this.selected = null;
            }
            this.renderCompletion();
            e.preventDefault();
          }
          break;

        case 9:   // Tab
          if (this.selected !== null) {
            this.selectCompletion(this.selected);
            e.preventDefault();
          }
          break;

        case 13:  // Enter
          if (this.selected !== null) {
            this.selectCompletion(this.selected);
          } else {
            // Technically this is a textarea, due to automatic multi-line
            // feature, but other than that it should look and behave like
            // a normal input. So expected behavior when pressing Enter is
            // to submit the form, not to add a new line.
            e.target.form.submit();
          }
          e.preventDefault();
          break;

        case 27:  // Esc
          this.hideCompletion();
          break;

        case 16:  // Shift
        case 17:  // Ctrl
        case 18:  // Alt
        case 91:  // Windows Key or Left Cmd on Mac
        case 93:  // Windows Menu or Right Cmd on Mac
          // Control keys shouldn't trigger completion popup
          break;

        default:
          // When keydown is fired input value has not been updated yet,
          // so we need to wait
          window.setTimeout(this.popupCompletion, 10);
          break;
      }
    },

    textareaResize: function () {
      // Automatically grow/shrink textarea to have the contents always visible
      var style = window.getComputedStyle(this.textarea, null);
      var heightOffset = parseFloat(style.paddingTop) +
          parseFloat(style.paddingBottom);
      this.textarea.style.height = '5px';
      // dirty hack, works for Django admin styles only.
      // Ping me if you know how to get rid of "+1"
      this.textarea.style.height = (this.textarea.scrollHeight - heightOffset) +
          1 + 'px';
    },

    popupCompletion: function () {
      this.generateSuggestions();
      this.renderCompletion();
    },

    selectCompletion: function (index) {
      var startPos = this.textarea.selectionStart - this.prefix.length;
      var textAfter = this.textarea.value.slice(startPos + this.prefix.length);
      var textBefore = this.textarea.value.slice(0, startPos);

      var snippetAfterParts = this.suggestions[index].snippetAfter.split('|');
      var textToPaste = this.suggestions[index].snippetBefore +
          this.suggestions[index].text +
          snippetAfterParts.join('');
      var cursorPosAfter = textBefore.length + textToPaste.length;
      if (snippetAfterParts.length > 1) {
        cursorPosAfter -= snippetAfterParts[1].length;
      }

      this.textarea.value = textBefore + textToPaste + textAfter;
      this.textarea.focus();
      this.textarea.setSelectionRange(cursorPosAfter, cursorPosAfter);
      this.selected = null;
      if (this.textareaResize) {
        this.textareaResize();
      }
      this.generateSuggestions(this.textarea);
      this.renderCompletion();
    },

    hideCompletion: function () {
      this.selected = null;
      if (this.completion) {
        this.completion.style.display = 'none';
      }
    },

    escapeRegExp: function (str) {
      // http://stackoverflow.com
      // /questions/3446170/escape-string-for-use-in-javascript-regex
      return str.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, '\\$&');  // eslint-disable-line
    },

    highlight: function (text, highlight) {
      if (!highlight || !text) {
        return text;
      } else if (this.highlightCaseSensitive) {
        return text.split(highlight).join('<b>' + highlight + '</b>');
      }
      return text.replace(
          new RegExp('(' + this.escapeRegExp(highlight) + ')', 'ig'),
          '<b>$1</b>');
    },

    renderCompletion: function (dontForceDisplay) {
      var currentLi;
      var i;
      var completionRect;
      var currentLiRect;
      var inputRect;
      var li;
      var liLen;
      var suggestionsLen;

      if (dontForceDisplay && this.completion.style.display === 'none') {
        return;
      }
      if (!this.suggestions.length) {
        this.hideCompletion();
        return;
      }

      suggestionsLen = this.suggestions.length;
      li = [].slice.call(this.completionUL.querySelectorAll('li'));
      liLen = li.length;

      // Update or create necessary elements
      for (i = 0; i < suggestionsLen; i++) {
        if (i < liLen) {
          currentLi = li[i];
        } else {
          currentLi = document.createElement('li');
          currentLi.setAttribute('data-index', i);
          this.completionUL.appendChild(currentLi);
          currentLi.addEventListener('click', this.onCompletionMouseClick);
          currentLi.addEventListener('mousedown', this.onCompletionMouseDown);
          currentLi.addEventListener('mouseout', this.onCompletionMouseOut);
          currentLi.addEventListener('mouseover', this.onCompletionMouseOver);
        }
        currentLi.innerHTML = this.highlight(
            this.suggestions[i].text,
            this.prefix);
        if (i === this.selected) {
          currentLi.className = 'active';
          currentLiRect = currentLi.getBoundingClientRect();
          completionRect = this.completionUL.getBoundingClientRect();
          if (currentLiRect.bottom > completionRect.bottom) {
            this.completionUL.scrollTop = this.completionUL.scrollTop + 2 +
                (currentLiRect.bottom - completionRect.bottom);
          } else if (currentLiRect.top < completionRect.top) {
            this.completionUL.scrollTop = this.completionUL.scrollTop - 2 -
                (completionRect.top - currentLiRect.top);
          }
        } else {
          currentLi.className = '';
        }
      }
      // Remove redundant elements
      while (liLen > suggestionsLen) {
        liLen--;
        li[liLen].removeEventListener('click', this.onCompletionMouseClick);
        li[liLen].removeEventListener('mousedown', this.onCompletionMouseDown);
        li[liLen].removeEventListener('mouseout', this.onCompletionMouseOut);
        li[liLen].removeEventListener('mouseover', this.onCompletionMouseOver);
        this.completionUL.removeChild(li[liLen]);
      }

      inputRect = this.textarea.getBoundingClientRect();
      this.completion.style.top = window.pageYOffset + inputRect.top +
          inputRect.height + 'px';
      this.completion.style.left = inputRect.left + 'px';
      this.completion.style.display = 'block';
    },

    resolveName: function (name) {
      // Walk through introspection definitions and get target model and field
      var f;
      var i;
      var l;
      var nameParts = name.split('.');
      var model = this.currentModel;
      var field = null;

      if (model) {
        for (i = 0, l = nameParts.length; i < l; i++) {
          f = this.models[model][nameParts[i]];
          if (!f) {
            model = null;
            field = null;
            break;
          } else if (f.type === 'relation') {
            model = f.relation;
            field = null;
          } else {
            field = nameParts[i];
          }
        }
      }
      return { model: model, field: field };
    },

    getContext: function (text, cursorPos) {
      // This function returns an object with the following 4 properties:
      var prefix;        // text already entered by user in the current scope
      var scope = null;  // 'field', 'comparison', 'value', 'logical' or null
      var model = null;  // model, set for 'field', 'comparison' and 'value'
      var field = null;  // field, set for 'comparison' and 'value'

      var whitespace;
      var nameParts;
      var resolvedName;
      var lastToken = null;
      var nextToLastToken = null;
      var tokens = this.lexer.setInput(text.slice(0, cursorPos)).lexAll();
      if (tokens.length && tokens[tokens.length - 1].end >= cursorPos) {
        // if cursor is positioned on the last token then remove it.
        // We are only interested in tokens preceding current.
        tokens.pop();
      }
      if (tokens.length) {
        lastToken = tokens[tokens.length - 1];
        if (tokens.length > 1) {
          nextToLastToken = tokens[tokens.length - 2];
        }
      }

      // Current token which is currently being typed may be not complete yet,
      // so lexer may fail to recognize it correctly. So we define current token
      // prefix as a string without whitespace positioned after previous token
      // and until current cursor position.
      prefix = text.slice(lastToken ? lastToken.end : 0, cursorPos);
      whitespace = prefix.match(whitespaceRegex);
      if (whitespace) {
        prefix = prefix.slice(whitespace[0].length);
      }
      if (prefix === '(') {
        // Paren should not be a part of suggestion
        prefix = '';
      }

      if (prefix === ')' && !whitespace) {
        // Nothing to suggest right after right paren
      } else if (!lastToken ||
          (['AND', 'OR'].indexOf(lastToken.name) >= 0 && whitespace) ||
          (prefix === '.' && lastToken && !whitespace) ||
          (lastToken.name === 'PAREN_L' && (!nextToLastToken ||
              ['AND', 'OR'].indexOf(nextToLastToken.name) >= 0))) {
        scope = 'field';
        model = this.currentModel;
        if (prefix === '.') {
          prefix = text.slice(lastToken.start, cursorPos);
        }
        nameParts = prefix.split('.');
        if (nameParts.length > 1) {
          // use last part as a prefix, analyze preceding parts to get the model
          prefix = nameParts.pop();
          resolvedName = this.resolveName(nameParts.join('.'));
          if (resolvedName.model && !resolvedName.field) {
            model = resolvedName.model;
          } else {
            // if resolvedName.model is null that means that model wasn't found.
            // if resolvedName.field is NOT null that means that the name
            // preceding current prefix is a concrete field and not a relation,
            // and therefore it can't have any properties.
            scope = null;
            model = null;
          }
        }
      } else if (lastToken && whitespace &&
          nextToLastToken && nextToLastToken.name === 'NAME' &&
          ['EQUALS', 'NOT_EQUALS', 'CONTAINS', 'NOT_CONTAINS', 'GREATER_EQUAL',
            'GREATER', 'LESS_EQUAL', 'LESS'].indexOf(lastToken.name) >= 0) {
        resolvedName = this.resolveName(nextToLastToken.value);
        if (resolvedName.model) {
          scope = 'value';
          model = resolvedName.model;
          field = resolvedName.field;
          if (prefix[0] === '"' && this.models[model][field].type === 'str') {
            prefix = prefix.slice(1);
          }
        }
      } else if (lastToken && whitespace && lastToken.name === 'NAME') {
        resolvedName = this.resolveName(lastToken.value);
        if (resolvedName.model) {
          scope = 'comparison';
          model = resolvedName.model;
          field = resolvedName.field;
        }
      } else if (lastToken && whitespace &&
          ['PAREN_R', 'INT_VALUE', 'FLOAT_VALUE', 'STRING_VALUE']
              .indexOf(lastToken.name) >= 0) {
        scope = 'logical';
      }
      return { prefix: prefix, scope: scope, model: model, field: field };
    },

    generateSuggestions: function () {
      var input = this.textarea;
      var context;
      var model;
      var field;
      var suggestions;
      var snippetBefore;
      var snippetAfter;
      var searchFilter;
      var textBefore;
      var textAfter;

      if (!this.currentModel) {
        // Introspections are not loaded yet
        return;
      }
      if (input.selectionStart !== input.selectionEnd) {
        // We shouldn't show suggestions when something is selected
        this.prefix = '';
        this.suggestions = [];
        return;
      }

      // default search filter - find anywhere in the string, case-sensitive
      searchFilter = function (item) {
        return item.text.indexOf(this.prefix) >= 0;
      }.bind(this);
      // default highlight mode - case sensitive
      this.highlightCaseSensitive = true;

      context = this.getContext(input.value, input.selectionStart);
      this.prefix = context.prefix;
      model = this.models[context.model];
      field = context.field && model[context.field];

      textBefore = input.value.slice(
          0, input.selectionStart - this.prefix.length);
      textAfter = input.value.slice(input.selectionStart);

      switch (context.scope) {
        case 'field':
          this.suggestions = Object.keys(model).map(function (f) {
            return suggestion(f, '', model[f].type === 'relation' ? '.' : ' ');
          });
          break;

        case 'comparison':
          suggestions = ['=', '!='];
          snippetAfter = ' ';
          if (field && field.type !== 'bool') {
            if (field.type === 'str') {
              suggestions.push('~');
              suggestions.push('!~');
              snippetAfter = ' "|"';
            } else if (field.type === 'date' || field.type === 'datetime') {
              snippetAfter = ' "|"';
            }
            Array.prototype.push.apply(suggestions, ['>', '>=', '<', '<=']);
          }
          this.suggestions = suggestions.map(function (s) {
            return suggestion(s, '', snippetAfter);
          });
          if (field && field.type !== 'bool') {
            if (['str', 'date', 'datetime'].indexOf(field.type) >= 0) {
              snippetAfter = ' ("|")';
            } else {
              snippetAfter = ' (|)';
            }
            this.suggestions.push(suggestion('in', '', snippetAfter));
            this.suggestions.push(suggestion('not in', '', snippetAfter));
          }
          // use "starts with" search filter instead of default
          searchFilter = function (item) {
            // See http://stackoverflow.com/a/4579228
            return item.text.lastIndexOf(this.prefix, 0) === 0;
          }.bind(this);
          break;

        case 'value':
          if (field.type === 'str') {
            if (textBefore && textBefore[textBefore.length - 1] === '"') {
              snippetBefore = '';
            } else {
              snippetBefore = '"';
            }
            if (textAfter[0] !== '"') {
              snippetAfter = '" ';
            } else {
              snippetAfter = '';
            }
            if (!this.valuesCaseSensitive) {
              searchFilter = function (item) {
                // Case-insensitive
                return item.text.toLowerCase()
                        .indexOf(this.prefix.toLowerCase()) >= 0;
              }.bind(this);
            }
            this.highlightCaseSensitive = this.valuesCaseSensitive;
            this.suggestions = field.options.map(function (f) {
              return suggestion(f, snippetBefore, snippetAfter);
            });
          } else if (field.type === 'bool') {
            this.suggestions = [
              suggestion('True', '', ' '),
              suggestion('False', '', ' ')
            ];
            if (field.nullable) {
              this.suggestions.push(suggestion('None', '', ' '));
            }
          }
          break;

        case 'logical':
          this.suggestions = [
            suggestion('and', '', ' '),
            suggestion('or', '', ' ')
          ];
          break;

        default:
          this.prefix = '';
          this.suggestions = [];
      }
      this.suggestions = this.suggestions.filter(searchFilter);
      if (this.suggestions.length === 1) {
        this.selected = 0;  // auto-select the only suggested item
      } else {
        this.selected = null;
      }
    }

  };
}));
