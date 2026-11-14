'use strict';

function tickDecimals(tickSize) {
  const text = String(tickSize);
  const dot = text.indexOf('.');
  if (dot < 0) return 0;
  return Math.min(8, text.length - dot - 1);
}

function normalizePrice(price, tickSize) {
  return Number(Number(price).toFixed(tickDecimals(tickSize)));
}

function isOnTick(price, tickSize) {
  if (!Number.isFinite(price) || !(Number(tickSize) > 0)) return false;
  const units = price / Number(tickSize);
  return Math.abs(units - Math.round(units)) < 1e-6;
}

function validatePrice(price, tickSize) {
  const n = typeof price === 'string' && price.trim() === '' ? NaN : Number(price);
  if (!Number.isFinite(n) || n <= 0) {
    return { ok: false, reason: 'price_must_be_positive' };
  }
  if (!isOnTick(n, tickSize)) {
    return { ok: false, reason: 'invalid_tick' };
  }
  return { ok: true, price: normalizePrice(n, tickSize) };
}

function validateQty(qty, lotSize) {
  const n = Number(qty);
  const lot = Number(lotSize);
  if (!Number.isInteger(n) || n <= 0) {
    return { ok: false, reason: 'qty_must_be_positive_integer' };
  }
  if (!Number.isInteger(lot) || lot <= 0) {
    return { ok: false, reason: 'bad_lot' };
  }
  if (n % lot !== 0) {
    return { ok: false, reason: 'qty_must_match_lot' };
  }
  return { ok: true, qty: n };
}

function optionalPrice(value, tickSize) {
  if (value == null || value === '') return { ok: true, price: null };
  return validatePrice(value, tickSize);
}

function validateOrder(input, opts) {
  const src = input || {};
  const tickSize = opts.tickSize;
  const lotSize = opts.lotSize;
  const symbol = String(src.symbol == null ? '' : src.symbol).trim();
  if (!symbol) return { ok: false, reason: 'symbol_required' };
  const side = String(src.side == null ? '' : src.side).toUpperCase();
  if (side !== 'BUY' && side !== 'SELL') return { ok: false, reason: 'bad_side' };
  const type = String(src.type || src.orderType || 'LIMIT').toUpperCase();
  if (['MARKET', 'LIMIT', 'SL', 'TP'].indexOf(type) < 0) {
    return { ok: false, reason: 'bad_type' };
  }
  const qty = validateQty(src.qty, lotSize);
  if (!qty.ok) return qty;
  const price = validatePrice(src.price, tickSize);
  if (!price.ok) return price;
  const stop = optionalPrice(src.stopPrice, tickSize);
  if (!stop.ok) return { ok: false, reason: stop.reason };
  const target = optionalPrice(src.targetPrice, tickSize);
  if (!target.ok) return { ok: false, reason: target.reason };
  const accountId = src.accountId == null ? '' : String(src.accountId).trim();
  const parentId = src.parentId == null || src.parentId === '' ? null : String(src.parentId);
  return {
    ok: true,
    order: {
      symbol,
      side,
      type,
      qty: qty.qty,
      price: price.price,
      stopPrice: stop.price,
      targetPrice: target.price,
      accountId,
      parentId
    }
  };
}

module.exports = {
  validatePrice,
  validateQty,
  validateOrder,
  isOnTick,
  normalizePrice,
  optionalPrice
};
