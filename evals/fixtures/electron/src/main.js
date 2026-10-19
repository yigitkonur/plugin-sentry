const Sentry = require('@sentry/electron/main');
const { app, BrowserWindow } = require('electron');
const path = require('path');

Sentry.init({ dsn: 'https://0123456789abcdef0123456789abcdef@o123456.ingest.us.sentry.io/1234567' });

function createWindow() {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: { preload: path.join(__dirname, 'preload.js') },
  });
  win.loadFile('index.html');
}

app.whenReady().then(createWindow);
