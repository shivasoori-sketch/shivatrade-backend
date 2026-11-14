(function (root, factory) {
  var api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.Mc325WsClient = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
  function createWsClient(options) {
    var opts = options || {};
    var WS = opts.WebSocket || root.WebSocket;
    var schedule = opts.schedule || function (fn, ms) { return setTimeout(fn, ms); };
    var url = opts.url;
    var getToken = opts.getToken || function () { return ''; };
    var backoff = 500;
    var maxBackoff = 8000;
    var queue = [];
    var socket = null;
    var authed = false;
    var closedByUser = false;
    var reconnecting = false;
    var listeners = {};

    function emit(type, payload) {
      var list = listeners[type] || [];
      list.forEach(function (fn) { fn(payload); });
    }

    function on(type, fn) {
      if (!listeners[type]) listeners[type] = [];
      listeners[type].push(fn);
      return function () {
        listeners[type] = listeners[type].filter(function (item) { return item !== fn; });
      };
    }

    function sendRaw(msg) {
      socket.send(JSON.stringify(msg));
    }

    function flush() {
      if (!socket || socket.readyState !== 1 || !authed) return;
      var pending = queue.splice(0, queue.length);
      pending.forEach(sendRaw);
    }

    function send(msg) {
      if (socket && socket.readyState === 1 && authed) {
        sendRaw(msg);
        return true;
      }
      queue.push(msg);
      return false;
    }

    function scheduleReconnect() {
      if (reconnecting || closedByUser) return;
      reconnecting = true;
      var wait = backoff;
      backoff = Math.min(maxBackoff, backoff * 2);
      schedule(function () {
        reconnecting = false;
        connect();
      }, wait);
    }

    function bind(sock) {
      sock.onopen = function () {
        authed = false;
        sock.send(JSON.stringify({ type: 'auth', token: getToken() }));
      };
      sock.onmessage = function (event) {
        var msg;
        try {
          msg = JSON.parse(event.data);
        } catch (err) {
          return;
        }
        if (msg && msg.type === 'auth_ok') {
          authed = true;
          backoff = 500;
          emit('status', 'live');
          flush();
        } else if (msg && msg.type === 'auth_reject') {
          authed = false;
          emit('status', 'offline');
        }
        emit('message', msg);
      };
      sock.onclose = function () {
        authed = false;
        if (socket === sock) socket = null;
        emit('status', 'offline');
        if (!closedByUser) scheduleReconnect();
      };
      sock.onerror = function () {
        emit('status', 'offline');
      };
    }

    function connect() {
      closedByUser = false;
      if (socket && (socket.readyState === 0 || socket.readyState === 1)) return;
      emit('status', 'connecting');
      socket = new WS(url);
      if (socket.readyState == null) socket.readyState = 0;
      bind(socket);
    }

    function close() {
      closedByUser = true;
      reconnecting = false;
      if (socket && typeof socket.close === 'function') socket.close();
      socket = null;
      authed = false;
    }

    return {
      connect: connect,
      close: close,
      send: send,
      on: on,
      getQueue: function () { return queue.slice(); },
      isAuthed: function () { return authed; }
    };
  }

  return { createWsClient: createWsClient };
});
