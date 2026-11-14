'use strict';

const jwt = require('jsonwebtoken');
const { WebSocketServer } = require('ws');
const { OrderError } = require('./orderEngine');

function attachWs(options) {
  const engine = options.engine;
  const secret = options.jwtSecret;
  const tickSize = options.tickSize;
  const lotSize = options.lotSize;
  const sockets = new Map();

  const wss = new WebSocketServer({
    port: options.port,
    host: options.host || '127.0.0.1',
    path: '/ws'
  });

  function broadcast(userId, message) {
    const set = sockets.get(userId);
    if (!set) return;
    const data = JSON.stringify(message);
    set.forEach((socket) => {
      if (socket.readyState === 1) socket.send(data);
    });
  }

  function onOrder(order) {
    broadcast(order.userId, { type: 'order_update', order });
  }

  function onPositions(payload) {
    broadcast(payload.userId, { type: 'positions', positions: payload.positions });
  }

  engine.on('order', onOrder);
  engine.on('positions', onPositions);

  function send(socket, message) {
    if (socket.readyState === 1) socket.send(JSON.stringify(message));
  }

  function reject(socket, msg, err) {
    send(socket, {
      type: 'reject',
      action: msg && msg.type ? msg.type : null,
      id: msg && msg.id ? msg.id : null,
      clientId: msg && msg.clientId ? msg.clientId : null,
      reason: err && err.reason ? err.reason : 'rejected'
    });
  }

  function route(socket, userId, msg) {
    try {
      if (msg.type === 'place_order') {
        engine.place(userId, {
          symbol: msg.symbol,
          side: msg.side,
          type: msg.orderType,
          qty: msg.qty,
          price: msg.price,
          stopPrice: msg.stopPrice,
          targetPrice: msg.targetPrice,
          accountId: msg.accountId,
          parentId: msg.parentId
        });
        return;
      }
      if (msg.type === 'modify_order') {
        engine.modify(userId, msg.id, msg);
        return;
      }
      if (msg.type === 'cancel_order') {
        engine.cancel(userId, msg.id);
        return;
      }
      if (msg.type === 'cancel_all') {
        engine.cancelAll(userId);
        return;
      }
      if (msg.type === 'get_orders') {
        send(socket, { type: 'orders', orders: engine.getOrders(userId) });
        return;
      }
      if (msg.type === 'get_positions') {
        send(socket, { type: 'positions', positions: engine.getPositions(userId) });
        return;
      }
      reject(socket, msg, new OrderError('unknown_type'));
    } catch (err) {
      if (err instanceof OrderError) {
        reject(socket, msg, err);
        return;
      }
      reject(socket, msg, new OrderError('rejected'));
    }
  }

  wss.on('connection', (socket) => {
    let userId = null;
    socket.on('message', (buf) => {
      let msg;
      try {
        msg = JSON.parse(String(buf));
      } catch (err) {
        send(socket, { type: 'reject', reason: 'bad_json' });
        return;
      }
      if (!msg || typeof msg.type !== 'string') {
        send(socket, { type: 'reject', reason: 'bad_message' });
        return;
      }
      if (!userId) {
        if (msg.type !== 'auth') {
          send(socket, { type: 'reject', action: msg.type, reason: 'auth_required' });
          socket.close();
          return;
        }
        try {
          const payload = jwt.verify(String(msg.token || ''), secret);
          userId = String(payload.sub || '');
          if (!userId) throw new Error('no sub');
        } catch (err) {
          send(socket, { type: 'reject', action: 'auth', reason: 'bad_token' });
          socket.close();
          return;
        }
        let set = sockets.get(userId);
        if (!set) {
          set = new Set();
          sockets.set(userId, set);
        }
        set.add(socket);
        send(socket, { type: 'auth_ok', userId, tickSize, lotSize });
        send(socket, { type: 'orders', orders: engine.getOrders(userId) });
        send(socket, { type: 'positions', positions: engine.getPositions(userId) });
        return;
      }
      route(socket, userId, msg);
    });

    socket.on('close', () => {
      if (!userId) return;
      const set = sockets.get(userId);
      if (!set) return;
      set.delete(socket);
      if (set.size === 0) sockets.delete(userId);
    });

    socket.on('error', () => {});
  });

  function close() {
    engine.removeListener('order', onOrder);
    engine.removeListener('positions', onPositions);
    wss.clients.forEach((client) => {
      try { client.terminate(); } catch (err) {}
    });
    return new Promise((resolve) => {
      wss.close(() => resolve());
    });
  }

  return new Promise((resolve, reject) => {
    const done = () => resolve({
      wss,
      port: wss.address().port,
      close
    });
    if (wss.address()) {
      done();
      return;
    }
    wss.once('listening', done);
    wss.once('error', reject);
  });
}

module.exports = { attachWs };
