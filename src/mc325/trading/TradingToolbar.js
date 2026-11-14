(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.Mc325TradingToolbar = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function createLineVisibility(initial) {
    var visible = initial !== false;
    var listeners = [];
    return {
      isVisible: function () { return visible; },
      toggle: function () {
        visible = !visible;
        listeners.forEach(function (fn) { fn(visible); });
        return visible;
      },
      subscribe: function (fn) {
        listeners.push(fn);
        return function () {
          listeners = listeners.filter(function (item) { return item !== fn; });
        };
      }
    };
  }

  function button(label) {
    var node = document.createElement('button');
    node.type = 'button';
    node.textContent = label;
    node.style.height = '28px';
    node.style.padding = '0 8px';
    node.style.font = '12px/1 sans-serif';
    node.style.fontWeight = '700';
    node.style.border = '1px solid #c5ced8';
    node.style.borderRadius = '2px';
    node.style.background = '#fff';
    node.style.color = '#243348';
    return node;
  }

  function mountTradingToolbar(options) {
    var opts = options || {};
    var book = opts.book;
    var ticket = opts.ticket;
    var lines = opts.lines || createLineVisibility(true);
    var focusedSymbol = opts.focusedSymbol || function () { return ''; };
    var host = opts.host || document.body;
    var rootNode = document.createElement('div');
    rootNode.id = 'mc325TradingToolbar';
    rootNode.className = 'mc325-trading-toolbar';
    rootNode.setAttribute('aria-label', 'Chart trading');
    rootNode.style.display = 'flex';
    rootNode.style.gap = '4px';
    rootNode.style.alignItems = 'center';
    if (host === document.body) {
      rootNode.style.position = 'fixed';
      rootNode.style.top = '8px';
      rootNode.style.left = '8px';
      rootNode.style.zIndex = '20';
    }

    var buy = button('Buy');
    buy.style.color = '#067044';
    var sell = button('Sell');
    sell.style.color = '#B8293E';
    var linesBtn = button('Lines on');
    linesBtn.setAttribute('aria-pressed', 'true');
    var cancel = button('Cancel all');
    var status = document.createElement('span');
    status.className = 'mc325-trading-status';
    status.textContent = book.getState().status || 'offline';
    status.style.font = '11px/1 sans-serif';
    status.style.padding = '0 4px';

    buy.addEventListener('click', function () {
      ticket.setSide('BUY');
      ticket.setSymbol(focusedSymbol());
      if (ticket.focus) ticket.focus();
    });
    sell.addEventListener('click', function () {
      ticket.setSide('SELL');
      ticket.setSymbol(focusedSymbol());
      if (ticket.focus) ticket.focus();
    });
    linesBtn.addEventListener('click', function () {
      var on = lines.toggle();
      linesBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
      linesBtn.textContent = on ? 'Lines on' : 'Lines off';
    });
    cancel.addEventListener('click', function () {
      if (typeof window.confirm === 'function' && !window.confirm('Cancel all open paper orders?')) return;
      book.cancelAll();
    });

    if (book.subscribe) {
      book.subscribe(function (state) {
        status.textContent = state.status || 'offline';
      });
    }

    rootNode.appendChild(buy);
    rootNode.appendChild(sell);
    rootNode.appendChild(linesBtn);
    rootNode.appendChild(cancel);
    rootNode.appendChild(status);
    host.appendChild(rootNode);
    return { element: rootNode, lines: lines };
  }

  return {
    createLineVisibility: createLineVisibility,
    mountTradingToolbar: mountTradingToolbar
  };
});
