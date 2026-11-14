(function (root) {
  var state = null;

  function injectStyle() {
    if (document.getElementById('mc325-chart-trading-style')) return;
    var style = document.createElement('style');
    style.id = 'mc325-chart-trading-style';
    style.textContent = ''
      + '.mc325-chart-overlay{position:absolute;inset:0;z-index:10;pointer-events:none;}'
      + '#mc325OrderTicket{z-index:1000;}'
      + '#mc325TradingToolbar button{cursor:pointer;}';
    document.head.appendChild(style);
  }

  function symbolOf(id, node) {
    var card = node.closest ? node.closest('.panel, .chart-card') : null;
    var label = card && card.querySelector('.chart-contract-label');
    var text = label && label.textContent ? label.textContent.trim() : '';
    if (text) return text;
    if (node.dataset && node.dataset.mc325Symbol) return node.dataset.mc325Symbol;
    return id || '';
  }

  function focusedSymbol() {
    var selected = document.querySelector('.panel.kite-chart-selected .chart, .chart-card.kite-chart-selected .chart-pane, .panel.kite-chart-selected, .chart-card.kite-chart-selected');
    if (selected) {
      if (selected.dataset && selected.dataset.mc325Symbol) return selected.dataset.mc325Symbol;
      var chart = selected.querySelector ? selected.querySelector('.chart, .chart-pane') : null;
      if (chart && chart.dataset && chart.dataset.mc325Symbol) return chart.dataset.mc325Symbol;
    }
    return 'CE';
  }

  function collectSlots() {
    var slots = [];
    var seen = [];
    function add(id, node, slot) {
      if (!node || seen.indexOf(node) >= 0) return;
      seen.push(node);
      var symbol = symbolOf(id, node);
      if (node.dataset) node.dataset.mc325Symbol = symbol;
      slots.push({ id: id, node: node, slot: slot, symbol: symbol });
    }
    if (root.mc325Charts) {
      Object.keys(root.mc325Charts).forEach(function (id) {
        add(id, document.getElementById('chart' + id), root.mc325Charts[id]);
      });
    }
    if (root.shivMultiPanes) {
      Object.keys(root.shivMultiPanes).forEach(function (key) {
        var pane = root.shivMultiPanes[key];
        if (!pane) return;
        var node = pane.card && pane.card.querySelector ? pane.card.querySelector('.chart-pane') : null;
        add(key, node, pane);
      });
    }
    return slots;
  }

  function httpBase() {
    if (root.MC325_TRADING_HTTP) return String(root.MC325_TRADING_HTTP).replace(/\/$/, '');
    var script = document.querySelector('script[src*="/mc325/trading/mount.js"]');
    if (script && script.src) {
      try { return new URL(script.src).origin; } catch (err) {}
    }
    return 'http://127.0.0.1:6161';
  }

  function mountMc325DirectChartTrading() {
    if (typeof document === 'undefined') return;
    if (!root.Mc325WsClient || !root.Mc325UseOrders || !root.Mc325ChartTradingOverlay || !root.Mc325OrderTicket || !root.Mc325TradingToolbar) return;
    if (state) {
      state.refresh();
      return;
    }
    state = { refresh: function () {} };
    injectStyle();
    var userId = 'paper';
    try { userId = localStorage.getItem('mc325PaperUser') || 'paper'; } catch (err) {}
    var base = httpBase();
    fetch(base + '/api/session', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ userId: userId })
    }).then(function (res) {
      if (!res.ok) throw new Error('session');
      return res.json();
    }).then(function (session) {
      var wsUrl = root.MC325_TRADING_WS || 'ws://127.0.0.1:6162/ws';
      var client = root.Mc325WsClient.createWsClient({
        url: wsUrl,
        getToken: function () { return session.token; }
      });
      var book = root.Mc325UseOrders.createOrderBook(client, {
        tickSize: session.tickSize,
        lotSize: session.lotSize
      });
      var lines = root.Mc325TradingToolbar.createLineVisibility(true);
      var ticket = root.Mc325OrderTicket.mountOrderTicket({
        host: document.body,
        book: book,
        accountId: session.accountId,
        symbol: focusedSymbol(),
        side: 'BUY'
      });
      var bar = document.getElementById('kiteBarRight') || document.body;
      root.Mc325TradingToolbar.mountTradingToolbar({
        host: bar,
        book: book,
        ticket: ticket,
        lines: lines,
        focusedSymbol: focusedSymbol
      });
      function refresh() {
        collectSlots().forEach(function (slot) {
          if (slot.node.querySelector('.mc325-chart-overlay')) return;
          root.Mc325ChartTradingOverlay.mountChartTradingOverlay({
            host: slot.node,
            book: book,
            symbol: slot.symbol,
            getSymbol: function () { return slot.node.dataset.mc325Symbol || slot.symbol; },
            getSeries: function () { return slot.slot; },
            getTickSize: function () { return book.getState().tickSize || session.tickSize || 0.01; },
            linesVisible: function () { return lines.isVisible(); }
          });
        });
      }
      state.refresh = refresh;
      refresh();
      root.addEventListener('mc325-chart-loaded', refresh);
      lines.subscribe(function () { refresh(); });
      var chartsRoot = document.getElementById('kiteCharts') || document.getElementById('charts');
      if (chartsRoot && root.MutationObserver) {
        new MutationObserver(function () { refresh(); }).observe(chartsRoot, { childList: true, subtree: true });
      }
      client.connect();
    }).catch(function () {});
  }

  root.mountMc325DirectChartTrading = mountMc325DirectChartTrading;
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', mountMc325DirectChartTrading);
    } else {
      mountMc325DirectChartTrading();
    }
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
