'use strict';

/**
 * Broker boundary. Only MockBrokerAdapter is implemented.
 * Market orders fill immediately in memory. Nothing is sent to a venue.
 */
class IBrokerAdapter {
  place() {
    throw new Error('IBrokerAdapter.place is not implemented');
  }

  modify() {
    throw new Error('IBrokerAdapter.modify is not implemented');
  }

  cancel() {
    throw new Error('IBrokerAdapter.cancel is not implemented');
  }
}

class MockBrokerAdapter extends IBrokerAdapter {
  place(order) {
    if (order.type === 'MARKET') {
      return {
        status: 'FILLED',
        filledQty: order.qty,
        avgPrice: order.price
      };
    }
    return {
      status: 'OPEN',
      filledQty: 0,
      avgPrice: 0
    };
  }

  modify(order, patch) {
    return {
      price: patch.price != null ? patch.price : order.price,
      qty: patch.qty != null ? patch.qty : order.qty,
      stopPrice: Object.prototype.hasOwnProperty.call(patch, 'stopPrice') ? patch.stopPrice : order.stopPrice,
      targetPrice: Object.prototype.hasOwnProperty.call(patch, 'targetPrice') ? patch.targetPrice : order.targetPrice
    };
  }

  cancel() {
    return { status: 'CANCELLED' };
  }
}

module.exports = {
  IBrokerAdapter,
  MockBrokerAdapter
};
