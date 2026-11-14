(function (root, factory) {
  var api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.Mc325UseOrders = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
  function tickDecimals(tickSize) {
    var text = String(tickSize);
    var dot = text.indexOf('.');
    if (dot < 0) return 0;
    return Math.min(8, text.length - dot - 1);
  }

  function normalizePrice(price, tickSize) {
    return Number(Number(price).toFixed(tickDecimals(tickSize)));
  }

  function isOnTick(price, tickSize) {
    if (!Number.isFinite(price) || !(Number(tickSize) > 0)) return false;
    var units = price / Number(tickSize);
    return Math.abs(units - Math.round(units)) < 1e-6;
  }

  function validatePrice(price, tickSize) {
    var n = typeof price === 'string' && price.trim() === '' ? NaN : Number(price);
    if (!Number.isFinite(n) || n <= 0) return { ok: false, reason: 'price_must_be_positive' };
    if (!isOnTick(n, tickSize)) return { ok: false, reason: 'invalid_tick' };
    return { ok: true, price: normalizePrice(n, tickSize) };
  }

  function validateQty(qty, lotSize) {
    var n = Number(qty);
    var lot = Number(lotSize);
    if (!Number.isInteger(n) || n <= 0) return { ok: false, reason: 'qty_must_be_positive_integer' };
    if (!Number.isInteger(lot) || lot <= 0) return { ok: false, reason: 'bad_lot' };
    if (n % lot !== 0) return { ok: false, reason: 'qty_must_match_lot' };
    return { ok: true, qty: n };
  }

  function validateOrderDraft(form, tickSize, lotSize) {
    var errors = [];
    var draft = form || {};
    if (!String(draft.symbol || '').trim()) errors.push('symbol_required');
    if (draft.side !== 'BUY' && draft.side !== 'SELL') errors.push('bad_side');
    if (['MARKET', 'LIMIT', 'SL', 'TP'].indexOf(draft.type) < 0) errors.push('bad_type');
    var qty = validateQty(draft.qty, lotSize);
    if (!qty.ok) errors.push(qty.reason);
    var price = validatePrice(draft.price, tickSize);
    if (!price.ok) errors.push(price.reason);
    if (draft.stopPrice != null && draft.stopPrice !== '') {
      var stop = validatePrice(draft.stopPrice, tickSize);
      if (!stop.ok) errors.push(stop.reason);
    }
    if (draft.targetPrice != null && draft.targetPrice !== '') {
      var target = validatePrice(draft.targetPrice, tickSize);
      if (!target.ok) errors.push(target.reason);
    }
    return errors;
  }

  function nearestTick(price, tickSize) {
    var n = Number(price);
    var tick = Number(tickSize);
    if (!Number.isFinite(n) || !(tick > 0)) return null;
    var rounded = Math.round(n / tick) * tick;
    var checked = validatePrice(rounded, tick);
    return checked.ok ? checked.price : null;
  }

  function resolveDragPrice(rawPrice, tickSize, originPrice) {
    var checked = validatePrice(rawPrice, tickSize);
    var origin = Number(originPrice);
    var fallback = Number.isFinite(origin) ? origin : null;
    if (!checked.ok) {
      return { ok: false, snapback: true, price: fallback, reason: checked.reason };
    }
    return { ok: true, snapback: false, price: checked.price, reason: null };
  }

  function copyOrder(order) {
    var next = {};
    Object.keys(order || {}).forEach(function (key) { next[key] = order[key]; });
    return next;
  }

  function createOrderBook(client, options) {
    var opts = options || {};
    var tickSize = Number(opts.tickSize || 0.01);
    var lotSize = Number(opts.lotSize || 1);
    var state = { orders: [], positions: [], status: 'offline', tickSize: tickSize, lotSize: lotSize, lastReject: null };
    var cached = null;
    var listeners = [];
    var snapshots = new Map();

    function publish() {
      cached = {
        orders: state.orders.map(copyOrder),
        positions: state.positions.map(copyOrder),
        status: state.status,
        tickSize: tickSize,
        lotSize: lotSize,
        lastReject: state.lastReject
      };
      listeners.forEach(function (fn) { fn(cached); });
    }

    function getState() {
      if (!cached) publish();
      return cached;
    }

    function subscribe(fn) {
      listeners.push(fn);
      return function () {
        listeners = listeners.filter(function (item) { return item !== fn; });
      };
    }

    function upsert(order) {
      var clean = copyOrder(order);
      clean.optimistic = false;
      var index = state.orders.findIndex(function (item) { return item.id === clean.id; });
      if (index < 0) state.orders.push(clean);
      else state.orders[index] = clean;
      snapshots.delete(clean.id);
    }

    function restore(id) {
      var prev = snapshots.get(id);
      if (!prev) return;
      var index = state.orders.findIndex(function (item) { return item.id === id; });
      if (index >= 0) state.orders[index] = copyOrder(prev);
      snapshots.delete(id);
    }

    client.on('status', function (status) {
      state.status = status;
      publish();
    });

    client.on('message', function (msg) {
      if (!msg || !msg.type) return;
      if (msg.type === 'auth_ok') {
        if (msg.tickSize) tickSize = Number(msg.tickSize);
        if (msg.lotSize) lotSize = Number(msg.lotSize);
        state.tickSize = tickSize;
        state.lotSize = lotSize;
        publish();
        return;
      }
      if (msg.type === 'orders') {
        state.orders = (msg.orders || []).map(copyOrder);
        snapshots.clear();
        publish();
        return;
      }
      if (msg.type === 'order_update' && msg.order) {
        upsert(msg.order);
        publish();
        return;
      }
      if (msg.type === 'positions') {
        state.positions = (msg.positions || []).map(copyOrder);
        publish();
        return;
      }
      if (msg.type === 'reject') {
        if (msg.action === 'modify_order' && msg.id) restore(msg.id);
        state.lastReject = { action: msg.action || null, id: msg.id || null, clientId: msg.clientId || null, reason: msg.reason || 'rejected' };
        publish();
      }
    });

    function checkedPatch(patch) {
      var next = {};
      if (patch.price != null && patch.price !== '') {
        var price = validatePrice(patch.price, tickSize);
        if (!price.ok) return price;
        next.price = price.price;
      }
      if (patch.stopPrice != null && patch.stopPrice !== '') {
        var stop = validatePrice(patch.stopPrice, tickSize);
        if (!stop.ok) return stop;
        next.stopPrice = stop.price;
      }
      if (patch.targetPrice != null && patch.targetPrice !== '') {
        var target = validatePrice(patch.targetPrice, tickSize);
        if (!target.ok) return target;
        next.targetPrice = target.price;
      }
      if (patch.qty != null && patch.qty !== '') {
        var qty = validateQty(patch.qty, lotSize);
        if (!qty.ok) return qty;
        next.qty = qty.qty;
      }
      if (!Object.keys(next).length) return { ok: false, reason: 'empty_modify' };
      return { ok: true, patch: next };
    }

    function modify(id, patch) {
      var current = state.orders.find(function (order) { return order.id === id; });
      if (!current) return { ok: false, reason: 'not_found', snapback: true };
      if (current.status === 'FILLED') return { ok: false, reason: 'not_filled', snapback: true };
      if (current.status !== 'OPEN') return { ok: false, reason: 'not_open', snapback: true };
      var checked = checkedPatch(patch || {});
      if (!checked.ok) return { ok: false, reason: checked.reason, snapback: true };
      if (!snapshots.has(id)) snapshots.set(id, copyOrder(current));
      var index = state.orders.findIndex(function (order) { return order.id === id; });
      state.orders[index] = Object.assign({}, current, checked.patch, { optimistic: true });
      publish();
      client.send(Object.assign({ type: 'modify_order', id: id, clientId: String(id) }, checked.patch));
      return { ok: true, patch: checked.patch };
    }

    function place(input) {
      var clientId = 'c' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
      client.send({
        type: 'place_order',
        clientId: clientId,
        symbol: input.symbol,
        side: input.side,
        orderType: input.type,
        qty: input.qty,
        price: input.price,
        stopPrice: input.stopPrice,
        targetPrice: input.targetPrice,
        accountId: input.accountId || null
      });
      return { ok: true, clientId: clientId };
    }

    function cancelAll() {
      client.send({ type: 'cancel_all' });
      return { ok: true };
    }

    publish();

    return {
      getState: getState,
      subscribe: subscribe,
      modify: modify,
      place: place,
      cancelAll: cancelAll
    };
  }

  function useOrders(book) {
    var ReactRef = root.React;
    if (!ReactRef || typeof ReactRef.useSyncExternalStore !== 'function') return book.getState();
    return ReactRef.useSyncExternalStore(book.subscribe, book.getState, book.getState);
  }

  return {
    createOrderBook: createOrderBook,
    useOrders: useOrders,
    validatePrice: validatePrice,
    validateQty: validateQty,
    validateOrderDraft: validateOrderDraft,
    nearestTick: nearestTick,
    resolveDragPrice: resolveDragPrice
  };
});
