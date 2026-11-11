# RPX shadow read path (Upstox migration)

RPX V2 (`/opt/shivtrade/research/kaaldrishti-feed/kd_rpx.py`) does **not** read tick files directly. It consumes `participation_evolution` on the KD assess payload after PGE attaches V2 scores.

## Cutover checklist (post–shadow validation)

1. **Fabric buckets:** Point PGE V2 / kd feed hooks at ` /opt/shivtrade/upstox_migration/state/fabric_buckets/` JSON files (`schema: upstox.fabric.stream_bucket.v1`). Fields align with `stream_capture_fabric.candle()` (`open/high/low/close`, `half_bucket_ticks`, `instrument_token`).
2. **Tick cache:** PulseGuard / `live_ltp_engine` reads `latest_tick_cache.json` via `shivtrade_ws_market_data.load_ws_quotes`. Shadow cache: `/opt/shivtrade/upstox_migration/state/latest_tick_cache.json` with `NSE:NIFTY 50`, `NSE:NIFTY BANK`, `BSE:SENSEX` keys and `received_at` UTC ISO.
3. **RPX validation:** Run `kd_rpx.attach_rpx_v2` on synthetic payload where `participation_evolution.state` is derived from Upstox fabric bucket density (tick_count / half_bucket_ticks), not spot direction.
4. **Do not** repoint live SLM/PGE bridge (`:5074`) or PG publication-render in shadow phase.

## Quick probe

```bash
python3 -c "
import json,glob
p=sorted(glob.glob('/opt/shivtrade/upstox_migration/state/fabric_buckets/*.json'))[-1:]
print(p)
if p: print(json.load(open(p[0])))
"
```
