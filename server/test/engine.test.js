'use strict';

const { describe, test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const { OrderEngine, OrderError } = require('../src/orderEngine');
const { IBrokerAdapter, MockBrokerAdapter } = require('../src/brokerAdapter');
const { validatePrice, validateQty } = require('../src/validate');

function engine(extra) {
  const logs = [];
  const book = new OrderEngine(Object.assign({
    broker: new MockBrokerAdapter(),
    tickSize: 0.01,
    lotSize: 1,
    log: (entry) => logs.push(entry)
  }, extra));
  return { book, logs };
}

describe('validation', () => {
  test('price must be a positive tick', () => {
    assert.equal(validatePrice(0, 0.01).reason, 'price_must_be_positive');
    assert.equal(validatePrice(-1, 0.01).reason, 'price_must_be_positive');
    assert.equal(validatePrice(10.015, 0.01).reason, 'invalid_tick');
    assert.equal(validatePrice(10.02, 0.01).price, 10.02);
    assert.equal(validatePrice('10.50', 0.01).price, 10.5);
  });

  test('qty matches the lot', () => {
    assert.equal(validateQty(0, 1).ok, false);
    assert.equal(validateQty(1.5, 1).ok, false);
    assert.equal(validateQty(25, 50).reason, 'qty_must_match_lot');
    assert.equal(validateQty(50, 50).qty, 50);
  });
});

describe('order engine', () => {
  test('market orders fill immediately and exits stay open', () => {
    const { book, logs } = engine();
    const orders = book.place('user-1', {
      symbol: 'CE',
      side: 'BUY',
      type: 'MARKET',
      qty: 1,
      price: 10,
      stopPrice: 9.5,
      targetPrice: 11
    });
    assert.equal(orders[0].status, 'FILLED');
    assert.equal(orders[0].filledQty, 1);
    assert.equal(orders[0].avgPrice, 10);
    assert.equal(orders[1].type, 'SL');
    assert.equal(orders[1].status, 'OPEN');
    assert.equal(orders[1].parentId, orders[0].id);
    assert.equal(orders[2].type, 'TP');
    assert.equal(book.getPositions('user-1')[0].qty, 1);
    assert.equal(book.getPositions('user-1')[0].avgPrice, 10);
    assert.equal(logs[0].event, 'place');
    assert.equal(logs[0].userId, 'user-1');
    assert.equal(typeof logs[0].time, 'string');
    assert.ok(!Number.isNaN(Date.parse(logs[0].time)));
  });

  test('rejects a missing, filled, or off-tick modify and logs a valid one', () => {
    const { book, logs } = engine();
    const [filled] = book.place('user-1', {
      symbol: 'CE', side: 'BUY', type: 'MARKET', qty: 2, price: 10
    });
    assert.throws(() => book.modify('user-1', filled.id, { price: 10.5 }), (err) => err instanceof OrderError && err.reason === 'not_filled');
    assert.throws(() => book.cancel('user-1', filled.id), (err) => err.reason === 'not_filled');
    assert.throws(() => book.modify('user-1', 'missing', { price: 10 }), (err) => err.reason === 'not_found');

    const [limit] = book.place('user-1', {
      symbol: 'CE', side: 'SELL', type: 'LIMIT', qty: 2, price: 10, stopPrice: 10.5
    });
    assert.equal(limit.status, 'OPEN');
    assert.throws(() => book.modify('user-1', limit.id, { price: 10.015 }), (err) => err.reason === 'invalid_tick');
    const moved = book.modify('user-1', limit.id, { price: 10.25 });
    assert.equal(moved.price, 10.25);
    assert.equal(moved.status, 'OPEN');
    const cancelled = book.cancel('user-1', limit.id);
    assert.equal(cancelled.status, 'CANCELLED');
    assert.throws(() => book.cancel('user-1', limit.id), (err) => err.reason === 'not_open');
    const events = logs.map((entry) => entry.event);
    assert.ok(events.includes('place'));
    assert.ok(events.includes('modify'));
    assert.ok(events.includes('cancel'));
    logs.forEach((entry) => {
      assert.equal(entry.userId, 'user-1');
      assert.ok(entry.time);
      assert.ok(entry.orderId);
    });
  });

  test('positions net across fills and stay private to the user', () => {
    const { book } = engine();
    book.place('user-1', { symbol: 'CE', side: 'BUY', type: 'MARKET', qty: 2, price: 10 });
    book.place('user-1', { symbol: 'CE', side: 'BUY', type: 'MARKET', qty: 2, price: 12 });
    assert.equal(book.getPositions('user-1')[0].qty, 4);
    assert.equal(book.getPositions('user-1')[0].avgPrice, 11);
    book.place('user-1', { symbol: 'CE', side: 'SELL', type: 'MARKET', qty: 4, price: 13 });
    assert.deepEqual(book.getPositions('user-1'), []);
    book.place('user-2', { symbol: 'CE', side: 'BUY', type: 'MARKET', qty: 1, price: 8 });
    assert.equal(book.getOrders('user-1').some((order) => order.userId === 'user-2'), false);
    assert.equal(book.getOrders('user-2').length, 1);
  });

  test('lot size is enforced', () => {
    const { book } = engine({ lotSize: 50 });
    assert.throws(() => book.place('user-1', {
      symbol: 'CE', side: 'BUY', type: 'LIMIT', qty: 25, price: 10
    }), (err) => err.reason === 'qty_must_match_lot');
    const [order] = book.place('user-1', {
      symbol: 'CE', side: 'BUY', type: 'LIMIT', qty: 50, price: 10
    });
    assert.equal(order.qty, 50);
  });

  test('the adapter interface is not a broker', () => {
    const adapter = new IBrokerAdapter();
    assert.throws(() => adapter.place({}), /not implemented/);
    assert.equal(new MockBrokerAdapter().place({ type: 'MARKET', qty: 1, price: 3 }).status, 'FILLED');
    assert.equal(new MockBrokerAdapter().place({ type: 'LIMIT', qty: 1, price: 3 }).status, 'OPEN');
  });
});

describe('server source', () => {
  test('does not start a cluster or a real broker', () => {
    const dir = path.join(__dirname, '../src');
    fs.readdirSync(dir).forEach((file) => {
      const text = fs.readFileSync(path.join(dir, file), 'utf8');
      assert.equal(/\bcluster\b|kiteconnect|KiteConnect|SmartConnect|smartapi/i.test(text), false, file);
    });
  });
});
