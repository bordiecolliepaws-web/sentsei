// Legacy entry point kept for compatibility with tests and service worker.
// The real application logic now lives in ES modules under static/js/.
// This file is still served at /app.js but is not used by the UI.

// No-op shim to satisfy old tooling that expects a JS file here.
(function(){
  window.__sentsei_legacy_stub__ = true;
})();
