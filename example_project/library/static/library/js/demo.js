/* Showcase glue for the overlay demo page. Wires the library primitives
 * (multiline.js, highlight.js) to the demo API (format / explain / search).
 * Nothing here is part of DjangoQL — it is how *this* app chooses to use it. */
(function () {
  'use strict';

  var textarea = document.getElementById('q');
  var form = document.getElementById('search-form');
  var errorEl = document.getElementById('error');
  var resultsBody = document.querySelector('#results tbody');
  var resultCount = document.getElementById('result-count');
  var explainPanel = document.getElementById('explain-panel');
  var explainTree = document.getElementById('explain-tree');

  // Attach the highlight overlay here so we keep its handle and can mark the
  // syntax-error location returned by the API.
  var overlay = window.DjangoQLHighlight
    ? DjangoQLHighlight.attachOverlay(textarea)
    : null;

  // --- Anchor the suggestion popup at the caret --------------------------
  // The bundled widget positions its popup at the textarea's bottom-left; with
  // this demo's tall multi-line box that lands far below the caret. Re-anchor
  // it just under the caret. Scoped to this page — the admin doesn't load this
  // script, so its (single-line) box keeps the default placement.
  var MIRROR_PROPS = [
    'boxSizing', 'width', 'paddingTop', 'paddingRight', 'paddingBottom',
    'paddingLeft', 'borderTopWidth', 'borderRightWidth', 'borderBottomWidth',
    'borderLeftWidth', 'fontStyle', 'fontVariant', 'fontWeight', 'fontStretch',
    'fontSize', 'lineHeight', 'fontFamily', 'textAlign', 'textTransform',
    'textIndent', 'letterSpacing', 'wordSpacing', 'tabSize'
  ];

  function caretCoordinates(el) {
    var cs = window.getComputedStyle(el);
    var mirror = document.createElement('div');
    var s = mirror.style;
    s.position = 'absolute';
    s.visibility = 'hidden';
    s.whiteSpace = 'pre-wrap';
    s.overflowWrap = 'break-word';
    s.overflow = 'hidden';
    for (var i = 0; i < MIRROR_PROPS.length; i++) {
      s[MIRROR_PROPS[i]] = cs[MIRROR_PROPS[i]];
    }
    var rect = el.getBoundingClientRect();
    s.left = (window.pageXOffset + rect.left) + 'px';
    s.top = (window.pageYOffset + rect.top) + 'px';
    mirror.textContent = el.value.slice(0, el.selectionStart);
    var marker = document.createElement('span');
    marker.textContent = el.value.slice(el.selectionStart) || '.';
    mirror.appendChild(marker);
    document.body.appendChild(mirror);
    // offsetLeft/Top are measured from the mirror's padding edge, so add the
    // textarea's border widths back to get the caret relative to its outer box.
    var bl = parseFloat(cs.borderLeftWidth) || 0;
    var bt = parseFloat(cs.borderTopWidth) || 0;
    var x = window.pageXOffset + rect.left + bl + marker.offsetLeft - el.scrollLeft;
    var y = window.pageYOffset + rect.top + bt + marker.offsetTop - el.scrollTop;
    var lineHeight = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.4;
    document.body.removeChild(mirror);
    return { x: x, y: y, lineHeight: lineHeight };
  }

  function positionPopupAtCaret(ta, popup) {
    if (!ta || !popup) { return; }
    var c = caretCoordinates(ta);
    var left = c.x + 2;  // a hair right of the caret
    var docEl = document.documentElement;
    var maxLeft = window.pageXOffset + docEl.clientWidth - popup.offsetWidth - 8;
    if (left > maxLeft) { left = Math.max(window.pageXOffset + 8, maxLeft); }
    popup.style.left = left + 'px';
    popup.style.top = (c.y + c.lineHeight) + 'px';
  }

  if (window.DjangoQL && DjangoQL.prototype && !DjangoQL.prototype._demoCaret) {
    var _renderCompletion = DjangoQL.prototype.renderCompletion;
    DjangoQL.prototype.renderCompletion = function () {
      _renderCompletion.apply(this, arguments);
      if (this.completion && this.completion.style.display === 'block') {
        positionPopupAtCaret(this.textarea, this.completion);
      }
    };
    DjangoQL.prototype._demoCaret = true;
  }

  function clearError() {
    errorEl.hidden = true;
    if (overlay) { overlay.clearError(); }
  }

  // Show the message and, when the API reports a (line, column), mark that
  // spot in the query box.
  function showError(data) {
    var msg = (data && data.error) || 'Query error';
    errorEl.textContent = msg;
    errorEl.hidden = false;
    if (overlay && data && data.line && data.column) {
      if (data.mark === 'token') {
        // Unknown field etc.: flag just that token.
        overlay.setErrorAt(data.line, data.column);
      } else {
        // Syntax error: paint the whole broken tail from the error column.
        overlay.setErrorFrom(data.line, data.column);
      }
    }
  }

  function post(url) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ q: textarea.value }),
    }).then(function (r) {
      return r.json().then(function (data) {
        return { ok: r.ok, data: data };
      });
    });
  }

  function repaintOverlay() {
    // highlight.js listens for 'input' to repaint its backdrop.
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function run() {
    clearError();
    post('/api/search/').then(function (res) {
      if (!res.ok) { showError(res.data); return; }
      resultCount.textContent =
        'showing ' + res.data.shown + ' of ' + res.data.total;
      resultsBody.innerHTML = '';
      res.data.rows.forEach(function (row) {
        var tr = document.createElement('tr');
        [row.title, row.author, row.publisher, row.year,
          row.rating, row.price, row.in_stock ? '✓' : '—'
        ].forEach(function (v) {
          var td = document.createElement('td');
          td.textContent = v;
          tr.appendChild(td);
        });
        resultsBody.appendChild(tr);
      });
      // When a valid query matches nothing, auto-open the per-branch breakdown
      // so it's obvious *where* the zero comes from.
      if (res.data.total === 0 && textarea.value.trim()) {
        explain();
      } else {
        explainPanel.hidden = true;
      }
    });
  }

  function format() {
    clearError();
    post('/api/format/').then(function (res) {
      if (!res.ok) { showError(res.data); return; }
      if (res.data.formatted) {
        textarea.value = res.data.formatted;
        textarea.rows = Math.max(3, res.data.formatted.split('\n').length);
        repaintOverlay();
      }
    });
  }

  function renderNode(node) {
    var li = document.createElement('li');
    li.className = 'node role-' + node.role;
    li.title = node.count + ' row(s) match this sub-expression';
    var label = document.createElement('span');
    label.className = 'node-label';
    // Syntax-highlight the sub-expression with the same tokenizer/palette as the
    // query box. renderHtml is XSS-safe (it HTML-escapes every token value).
    if (window.DjangoQLHighlight) {
      label.innerHTML = DjangoQLHighlight.renderHtml(node.text);
    } else {
      label.textContent = node.text;
    }
    var count = document.createElement('span');
    count.className = 'node-count';
    count.textContent = node.count;
    li.appendChild(count);
    li.appendChild(label);
    if (node.children && node.children.length) {
      var ul = document.createElement('ul');
      node.children.forEach(function (child) {
        ul.appendChild(renderNode(child));
      });
      li.appendChild(ul);
    }
    return li;
  }

  function explain() {
    clearError();
    post('/api/explain/').then(function (res) {
      if (!res.ok) { showError(res.data); return; }
      explainTree.innerHTML = '';
      if (!res.data.tree) { explainPanel.hidden = true; return; }
      var ul = document.createElement('ul');
      ul.className = 'tree';
      ul.appendChild(renderNode(res.data.tree));
      explainTree.appendChild(ul);
      explainPanel.hidden = false;
    });
  }

  form.addEventListener('submit', function (e) { e.preventDefault(); run(); });
  document.getElementById('btn-format').addEventListener('click', format);
  document.getElementById('btn-explain').addEventListener('click', explain);

  Array.prototype.forEach.call(
    document.querySelectorAll('.example'),
    function (btn) {
      btn.addEventListener('click', function () {
        textarea.value = btn.dataset.q;
        repaintOverlay();
        run();
      });
    }
  );
}());
