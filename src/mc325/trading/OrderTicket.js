(function (root, factory) {
  var api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.Mc325OrderTicket = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
  function ordersApi() {
    if (typeof require === 'function') return require('./useOrders');
    return root.Mc325UseOrders;
  }

  function snapshotOf(form) {
    return {
      symbol: form.symbol,
      side: form.side,
      type: form.type,
      qty: form.qty,
      price: form.price,
      stopPrice: form.stopPrice,
      targetPrice: form.targetPrice
    };
  }

  function same(a, b) {
    return JSON.stringify(a) === JSON.stringify(b);
  }

  function toPayload(form) {
    return {
      symbol: String(form.symbol || '').trim(),
      side: form.side,
      type: form.type,
      qty: Number(form.qty),
      price: Number(form.price),
      stopPrice: form.stopPrice == null || form.stopPrice === '' ? null : Number(form.stopPrice),
      targetPrice: form.targetPrice == null || form.targetPrice === '' ? null : Number(form.targetPrice)
    };
  }

  function createTicketController(options) {
    var opts = options || {};
    var getTickSize = opts.getTickSize || function () { return 0.01; };
    var getLotSize = opts.getLotSize || function () { return 1; };
    var form = {
      symbol: opts.symbol || '',
      side: opts.side || 'BUY',
      type: opts.type || 'LIMIT',
      qty: opts.qty != null ? opts.qty : 1,
      price: opts.price != null ? opts.price : '',
      stopPrice: opts.stopPrice != null ? opts.stopPrice : '',
      targetPrice: opts.targetPrice != null ? opts.targetPrice : ''
    };
    var preview = null;

    function set(patch) {
      Object.keys(patch || {}).forEach(function (key) {
        if (Object.prototype.hasOwnProperty.call(form, key)) form[key] = patch[key];
      });
      if (!preview || !same(preview, snapshotOf(form))) preview = null;
    }

    function errors() {
      return ordersApi().validateOrderDraft(form, getTickSize(), getLotSize());
    }

    return {
      getForm: function () { return snapshotOf(form); },
      set: set,
      preview: function () {
        var found = errors();
        if (found.length) {
          preview = null;
          return { ok: false, errors: found };
        }
        preview = snapshotOf(form);
        return { ok: true, preview: snapshotOf(form) };
      },
      canPlace: function () {
        return !!(preview && same(preview, snapshotOf(form)) && errors().length === 0);
      },
      consumePlace: function () {
        if (!(preview && same(preview, snapshotOf(form)) && errors().length === 0)) {
          return { ok: false, reason: 'preview_required' };
        }
        var order = toPayload(preview);
        preview = null;
        return { ok: true, order: order };
      }
    };
  }

  function field(labelText, node) {
    var label = document.createElement('label');
    label.style.display = 'grid';
    label.style.gap = '2px';
    label.style.font = '11px/1.2 sans-serif';
    var title = document.createElement('span');
    title.textContent = labelText;
    label.appendChild(title);
    label.appendChild(node);
    return label;
  }

  function mountOrderTicket(options) {
    var opts = options || {};
    var book = opts.book;
    var controller = opts.controller || createTicketController({
      symbol: opts.symbol || '',
      side: opts.side || 'BUY',
      getTickSize: function () { return book.getState().tickSize || 0.01; },
      getLotSize: function () { return book.getState().lotSize || 1; }
    });
    var rootNode = document.createElement('section');
    rootNode.id = 'mc325OrderTicket';
    rootNode.className = 'mc325-order-ticket';
    rootNode.setAttribute('aria-label', 'Order ticket');
    rootNode.style.position = 'fixed';
    rootNode.style.right = '16px';
    rootNode.style.bottom = '16px';
    rootNode.style.width = '280px';
    rootNode.style.boxSizing = 'border-box';
    rootNode.style.padding = '10px';
    rootNode.style.display = 'grid';
    rootNode.style.gap = '6px';
    rootNode.style.background = '#fff';
    rootNode.style.color = '#243348';
    rootNode.style.border = '1px solid #c8d1de';
    rootNode.style.borderRadius = '8px';
    rootNode.style.boxShadow = '0 8px 24px rgba(15,23,42,.18)';
    rootNode.style.setProperty('z-index', '1000', 'important');

    var heading = document.createElement('h2');
    heading.textContent = 'Paper order';
    heading.style.margin = '0';
    heading.style.font = '13px/1.2 sans-serif';
    rootNode.appendChild(heading);

    function input(kind) {
      var node = document.createElement('input');
      node.type = kind;
      node.style.height = '26px';
      node.style.border = '1px solid #c5ced8';
      node.style.borderRadius = '2px';
      node.style.padding = '0 6px';
      return node;
    }

    var symbolInput = input('text');
    var sideInput = document.createElement('select');
    sideInput.innerHTML = '<option value="BUY">Buy</option><option value="SELL">Sell</option>';
    var typeInput = document.createElement('select');
    typeInput.innerHTML = '<option value="LIMIT">Limit</option><option value="MARKET">Market</option>';
    var qtyInput = input('number');
    qtyInput.min = '1';
    qtyInput.step = '1';
    var priceInput = input('number');
    priceInput.min = '0';
    priceInput.step = '0.01';
    var stopInput = input('number');
    stopInput.step = '0.01';
    var targetInput = input('number');
    targetInput.step = '0.01';
    [sideInput, typeInput].forEach(function (node) {
      node.style.height = '26px';
      node.style.border = '1px solid #c5ced8';
      node.style.background = '#fff';
    });

    rootNode.appendChild(field('Symbol', symbolInput));
    rootNode.appendChild(field('Side', sideInput));
    rootNode.appendChild(field('Type', typeInput));
    rootNode.appendChild(field('Qty', qtyInput));
    rootNode.appendChild(field('Price', priceInput));
    rootNode.appendChild(field('Stop', stopInput));
    rootNode.appendChild(field('Target', targetInput));

    var previewBox = document.createElement('p');
    previewBox.className = 'mc325-ticket-preview';
    previewBox.style.margin = '0';
    previewBox.style.minHeight = '32px';
    previewBox.style.font = '12px/1.35 sans-serif';
    previewBox.textContent = 'Preview the order before placing it.';
    rootNode.appendChild(previewBox);

    var actions = document.createElement('div');
    actions.style.display = 'grid';
    actions.style.gridTemplateColumns = '1fr 1fr';
    actions.style.gap = '6px';
    var previewBtn = document.createElement('button');
    previewBtn.type = 'button';
    previewBtn.textContent = 'Preview';
    var placeBtn = document.createElement('button');
    placeBtn.type = 'button';
    placeBtn.textContent = 'Place';
    placeBtn.disabled = true;
    [previewBtn, placeBtn].forEach(function (node) {
      node.style.height = '32px';
      node.style.fontWeight = '700';
    });
    actions.appendChild(previewBtn);
    actions.appendChild(placeBtn);
    rootNode.appendChild(actions);

    function readInputs() {
      controller.set({
        symbol: symbolInput.value,
        side: sideInput.value,
        type: typeInput.value,
        qty: qtyInput.value,
        price: priceInput.value,
        stopPrice: stopInput.value,
        targetPrice: targetInput.value
      });
    }

    function applyForm() {
      var form = controller.getForm();
      symbolInput.value = form.symbol;
      sideInput.value = form.side;
      typeInput.value = form.type;
      qtyInput.value = form.qty;
      priceInput.value = form.price;
      stopInput.value = form.stopPrice;
      targetInput.value = form.targetPrice;
      paint();
    }

    function paint() {
      var allowed = controller.canPlace();
      placeBtn.disabled = !allowed;
      if (!allowed && previewBox.dataset.mode !== 'error' && previewBox.dataset.mode !== 'preview') {
        previewBox.textContent = 'Preview the order before placing it.';
      }
    }

    function onEdit() {
      readInputs();
      previewBox.dataset.mode = '';
      previewBox.textContent = 'Preview the order before placing it.';
      paint();
    }

    [symbolInput, sideInput, typeInput, qtyInput, priceInput, stopInput, targetInput].forEach(function (node) {
      node.addEventListener('input', onEdit);
      node.addEventListener('change', onEdit);
    });

    previewBtn.addEventListener('click', function () {
      readInputs();
      var result = controller.preview();
      if (!result.ok) {
        previewBox.dataset.mode = 'error';
        previewBox.textContent = result.errors.join(', ');
        paint();
        return;
      }
      var order = result.preview;
      previewBox.dataset.mode = 'preview';
      var text = order.side + ' ' + order.type + ' ' + order.symbol + ' qty ' + order.qty + ' @ ' + order.price;
      if (order.stopPrice !== '') text += ' SL ' + order.stopPrice;
      if (order.targetPrice !== '') text += ' TP ' + order.targetPrice;
      previewBox.textContent = text;
      paint();
    });

    placeBtn.addEventListener('click', function () {
      readInputs();
      var result = controller.consumePlace();
      if (!result.ok) {
        previewBox.dataset.mode = 'error';
        previewBox.textContent = 'Preview the order before placing it.';
        paint();
        return;
      }
      book.place(Object.assign({ accountId: opts.accountId || null }, result.order));
      previewBox.dataset.mode = '';
      previewBox.textContent = 'Sent. Preview again for another order.';
      paint();
    });

    if (book.subscribe) {
      book.subscribe(function (state) {
        if (!state.lastReject || state.lastReject.action !== 'place_order') return;
        previewBox.dataset.mode = 'error';
        previewBox.textContent = state.lastReject.reason || 'rejected';
      });
    }

    applyForm();
    (opts.host || document.body).appendChild(rootNode);

    return {
      element: rootNode,
      controller: controller,
      setSide: function (side) {
        controller.set({ side: side });
        applyForm();
      },
      setSymbol: function (symbol) {
        if (!symbol) return;
        controller.set({ symbol: symbol });
        applyForm();
      },
      focus: function () { priceInput.focus(); }
    };
  }

  return {
    createTicketController: createTicketController,
    mountOrderTicket: mountOrderTicket
  };
});
