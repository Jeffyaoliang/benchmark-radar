// A missing generated Models page cannot run app.js. Enter through the root
// document instead; its router restores the clean path without another request.
// replace keeps Back from revisiting the failed entry. Unknown paths stay 404s.
(() => {
  if (!["/models", "/models/"].includes(window.location.pathname)) return;
  const target = new URL("/", window.location.origin);
  target.search = window.location.search;
  target.searchParams.set("view", "models");
  target.hash = window.location.hash;
  window.location.replace(target.href);
})();
