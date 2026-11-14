'use strict';

const jwt = require('jsonwebtoken');
const { OrderError } = require('./orderEngine');

function mountRest(app, options) {
  const engine = options.engine;
  const secret = options.jwtSecret;
  const tickSize = options.tickSize;
  const lotSize = options.lotSize;

  function signUser(userId) {
    return jwt.sign({ sub: userId }, secret, { expiresIn: '12h' });
  }

  function fail(res, err) {
    const reason = err && err.reason ? err.reason : 'rejected';
    const status = reason === 'not_found' ? 404 : 400;
    res.status(status).json({ error: reason });
  }

  function auth(req, res, next) {
    const header = String(req.headers.authorization || '');
    const token = header.startsWith('Bearer ') ? header.slice(7).trim() : '';
    if (!token) {
      res.status(401).json({ error: 'auth_required' });
      return;
    }
    try {
      const payload = jwt.verify(token, secret);
      const userId = String(payload.sub || '');
      if (!userId) throw new Error('no sub');
      req.userId = userId;
      next();
    } catch (err) {
      res.status(401).json({ error: 'bad_token' });
    }
  }

  app.post('/api/session', (req, res) => {
    const userId = String((req.body && req.body.userId) || '').trim();
    if (!/^[A-Za-z0-9_.:-]{1,64}$/.test(userId)) {
      res.status(400).json({ error: 'bad_user' });
      return;
    }
    res.json({
      token: signUser(userId),
      userId,
      accountId: 'paper:' + userId,
      tickSize,
      lotSize
    });
  });

  app.get('/api/accounts', auth, (req, res) => {
    res.json({
      accounts: [{
        id: 'paper:' + req.userId,
        name: 'Paper',
        broker: 'mock',
        userId: req.userId
      }]
    });
  });

  app.get('/api/orders', auth, (req, res) => {
    res.json({ orders: engine.getOrders(req.userId) });
  });

  app.get('/api/positions', auth, (req, res) => {
    res.json({ positions: engine.getPositions(req.userId) });
  });

  app.post('/api/orders', auth, (req, res) => {
    try {
      const orders = engine.place(req.userId, req.body || {});
      res.status(201).json({ orders });
    } catch (err) {
      if (err instanceof OrderError) {
        fail(res, err);
        return;
      }
      res.status(500).json({ error: 'server_error' });
    }
  });

  app.patch('/api/orders/:id', auth, (req, res) => {
    try {
      const order = engine.modify(req.userId, req.params.id, req.body || {});
      res.json({ order });
    } catch (err) {
      if (err instanceof OrderError) {
        fail(res, err);
        return;
      }
      res.status(500).json({ error: 'server_error' });
    }
  });

  app.delete('/api/orders/:id', auth, (req, res) => {
    try {
      const order = engine.cancel(req.userId, req.params.id);
      res.json({ order });
    } catch (err) {
      if (err instanceof OrderError) {
        fail(res, err);
        return;
      }
      res.status(500).json({ error: 'server_error' });
    }
  });
}

module.exports = { mountRest };
