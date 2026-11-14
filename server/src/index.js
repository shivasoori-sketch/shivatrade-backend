'use strict';

const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '../.env') });

const express = require('express');
const cors = require('cors');
const { OrderEngine } = require('./orderEngine');
const { MockBrokerAdapter } = require('./brokerAdapter');
const { mountRest } = require('./rest');
const { attachWs } = require('./ws');

function createApp(options) {
  const opts = options || {};
  const tickSize = Number(opts.tickSize != null ? opts.tickSize : process.env.TICK_SIZE || 0.01);
  const lotSize = Number(opts.lotSize != null ? opts.lotSize : process.env.LOT_SIZE || 1);
  const jwtSecret = opts.jwtSecret || process.env.JWT_SECRET || 'change_me';
  const engine = opts.engine || new OrderEngine({
    broker: opts.broker || new MockBrokerAdapter(),
    tickSize,
    lotSize,
    log: opts.log
  });
  const app = express();
  app.use(cors());
  app.use(express.json());
  mountRest(app, { engine, jwtSecret, tickSize, lotSize });
  const staticRoot = opts.staticRoot || path.join(__dirname, '../../src/mc325/trading');
  if (fs.existsSync(staticRoot)) {
    app.use('/mc325/trading', express.static(staticRoot));
  }
  app.use((err, req, res, next) => {
    if (err && (err.type === 'entity.parse.failed' || err instanceof SyntaxError)) {
      res.status(400).json({ error: 'bad_json' });
      return;
    }
    next(err);
  });
  return { app, engine, jwtSecret, tickSize, lotSize };
}

async function start(options) {
  const opts = options || {};
  if (!process.env.JWT_SECRET && !opts.jwtSecret) {
    console.warn(JSON.stringify({
      event: 'config',
      time: new Date().toISOString(),
      message: 'JWT_SECRET is unset; development default is in use'
    }));
  }
  const built = createApp(opts);
  const host = opts.host || process.env.HOST || '127.0.0.1';
  const port = Number(opts.port != null ? opts.port : process.env.PORT || 6161);
  const wsPort = Number(opts.wsPort != null ? opts.wsPort : process.env.WS_PORT || 6162);
  const server = await new Promise((resolve, reject) => {
    const httpServer = built.app.listen(port, host, () => resolve(httpServer));
    httpServer.on('error', reject);
  });
  let ws;
  try {
    ws = await attachWs({
      port: wsPort,
      host,
      engine: built.engine,
      jwtSecret: built.jwtSecret,
      tickSize: built.tickSize,
      lotSize: built.lotSize
    });
  } catch (err) {
    await new Promise((resolve) => server.close(resolve));
    throw err;
  }
  return {
    app: built.app,
    engine: built.engine,
    host,
    port: server.address().port,
    wsPort: ws.port,
    server,
    wss: ws.wss,
    async close() {
      await ws.close();
      await new Promise((resolve) => server.close(resolve));
    }
  };
}

if (require.main === module) {
  start().catch((err) => {
    console.error(err && err.message ? err.message : String(err));
    process.exit(1);
  });
}

module.exports = { start, createApp };
