function formatTime(isoOrMs) {
  if (!isoOrMs) return "—";
  const d = typeof isoOrMs === "number" ? new Date(isoOrMs) : new Date(isoOrMs);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function stateClass(state) {
  if (state === "HOLDS") return "thesis-badge holds";
  if (state === "WEAKENING") return "thesis-badge weakening";
  if (state === "INVALIDATED") return "thesis-badge invalidated";
  return "thesis-badge idle";
}

function bookAlignment(book) {
  if (!book) return "—";
  if (book.divergence_flag) return "diverging";
  if (book.sweep_risk) return "sweep risk";
  return "aligned";
}

export default function ThesisCard({
  trade,
  state,
  book,
  lastUpdated,
  timeInTradeLabel = "—",
  adversePts = "—",
  idle = false,
  previewHref,
  previewBanner,
}) {
  if (idle || !trade) {
    return (
      <div className="thesis-card thesis-card-idle">
        <header className="thesis-head">
          <span className="thesis-title">THESIS</span>
          <span className={stateClass("IDLE")}>No trade</span>
        </header>
        <p className="thesis-idle-copy">
          Lock a thesis to track hold integrity. Conviction changes only when your thesis
          changes — not when price twitches.
        </p>
        {previewHref ? (
          <p className="thesis-idle-preview">
            <a href={previewHref}>Preview live hold UI</a>
          </p>
        ) : null}
      </div>
    );
  }

  const verdict = state?.state || "HOLDS";
  const barPct = book ? Math.min(100, Math.max(0, book.book_score)) : 0;

  return (
    <div className={`thesis-card verdict-${verdict.toLowerCase()}`}>
      {previewBanner ? (
        <p className="thesis-preview-banner" role="note">
          {previewBanner}
        </p>
      ) : null}
      <header className="thesis-head">
        <span className="thesis-title">THESIS</span>
        <span className={stateClass(verdict)} role="status">
          {verdict}
        </span>
        <time className="thesis-time" dateTime={String(lastUpdated)}>
          {formatTime(lastUpdated)}
        </time>
      </header>
      {state?.annotation ? (
        <p className="thesis-annotation" role="note">
          {state.annotation}
        </p>
      ) : null}

      <section className="thesis-book" aria-label="Book divergence">
        <div className="thesis-book-row">
          <span>
            BOOK: {book ? book.book_score : "—"} / 100
          </span>
          <span className="thesis-book-align">{bookAlignment(book)}</span>
        </div>
        <div
          className="thesis-bar"
          role="meter"
          aria-valuenow={barPct}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <span className="thesis-bar-fill" style={{ width: `${barPct}%` }} />
        </div>
      </section>

      <section className="thesis-checklist">
        <h2 className="thesis-section-label">Thesis checklist</h2>
        <ul>
          {(state?.conditions || []).map((c) => (
            <li key={c.id}>
              <span className={c.met ? "chk-ok" : "chk-warn"} aria-hidden>
                {c.met ? "✅" : "⚠️"}
              </span>
              <span>{c.label}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="thesis-levels" aria-label="Entry levels">
        <div>
          Entry <strong>{trade.entry_price}</strong>
        </div>
        <div>
          SL <strong>{trade.stop_loss}</strong>
        </div>
        <div>
          TGT <strong>{trade.target}</strong>
        </div>
      </section>
      <section className="thesis-meta">
        <div>
          Time <strong>{timeInTradeLabel}</strong>
        </div>
        <div>
          Adverse <strong>{adversePts} pts</strong>
        </div>
      </section>

      <footer className="thesis-decision">
        DECISION: <strong>{state?.decision_line || "HOLD"}</strong>
      </footer>
      {state?.data_stale ? (
        <p className="thesis-stale" role="note">
          Feed gap detected — data marked stale; verdict unchanged until thesis rules fire.
        </p>
      ) : null}
    </div>
  );
}
