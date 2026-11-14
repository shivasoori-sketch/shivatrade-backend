# MC325 direct chart trading (mock)

Paper orders only. The process uses `MockBrokerAdapter`, which fills market orders in memory. It does not call a broker and it is not for the live VPS.

## Run

```bash
cd server
cp .env.example .env
npm install
npm start
```

HTTP listens on `127.0.0.1:6161`. WebSocket listens on `127.0.0.1:6162/ws`. One process, no cluster.

## Env

| Name | Role |
| --- | --- |
| `PORT` | HTTP port |
| `WS_PORT` | WebSocket port |
| `JWT_SECRET` | Server-only signing secret. Never put this in the chart page. |
| `TICK_SIZE` | Minimum price step |
| `LOT_SIZE` | Quantity step |

The chart asks `POST /api/session` with a paper user id and gets a token back. The secret stays on the server.

## HTTP

- `POST /api/session` `{ "userId": "paper" }`
- `GET /api/accounts`
- `GET /api/orders`
- `GET /api/positions`
- `POST /api/orders`
- `PATCH /api/orders/:id`
- `DELETE /api/orders/:id`

Send `Authorization: Bearer <token>` on the account, order, and position routes.

## WebSocket

Connect to `ws://127.0.0.1:6162/ws`. Messages are JSON with a `type`. The first message must be:

```json
{ "type": "auth", "token": "<paper token>" }
```

Later messages use `place_order`, `modify_order`, `cancel_order`, `cancel_all`, `get_orders`, and `get_positions`. The server broadcasts `order_update` and `positions`. A rejected modify comes back as `{ "type": "reject" }`.

## Chart page

Static modules are served at `/mc325/trading/`. On `localhost` the existing MC325 chart script loads them and adds the order overlay, toolbar, and ticket. It does not replace the chart. On the production host it does not open a connection unless `window.MC325_TRADING_BASE` is set to this server.

Prices on the chart come from the chart itself. This server does not poll a price feed.
