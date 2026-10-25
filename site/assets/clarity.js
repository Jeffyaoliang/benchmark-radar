// Clarity records session replays, so it must not load before the visitor opts
// in (GDPR consent, and California CIPA treats unconsented replay as
// wiretapping). The choice lives in localStorage; without a stored "granted"
// the tag is never requested.
(function () {
  const STORAGE_KEY = "benchmark-radar:analytics-consent";
  const PROJECT_ID = "ya4h95jvfj";

  function readChoice() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  }

  function storeChoice(value) {
    try {
      if (value === null) window.localStorage.removeItem(STORAGE_KEY);
      else window.localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // Storage blocked: the choice holds for this page view only.
    }
  }

  function loadClarity() {
    if (window.clarity) return;
    (function (c, l, a, r, i, t, y) {
      c[a] =
        c[a] ||
        function () {
          (c[a].q = c[a].q || []).push(arguments);
        };
      t = l.createElement(r);
      t.async = 1;
      t.src = `https://www.clarity.ms/tag/${i}`;
      y = l.getElementsByTagName(r)[0];
      y.parentNode.insertBefore(t, y);
    })(window, document, "clarity", "script", PROJECT_ID);
    window.clarity("consentv2", { ad_Storage: "denied", analytics_Storage: "granted" });
  }

  function closeBanner() {
    document.getElementById("analytics-consent")?.remove();
  }

  function choose(value) {
    const wasGranted = readChoice() === "granted";
    storeChoice(value);
    closeBanner();
    if (value === "granted") {
      loadClarity();
    } else if (wasGranted && window.clarity) {
      // Withdrawal: tell Clarity to drop its cookies, then reload so the
      // already-running recorder is gone.
      window.clarity("consentv2", { ad_Storage: "denied", analytics_Storage: "denied" });
      window.clarity("consent", false);
      window.location.reload();
    }
  }

  function showBanner() {
    if (document.getElementById("analytics-consent")) return;
    const banner = document.createElement("section");
    banner.id = "analytics-consent";
    banner.className = "analytics-consent";
    banner.setAttribute("role", "region");
    banner.setAttribute("aria-label", "Analytics consent");
    banner.innerHTML = `
      <p data-i18n="analytics-consent-text">
        May we use Microsoft Clarity to record session replays and heatmaps of your visit? They help us
        improve navigation. Nothing is recorded unless you accept.
        <a href="https://privacy.microsoft.com/privacystatement">Microsoft Privacy Statement</a>
      </p>
      <div class="analytics-consent-actions">
        <button type="button" data-consent="denied" data-i18n="Decline">Decline</button>
        <button type="button" data-consent="granted" data-i18n="Accept">Accept</button>
      </div>`;
    banner.addEventListener("click", (event) => {
      const button = event.target.closest("[data-consent]");
      if (button) choose(button.dataset.consent);
    });
    document.body.append(banner);
  }

  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-analytics-consent-reset]")) {
      event.preventDefault();
      showBanner();
    }
  });

  const choice = readChoice();
  if (choice === "granted") loadClarity();
  else if (choice !== "denied") showBanner();
})();
