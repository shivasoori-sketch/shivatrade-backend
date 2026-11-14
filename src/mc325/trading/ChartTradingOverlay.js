(function (root, factory) {
  var api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.Mc325ChartTradingOverlay = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
  function ordersApi() {
    if (typeof require === 'function') return require('./useOrders');
    return root.Mc325UseOrders;
  }

  function sampleDragPrice(pointerPrice, lockedPrice) {
    if (lockedPrice != null && lockedPrice !== '' && Number.isFinite(Number(lockedPrice))) {
      return Number(lockedPrice);
    }
    return pointerPrice;
  }

  function finishDrag(rawPrice, tickSize, originPrice) {
    var decision = ordersApi().resolveDragPrice(rawPrice, tickSize, originPrice);
    if (!decision.ok) {
      return { action: 'snapback', price: decision.price, reason: decision.reason };
    }
    if (Number(decision.price) === Number(originPrice)) {
      return { action: 'snapback', price: decision.price, reason: 'unchanged' };
    }
    return { action: 'modify', price: decision.price };
  }

  function lineSpecs(order) {
    if (!order || order.status !== 'OPEN') return [];
    var specs = [];
    if (order.price > 0 && (order.type === 'LIMIT' || order.type === 'SL' || order.type === 'TP')) {
      specs.push({
        field: 'price',
        price: order.price,
        kind: order.type === 'LIMIT' ? 'entry' : String(order.type).toLowerCase(),
        side: order.side
      });
    }
    if (order.stopPrice > 0) specs.push({ field: 'stopPrice', price: order.stopPrice, kind: 'sl', side: order.side });
    if (order.targetPrice > 0) specs.push({ field: 'targetPrice', price: order.targetPrice, kind: 'tp', side: order.side });
    return specs;
  }

  function lineColor(spec) {
    if (spec.kind === 'sl') return '#B8293E';
    if (spec.kind === 'tp') return '#067044';
    return spec.side === 'SELL' ? '#B8293E' : '#067044';
  }

  function lineTitle(spec) {
    var name = spec.kind === 'entry' ? spec.side : spec.kind.toUpperCase();
    return name + ' ' + spec.price;
  }

  function mountChartTradingOverlay(options) {
    var opts = options || {};
    var host = opts.host;
    var book = opts.book;
    var getSeries = opts.getSeries || function () { return null; };
    var getSymbol = opts.getSymbol || function () { return opts.symbol || ''; };
    var getTickSize = opts.getTickSize || function () { return (book.getState && book.getState().tickSize) || 0.01; };
    var linesVisible = opts.linesVisible || function () { return true; };
    var api = ordersApi();

    host.style.setProperty('z-index', '0', 'important');
    if (typeof getComputedStyle === 'function' && getComputedStyle(host).position === 'static') {
      host.style.setProperty('position', 'relative', 'important');
    } else if (!host.style.position) {
      host.style.setProperty('position', 'relative', 'important');
    }

    var overlay = document.createElement('div');
    overlay.className = 'mc325-chart-overlay';
    overlay.style.position = 'absolute';
    overlay.style.left = '0';
    overlay.style.right = '0';
    overlay.style.top = '0';
    overlay.style.bottom = '0';
    overlay.style.pointerEvents = 'none';
    overlay.style.setProperty('z-index', '10', 'important');
    host.appendChild(overlay);

    var dragging = null;
    var stopped = false;
    var raf = 0;

    function series() {
      var value = getSeries();
      if (!value) return null;
      return value.series || value;
    }

    function priceToY(price) {
      var current = series();
      if (!current || typeof current.priceToCoordinate !== 'function') return null;
      var y = current.priceToCoordinate(price);
      if (y == null || !Number.isFinite(Number(y))) return null;
      return Number(y);
    }

    function yToPrice(y) {
      var current = series();
      if (!current || typeof current.coordinateToPrice !== 'function') return null;
      var price = current.coordinateToPrice(y);
      return Number.isFinite(Number(price)) ? Number(price) : null;
    }

    function pointerY(event) {
      var rect = overlay.getBoundingClientRect();
      return event.clientY - rect.top;
    }

    function paintNode(node, spec) {
      node.dataset.origin = String(spec.price);
      node.dataset.field = spec.field;
      var label = node.querySelector('.mc325-line-label');
      if (label) label.textContent = lineTitle(spec);
      var bar = node.querySelector('.mc325-line-bar');
      var color = lineColor(spec);
      if (bar) bar.style.borderTopColor = color;
      if (label) label.style.color = color;
    }

    function createLine(key, spec, order) {
      var node = document.createElement('div');
      node.className = 'mc325-order-line';
      node.dataset.key = key;
      node.dataset.orderId = order.id;
      node.dataset.field = spec.field;
      node.style.position = 'absolute';
      node.style.left = '0';
      node.style.right = '72px';
      node.style.height = '16px';
      node.style.marginTop = '-8px';
      node.style.cursor = 'ns-resize';
      node.style.pointerEvents = 'auto';
      node.style.zIndex = '10';
      var bar = document.createElement('span');
      bar.className = 'mc325-line-bar';
      bar.style.position = 'absolute';
      bar.style.left = '0';
      bar.style.right = '0';
      bar.style.top = '7px';
      bar.style.borderTop = '1px dashed ' + lineColor(spec);
      bar.style.pointerEvents = 'none';
      var label = document.createElement('span');
      label.className = 'mc325-line-label';
      label.style.position = 'relative';
      label.style.font = '11px/16px sans-serif';
      label.style.background = 'rgba(255,255,255,.88)';
      label.style.padding = '0 4px';
      label.style.pointerEvents = 'none';
      node.appendChild(label);
      node.appendChild(bar);
      paintNode(node, spec);
      node.addEventListener('pointerdown', function (event) {
        if (event.button != null && event.button !== 0) return;
        event.preventDefault();
        event.stopPropagation();
        dragging = {
          key: key,
          id: order.id,
          field: spec.field,
          origin: Number(node.dataset.origin),
          node: node
        };
        node.dataset.locked = '';
        try {
          if (node.setPointerCapture && event.pointerId != null) node.setPointerCapture(event.pointerId);
        } catch (err) {}
      });
      overlay.appendChild(node);
      return node;
    }

    function render() {
      if (stopped) return;
      var show = linesVisible() !== false;
      overlay.style.display = show ? 'block' : 'none';
      if (!show) return;
      var symbol = getSymbol();
      var orders = (book.getState().orders || []).filter(function (order) { return order.symbol === symbol; });
      var live = {};
      orders.forEach(function (order) {
        lineSpecs(order).forEach(function (spec) {
          var key = order.id + ':' + spec.field;
          live[key] = true;
          var node = overlay.querySelector('[data-key="' + key + '"]');
          if (!node) node = createLine(key, spec, order);
          paintNode(node, spec);
          if (dragging && dragging.key === key) return;
          var y = priceToY(spec.price);
          if (y == null) {
            node.style.display = 'none';
            return;
          }
          node.style.display = 'block';
          node.style.top = y + 'px';
        });
      });
      Array.prototype.forEach.call(overlay.querySelectorAll('.mc325-order-line'), function (node) {
        if (!live[node.dataset.key]) node.remove();
      });
    }

    function moveDrag(event) {
      if (!dragging) return;
      if (event.cancelable) event.preventDefault();
      var raw = yToPrice(pointerY(event));
      var near = api.nearestTick(raw, getTickSize());
      if (near == null) {
        dragging.node.dataset.locked = '';
        return;
      }
      dragging.node.dataset.locked = String(near);
      var y = priceToY(near);
      if (y == null) return;
      dragging.node.style.display = 'block';
      dragging.node.style.top = y + 'px';
    }

    function endDrag(event) {
      if (!dragging) return;
      var drag = dragging;
      dragging = null;
      var raw = yToPrice(pointerY(event));
      var sample = sampleDragPrice(raw, drag.node.dataset.locked || null);
      drag.node.dataset.locked = '';
      var result = finishDrag(sample, getTickSize(), drag.origin);
      if (result.action !== 'modify') {
        var back = priceToY(drag.origin);
        if (back != null) drag.node.style.top = back + 'px';
        return;
      }
      var patch = {};
      patch[drag.field] = result.price;
      var applied = book.modify(drag.id, patch);
      if (!applied.ok) {
        var revert = priceToY(drag.origin);
        if (revert != null) drag.node.style.top = revert + 'px';
      }
    }

    function onMove(event) { moveDrag(event); }
    function onUp(event) { endDrag(event); }
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);

    var unsub = book.subscribe ? book.subscribe(function () { render(); }) : function () {};

    function loop() {
      if (stopped) return;
      render();
      raf = requestAnimationFrame(loop);
    }
    if (typeof requestAnimationFrame === 'function') raf = requestAnimationFrame(loop);
    else render();

    return {
      render: render,
      destroy: function () {
        stopped = true;
        if (raf && typeof cancelAnimationFrame === 'function') cancelAnimationFrame(raf);
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
        window.removeEventListener('pointercancel', onUp);
        unsub();
        overlay.remove();
      }
    };
  }

  return {
    mountChartTradingOverlay: mountChartTradingOverlay,
    finishDrag: finishDrag,
    sampleDragPrice: sampleDragPrice,
    lineSpecs: lineSpecs
  };
});
