const Sentry = require('@sentry/electron/renderer');

Sentry.init({});

document.getElementById('title').textContent = 'Electron App ' + window.app.version;
