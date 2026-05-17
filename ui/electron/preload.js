const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('snowShell', {
  pickDirectory(options) {
    return ipcRenderer.invoke('pick-directory', options);
  },
});
