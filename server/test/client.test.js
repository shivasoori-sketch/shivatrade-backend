'use strict';

const { describe, test } = require('node:test');
const assert = require('node:assert/strict');
const { createWsClient } = require('../../src/mc325/trading/wsClient');
const { createOrderBook, useOrders } = require('../../src/mc325/trading/useOrders');
const { finishDrag, sampleDragPrice } = require('../../src/mc325/trading/ChartTradingOverlay');
const { createTicketController } = require('../../src/mc325/trading/OrderTicket');

function fakeClient() {
  const sent = [];
  const handlers = {};
  return {
    sent,
    send(msg) { sent.push(msg); },
    on(type, fn) {
      handlers[type] = handlers[type] || [];
      handlers[type].push(fn);
    },
    emit(type, msg) {
      (handlers[type] || []).forEach((fn) => fn(msg));
    }
  };
}

describe('websocket client', () => {
  test('queues while down and flushes only after auth', () => {
    const sockets = [];
    const timers = [];
    function WS() {
      this.readyState = 0;
      this.sent = [];
      this.send = (data) => { this.sent.push(JSON.parse(data)); };
      this.close = () => {
        this.readyState = 3;
        if (this.onclose) this.onclose();
      };
      sockets.push(this);
    }
    const client = createWsClient({
      url: 'ws://127.0.0.1:6162/ws',
      WebSocket: WS,
      getToken: () => 'paper-token',
      schedule: (fn, ms) => {
        timers.push({ fn, ms });
        return timers.length;
      }
    });
    client.connect();
    assert.equal(client.send({ type: 'place_order', symbol: 'CE' }), false);
    assert.equal(client.getQueue().length, 1);
    assert.equal(sockets[0].sent.length, 0);
    sockets[0].readyState = 1;
    sockets[0].onopen();
    assert.deepEqual(sockets[0].sent[0], { type: 'auth', token: 'paper-token' });
    assert.equal(client.getQueue().length, 1);
    sockets[0].onmessage({ data: JSON.stringify({ type: 'auth_ok', userId: 'paper' }) });
    assert.equal(client.getQueue().length, 0);
    assert.equal(sockets[0].sent[1].type, 'place_order');
    sockets[0].onclose();
    assert.equal(timers[0].ms, 500);
    timers[0].fn();
    assert.equal(sockets.length, 2);
    sockets[1].onclose();
    assert.equal(timers[1].ms, 1000);
  });
});

describe('orders', () => {
  test('optimistic modify rolls back when the server rejects it', () => {
    const client = fakeClient();
    const book = createOrderBook(client, { tickSize: 0.01, lotSize: 1 });
    client.emit('message', {
      type: 'orders',
      orders: [{ id: '1', symbol: 'CE', side: 'BUY', type: 'LIMIT', qty: 1, price: 10, status: 'OPEN' }]
    });
    const denied = book.modify('1', { price: 10.015 });
    assert.equal(denied.snapback, true);
    assert.equal(denied.reason, 'invalid_tick');
    assert.equal(book.getState().orders[0].price, 10);
    assert.equal(client.sent.length, 0);

    const ok = book.modify('1', { price: 10.02 });
    assert.equal(ok.ok, true);
    assert.equal(book.getState().orders[0].price, 10.02);
    assert.equal(book.getState().orders[0].optimistic, true);
    assert.equal(client.sent[0].type, 'modify_order');
    client.emit('message', { type: 'reject', action: 'modify_order', id: '1', reason: 'not_filled' });
    assert.equal(book.getState().orders[0].price, 10);
    assert.equal(book.getState().orders[0].optimistic, undefined);
    assert.equal(useOrders(book).orders[0].id, '1');
    book.place({ symbol: 'CE', side: 'BUY', type: 'LIMIT', qty: 1, price: 10 });
    assert.equal(client.sent[1].type, 'place_order');
    assert.equal(client.sent[1].orderType, 'LIMIT');
  });
});

describe('chart drag', () => {
  test('an invalid tick snaps back and a valid tick can be modified', () => {
    const off = finishDrag(10.015, 0.01, 10);
    assert.equal(off.action, 'snapback');
    assert.equal(off.price, 10);
    assert.equal(off.reason, 'invalid_tick');
    const bad = finishDrag(0, 0.01, 10);
    assert.equal(bad.action, 'snapback');
    assert.equal(bad.reason, 'price_must_be_positive');
    const same = finishDrag(10, 0.01, 10);
    assert.equal(same.action, 'snapback');
    const moved = finishDrag(10.02, 0.01, 10);
    assert.equal(moved.action, 'modify');
    assert.equal(moved.price, 10.02);
    assert.equal(sampleDragPrice(10.015, ''), 10.015);
    assert.equal(finishDrag(sampleDragPrice(10.015, ''), 0.01, 10).action, 'snapback');
    assert.equal(sampleDragPrice(10.015, '10.02'), 10.02);
    assert.equal(finishDrag(sampleDragPrice(10.015, '10.02'), 0.01, 10).action, 'modify');
  });
});

describe('ticket', () => {
  test('place stays blocked until the preview matches the form', () => {
    const ticket = createTicketController({
      getTickSize: () => 0.01,
      getLotSize: () => 1
    });
    ticket.set({ symbol: 'CE', side: 'BUY', type: 'LIMIT', qty: 1, price: '10.02', stopPrice: '9.50', targetPrice: '' });
    assert.equal(ticket.canPlace(), false);
    assert.equal(ticket.consumePlace().reason, 'preview_required');
    const preview = ticket.preview();
    assert.equal(preview.ok, true);
    assert.equal(ticket.canPlace(), true);
    ticket.set({ price: '10.03' });
    assert.equal(ticket.canPlace(), false);
    ticket.set({ price: '10.015' });
    assert.equal(ticket.preview().ok, false);
    assert.equal(ticket.canPlace(), false);
  });
});
