const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  onServerError: (callback) => {
    ipcRenderer.on('server-error', (_, error) => callback(error));
  },
  onServerReady: (callback) => {
    ipcRenderer.on('server-ready', () => callback());
  },
  getVersion: () => ipcRenderer.invoke('get-version'),
  quitApp: () => ipcRenderer.invoke('quit-app'),
  minimizeWindow: () => ipcRenderer.invoke('minimize-window'),
  maximizeWindow: () => ipcRenderer.invoke('maximize-window'),
  isMaximized: () => ipcRenderer.invoke('is-maximized'),
});

contextBridge.exposeInMainWorld('appInfo', {
  name: 'Find the Gem',
  version: '1.0.0',
  platform: process.platform,
});

window.addEventListener('DOMContentLoaded', () => {
  const replaceText = (selector, text) => {
    const element = document.getElementById(selector);
    if (element) element.innerText = text;
  };

  for (const dependency of ['chrome', 'node', 'electron']) {
    replaceText(`${dependency}-version`, process.versions[dependency]);
  }
});