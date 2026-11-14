'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { WebSocket } = require('ws');
const { start } = require('../src/index');

function nextMessage(socket) {
  const queued = [];
  const waiting = [];
  socket.on('message', (buf) => {
    const msg = JSON.parse(String(buf));
    if (waiting.length) waiting.shift()(msg);
    else queued.push(msg);
  });
  return function next() {
    if (queued.length) return Promise.resolve(queued.shift());
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('timed out waiting for a socket message')), 4000);
      waiting.push((msg) => {
        clearTimeout(timer);
        resolve(msg);
      });
    });
  };
}

function opened(socket) {
  return new Promise((resolve, reject) => {
    socket.once('open', resolve);
    socket.once('error', reject);
  });
}

async function api(base, token, method, path, body) {
  const headers = { 'content-type': 'application/json' };
  if (token) headers.authorization = 'Bearer ' + token;
  const res = await fetch(base + path, {
    method,
    headers,
    body: body == null ? undefined : JSON.stringify(body)
  });
  const text = await res.text();
  return { status: res.status, body: text ? JSON.parse(text) : null };
}

test('rest and websocket paper trading', async (t) => {
  const logs = [];
  const started = await start({
    port: 0,
    wsPort: 0,
    host: '127.0.0.1',
    jwtSecret: 'test-secret',
    tickSize: 0.01,
    lotSize: 1,
    log: (entry) => logs.push(entry)
  });
  t.after(() => started.close());
  const base = 'http://127.0.0.1:' + started.port;

  const denied = await api(base, null, 'GET', '/api/orders');
  assert.equal(denied.status, 401);

  const session = await api(base, null, 'POST', '/api/session', { userId: 'paper' });
  assert.equal(session.status, 200);
  assert.equal(session.body.userId, 'paper');
  assert.equal(typeof session.body.token, 'string');
  assert.equal(session.body.token.includes('test-secret'), false);
  const token = session.body.token;

  const accounts = await api(base, token, 'GET', '/api/accounts');
  assert.equal(accounts.body.accounts[0].broker, 'mock');
  assert.equal(accounts.body.accounts[0].id, 'paper:paper');

  const badPrice = await api(base, token, 'POST', '/api/orders', {
    symbol: 'CE', side: 'BUY', type: 'LIMIT', qty: 1, price: 10.015
  });
  assert.equal(badPrice.status, 400);
  assert.equal(badPrice.body.error, 'invalid_tick');

  const placed = await api(base, token, 'POST', '/api/orders', {
    symbol: 'CE', side: 'BUY', type: 'LIMIT', qty: 1, price: 10
  });
  assert.equal(placed.status, 201);
  const limit = placed.body.orders[0];
  assert.equal(limit.status, 'OPEN');

  const moved = await api(base, token, 'PATCH', '/api/orders/' + limit.id, { price: 10.5 });
  assert.equal(moved.status, 200);
  assert.equal(moved.body.order.price, 10.5);

  const offTick = await api(base, token, 'PATCH', '/api/orders/' + limit.id, { price: 10.555 });
  assert.equal(offTick.status, 400);

  const cancelled = await api(base, token, 'DELETE', '/api/orders/' + limit.id);
  assert.equal(cancelled.body.order.status, 'CANCELLED');

  const filled = await api(base, token, 'POST', '/api/orders', {
    symbol: 'CE', side: 'BUY', type: 'MARKET', qty: 3, price: 10, stopPrice: 9.5
  });
  assert.equal(filled.body.orders[0].status, 'FILLED');
  assert.equal(filled.body.orders[1].type, 'SL');
  const positions = await api(base, token, 'GET', '/api/positions');
  assert.equal(positions.body.positions[0].qty, 3);
  const stillFilled = await api(base, token, 'PATCH', '/api/orders/' + filled.body.orders[0].id, { price: 11 });
  assert.equal(stillFilled.status, 400);
  assert.equal(stillFilled.body.error, 'not_filled');

  const other = await api(base, null, 'POST', '/api/session', { userId: 'other' });
  const hidden = await api(base, other.body.token, 'GET', '/api/orders');
  assert.equal(hidden.body.orders.length, 0);

  const moduleText = await fetch(base + '/mc325/trading/ChartTradingOverlay.js');
  assert.equal(moduleText.status, 200);

  ['place', 'modify', 'cancel'].forEach((event) => {
    const entry = logs.find((row) => row.event === event);
    assert.ok(entry, event);
    assert.equal(entry.userId, 'paper');
    assert.equal(typeof entry.time, 'string');
  });

  const early = new WebSocket('ws://127.0.0.1:' + started.wsPort + '/ws');
  await opened(early);
  const earlyNext = nextMessage(early);
  early.send(JSON.stringify({ type: 'place_order', symbol: 'CE' }));
  const earlyMsg = await earlyNext();
  assert.equal(earlyMsg.reason, 'auth_required');
  await new Promise((resolve) => early.once('close', resolve));

  const socket = new WebSocket('ws://127.0.0.1:' + started.wsPort + '/ws');
  await opened(socket);
  const next = nextMessage(socket);
  socket.send(JSON.stringify({ type: 'auth', token }));
  assert.equal((await next()).type, 'auth_ok');
  assert.equal((await next()).type, 'orders');
  assert.equal((await next()).type, 'positions');
  socket.send(JSON.stringify({
    type: 'place_order',
    clientId: 'c-limit',
    symbol: 'PE',
    side: 'SELL',
    orderType: 'LIMIT',
    qty: 1,
    price: 20
  }));
  const created = await next();
  assert.equal(created.type, 'order_update');
  assert.equal(created.order.status, 'OPEN');
  assert.equal((await next()).type, 'positions');
  socket.send(JSON.stringify({ type: 'modify_order', id: created.order.id, price: 20.015, clientId: 'c-bad' }));
  const rejected = await next();
  assert.equal(rejected.type, 'reject');
  assert.equal(rejected.reason, 'invalid_tick');
  assert.equal(rejected.clientId, 'c-bad');
  socket.send(JSON.stringify({ type: 'modify_order', id: created.order.id, price: 20.25 }));
  const updated = await next();
  assert.equal(updated.order.price, 20.25);
  assert.equal((await next()).type, 'positions');
  socket.send(JSON.stringify({ type: 'cancel_all' }));
  const cancelledUpdate = await next();
  assert.equal(cancelledUpdate.order.status, 'CANCELLED');
  socket.close();
});
