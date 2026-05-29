const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('snowShell', {
  isElectron: true,
  platform: process.platform,

  pickDirectory(options) {
    return ipcRenderer.invoke('pick-directory', options);
  },

  minimize() {
    ipcRenderer.send('window-minimize');
  },

  maximizeToggle() {
    ipcRenderer.send('window-maximize-toggle');
  },

  close() {
    ipcRenderer.send('window-close');
  },

  onMaximizeChange(cb) {
    ipcRenderer.on('window-maximized', (_event, isMaximized) => cb(isMaximized));
  },
});

// Intercept link clicks to open external URLs in browser
document.addEventListener('click', (event) => {
  const target = event.target.closest('a');
  if (!target) return;

  const href = target.getAttribute('href');
  if (!href) return;

  if (href.startsWith('http://') || href.startsWith('https://')) {
    event.preventDefault();
    event.stopPropagation();
    ipcRenderer.send('open-external', href);
  }
}, true);
