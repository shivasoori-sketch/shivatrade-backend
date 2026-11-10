/**
 * KD slot replacement — feature flag until single-cutover deploy.
 * ?card=thesis | ?card=kd · persists in localStorage `shivatrade_conviction_card`.
 */
(function installConvictionSlot() {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("card");
  if (fromQuery === "thesis" || fromQuery === "kd") {
    localStorage.setItem("shivatrade_conviction_card", fromQuery);
  }
  const mode =
    localStorage.getItem("shivatrade_conviction_card") ||
    window.SHIVATRADE_CONVICTION_CARD ||
    "kd";

  const kdRoot = document.getElementById("kd-card-root");
  const thesisRoot = document.getElementById("thesis-card-root");

  if (mode === "thesis") {
    if (kdRoot) {
      kdRoot.setAttribute("data-thesis-replaced", "1");
      kdRoot.hidden = true;
    }
    if (thesisRoot) thesisRoot.hidden = false;
    return;
  }

  if (thesisRoot) thesisRoot.hidden = true;
})();
