const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('snowShell', {
  pickDirectory(options) {
    return ipcRenderer.invoke('pick-directory', options);
  },
});

// Intercept link clicks to open external URLs in browser
document.addEventListener('click', (event) => {
  const target = event.target.closest('a');
  if (!target) return;

  const href = target.getAttribute('href');
  if (!href) return;

  // Check if it's an external URL
  if (href.startsWith('http://') || href.startsWith('https://')) {
    event.preventDefault();
    event.stopPropagation();
    ipcRenderer.send('open-external', href);
  }
}, true);
