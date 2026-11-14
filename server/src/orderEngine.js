'use strict';

const { EventEmitter } = require('events');
const crypto = require('crypto');
const { validateOrder, validatePrice, validateQty } = require('./validate');

class OrderError extends Error {
  constructor(reason) {
    super(reason);
    this.reason = reason;
  }
}

function audit(entry) {
  console.log(JSON.stringify(entry));
}

function signOf(side) {
  return side === 'SELL' ? -1 : 1;
}

class OrderEngine extends EventEmitter {
  constructor(options) {
    super();
    const opts = options || {};
    if (!opts.broker) throw new Error('broker adapter required');
    this.broker = opts.broker;
    this.tickSize = Number(opts.tickSize);
    this.lotSize = Number(opts.lotSize);
    if (!(this.tickSize > 0)) throw new Error('tick size required');
    if (!(this.lotSize > 0)) throw new Error('lot size required');
    this.orders = new Map();
    this.now = opts.now || function () { return new Date(); };
    this.log = opts.log || audit;
  }

  place(userId, input) {
    const owner = String(userId || '');
    if (!owner) throw new OrderError('user_required');
    const checked = validateOrder(input, { tickSize: this.tickSize, lotSize: this.lotSize });
    if (!checked.ok) throw new OrderError(checked.reason);
    const spec = checked.order;
    const time = this.now().toISOString();
    const order = {
      id: crypto.randomUUID(),
      userId: owner,
      accountId: spec.accountId || ('paper:' + owner),
      symbol: spec.symbol,
      side: spec.side,
      type: spec.type,
      qty: spec.qty,
      price: spec.price,
      stopPrice: spec.stopPrice,
      targetPrice: spec.targetPrice,
      parentId: spec.parentId,
      status: 'OPEN',
      filledQty: 0,
      avgPrice: 0,
      createdAt: time,
      updatedAt: time
    };
    this._applyFill(order, this.broker.place(order));
    this.orders.set(order.id, order);
    this._audit('place', owner, order.id, time);

    const created = [order];
    if (order.type === 'MARKET' && order.status === 'FILLED' && (order.stopPrice || order.targetPrice)) {
      const stop = order.stopPrice;
      const target = order.targetPrice;
      const opposite = order.side === 'BUY' ? 'SELL' : 'BUY';
      order.stopPrice = null;
      order.targetPrice = null;
      order.updatedAt = time;
      if (stop) {
        created.push(this.place(owner, {
          symbol: order.symbol,
          side: opposite,
          type: 'SL',
          qty: order.qty,
          price: stop,
          accountId: order.accountId,
          parentId: order.id
        })[0]);
      }
      if (target) {
        created.push(this.place(owner, {
          symbol: order.symbol,
          side: opposite,
          type: 'TP',
          qty: order.qty,
          price: target,
          accountId: order.accountId,
          parentId: order.id
        })[0]);
      }
    }

    this.emit('order', copyOrder(order));
    this.emit('positions', { userId: owner, positions: this.getPositions(owner) });
    return created.map(copyOrder);
  }

  modify(userId, id, patch) {
    const order = this._ownOpen(userId, id);
    const src = patch || {};
    const next = {};
    if (src.price != null && src.price !== '') {
      const price = validatePrice(src.price, this.tickSize);
      if (!price.ok) throw new OrderError(price.reason);
      next.price = price.price;
    }
    if (Object.prototype.hasOwnProperty.call(src, 'stopPrice') && src.stopPrice != null && src.stopPrice !== '') {
      const stop = validatePrice(src.stopPrice, this.tickSize);
      if (!stop.ok) throw new OrderError(stop.reason);
      next.stopPrice = stop.price;
    }
    if (Object.prototype.hasOwnProperty.call(src, 'targetPrice') && src.targetPrice != null && src.targetPrice !== '') {
      const target = validatePrice(src.targetPrice, this.tickSize);
      if (!target.ok) throw new OrderError(target.reason);
      next.targetPrice = target.price;
    }
    if (src.qty != null && src.qty !== '') {
      const qty = validateQty(src.qty, this.lotSize);
      if (!qty.ok) throw new OrderError(qty.reason);
      next.qty = qty.qty;
    }
    if (!Object.keys(next).length) throw new OrderError('empty_modify');
    const time = this.now().toISOString();
    const brokerPatch = this.broker.modify(order, next) || {};
    if (brokerPatch.price != null) order.price = brokerPatch.price;
    if (brokerPatch.qty != null) order.qty = brokerPatch.qty;
    if (Object.prototype.hasOwnProperty.call(brokerPatch, 'stopPrice')) order.stopPrice = brokerPatch.stopPrice;
    if (Object.prototype.hasOwnProperty.call(brokerPatch, 'targetPrice')) order.targetPrice = brokerPatch.targetPrice;
    Object.keys(next).forEach((key) => {
      order[key] = next[key];
    });
    order.updatedAt = time;
    if (order.status !== 'OPEN') order.status = 'OPEN';
    this.orders.set(order.id, order);
    this._audit('modify', order.userId, order.id, time);
    this.emit('order', copyOrder(order));
    this.emit('positions', { userId: order.userId, positions: this.getPositions(order.userId) });
    return copyOrder(order);
  }

  cancel(userId, id) {
    const order = this._ownOpen(userId, id);
    const time = this.now().toISOString();
    this.broker.cancel(order);
    order.status = 'CANCELLED';
    order.updatedAt = time;
    this.orders.set(order.id, order);
    this._audit('cancel', order.userId, order.id, time);
    this.emit('order', copyOrder(order));
    this.emit('positions', { userId: order.userId, positions: this.getPositions(order.userId) });
    return copyOrder(order);
  }

  cancelAll(userId) {
    const owner = String(userId || '');
    const open = this.getOrders(owner).filter((order) => order.status === 'OPEN');
    return open.map((order) => this.cancel(owner, order.id));
  }

  getOrders(userId) {
    const owner = String(userId || '');
    return Array.from(this.orders.values())
      .filter((order) => order.userId === owner)
      .sort((a, b) => (a.createdAt < b.createdAt ? -1 : a.createdAt > b.createdAt ? 1 : a.id < b.id ? -1 : 1))
      .map(copyOrder);
  }

  getPositions(userId) {
    const owner = String(userId || '');
    const fills = this.getOrders(owner)
      .filter((order) => order.status === 'FILLED' && order.filledQty > 0)
      .sort((a, b) => (a.createdAt < b.createdAt ? -1 : a.createdAt > b.createdAt ? 1 : 0));
    const book = new Map();
    fills.forEach((fill) => {
      const key = fill.accountId + '|' + fill.symbol;
      const signed = signOf(fill.side) * fill.filledQty;
      const current = book.get(key) || {
        accountId: fill.accountId,
        symbol: fill.symbol,
        qty: 0,
        avgPrice: 0
      };
      book.set(key, applyFill(current, signed, fill.avgPrice || fill.price));
    });
    return Array.from(book.values()).filter((row) => row.qty !== 0);
  }

  _applyFill(order, fill) {
    if (!fill) return;
    if (fill.status) order.status = fill.status;
    if (fill.filledQty != null) order.filledQty = fill.filledQty;
    if (fill.avgPrice != null) order.avgPrice = fill.avgPrice;
  }

  _own(userId, id) {
    const order = this.orders.get(String(id || ''));
    if (!order || order.userId !== String(userId || '')) throw new OrderError('not_found');
    return order;
  }

  _ownOpen(userId, id) {
    const order = this._own(userId, id);
    if (order.status === 'FILLED') throw new OrderError('not_filled');
    if (order.status !== 'OPEN') throw new OrderError('not_open');
    return order;
  }

  _audit(event, userId, orderId, time) {
    this.log({
      event,
      time,
      userId: String(userId),
      orderId: String(orderId)
    });
  }
}

function copyOrder(order) {
  return {
    id: order.id,
    userId: order.userId,
    accountId: order.accountId,
    symbol: order.symbol,
    side: order.side,
    type: order.type,
    qty: order.qty,
    price: order.price,
    stopPrice: order.stopPrice,
    targetPrice: order.targetPrice,
    parentId: order.parentId,
    status: order.status,
    filledQty: order.filledQty,
    avgPrice: order.avgPrice,
    createdAt: order.createdAt,
    updatedAt: order.updatedAt
  };
}

function applyFill(position, signedQty, price) {
  if (position.qty === 0) {
    return { accountId: position.accountId, symbol: position.symbol, qty: signedQty, avgPrice: price };
  }
  const sameDirection = Math.sign(position.qty) === Math.sign(signedQty);
  if (sameDirection) {
    const qty = position.qty + signedQty;
    const avgPrice = (Math.abs(position.qty) * position.avgPrice + Math.abs(signedQty) * price) / Math.abs(qty);
    return { accountId: position.accountId, symbol: position.symbol, qty, avgPrice };
  }
  const qty = position.qty + signedQty;
  if (qty === 0) {
    return { accountId: position.accountId, symbol: position.symbol, qty: 0, avgPrice: 0 };
  }
  if (Math.sign(qty) !== Math.sign(position.qty)) {
    return { accountId: position.accountId, symbol: position.symbol, qty, avgPrice: price };
  }
  return { accountId: position.accountId, symbol: position.symbol, qty, avgPrice: position.avgPrice };
}

module.exports = {
  OrderEngine,
  OrderError
};
