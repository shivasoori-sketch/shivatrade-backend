/** Live card book line gated until Gate 2 (adviser). Demo fixtures may still show BOOK. */
export function bookLineEnabledForLive() {
  if (typeof window === "undefined") return false;
  return window.THESIS_BOOK_LINE_ENABLED === true;
}

export const BOOK_PENDING_COPY =
  "Awaiting candle close — book score updates on 1m close.";
