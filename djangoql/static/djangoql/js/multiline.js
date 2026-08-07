/*
 * djangoql multiline support — Shift+Enter inserts a newline.
 *
 * The bundled completion widget binds Enter to submit the search form. This
 * small, framework-agnostic helper lets users build multi-line queries:
 *
 *   - Shift+Enter -> insert a newline at the caret (no submit)
 *   - Enter       -> left untouched (the widget/form submits as before)
 *
 * It works by delegating a *capture-phase* keydown listener on `document`, so
 * it runs before the widget's own (bubble-phase) handler and can stop the
 * event from ever reaching it. This also means it does not care when or how the
 * target textarea was created.
 *
 * It targets any textarea matching `DjangoQLMultiline.selector` (by default the
 * admin search box `textarea[name="q"]`, plus the generic opt-in hooks
 * `textarea.djangoql` and `textarea[data-djangoql]`). Integrators using their
 * own front-end can either add one of those hooks to their textarea or call
 * `DjangoQLMultiline.enable(textarea)` explicitly.
 *
 * This file is a library primitive: it imposes no styling and no editor. How
 * the multi-line query looks and behaves beyond newline insertion is the
 * integrator's decision.
 */
(function (window, document) {
  'use strict';

  var DjangoQLMultiline = {
    // Elements matching this selector get Shift+Enter newline behaviour.
    // Override before DOM is interacted with, or use enable() per element.
    selector: 'textarea[name="q"], textarea.djangoql, textarea[data-djangoql]',

    // Explicitly opt a textarea in (useful when it does not match selector).
    enable: function (textarea) {
      if (textarea && textarea.setAttribute) {
        textarea.setAttribute('data-djangoql', '');
      }
    },

    // Insert `text` at the current caret position of `textarea`, replacing any
    // current selection, then place the caret right after the inserted text.
    insertAtCaret: function (textarea, text) {
      var start = textarea.selectionStart;
      var end = textarea.selectionEnd;
      var value = textarea.value;
      textarea.value = value.slice(0, start) + text + value.slice(end);
      var caret = start + text.length;
      textarea.selectionStart = caret;
      textarea.selectionEnd = caret;
      // Let listeners (e.g. the widget's auto-resize) react to the change.
      if (typeof window.Event === 'function') {
        textarea.dispatchEvent(new window.Event('input', { bubbles: true }));
      } else if (document.createEvent) {
        // Legacy browsers (IE): construct the event the old way.
        var evt = document.createEvent('Event');
        evt.initEvent('input', true, false);
        textarea.dispatchEvent(evt);
      }
    },

    matches: function (el) {
      if (!el || el.tagName !== 'TEXTAREA') {
        return false;
      }
      var fn = el.matches || el.msMatchesSelector || el.webkitMatchesSelector;
      return fn ? fn.call(el, DjangoQLMultiline.selector) : false;
    },

    onKeydown: function (e) {
      // Only Shift+Enter, and never while an IME composition is in progress.
      if (e.key !== 'Enter' && e.keyCode !== 13) {
        return;
      }
      if (!e.shiftKey || e.isComposing || e.keyCode === 229) {
        return;
      }
      if (!DjangoQLMultiline.matches(e.target)) {
        return;
      }
      e.preventDefault();
      // Block the widget's own keydown handler from submitting the form.
      e.stopImmediatePropagation();
      DjangoQLMultiline.insertAtCaret(e.target, '\n');
    },
  };

  // Capture phase: run before the widget's bubble-phase keydown handler.
  document.addEventListener('keydown', DjangoQLMultiline.onKeydown, true);

  window.DjangoQLMultiline = DjangoQLMultiline;
}(window, document));
