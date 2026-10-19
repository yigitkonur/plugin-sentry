const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('app', { version: '1.0.0' });
