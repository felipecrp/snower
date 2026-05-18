const path = require('path');
const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');

if (process.env.SNOW_USER_DATA_DIR) {
  app.setPath('userData', process.env.SNOW_USER_DATA_DIR);
  app.setPath('sessionData', path.join(process.env.SNOW_USER_DATA_DIR, 'session'));
}

const TARGET_URL = process.env.SNOW_UI_URL || 'http://localhost:4200';

ipcMain.handle('pick-directory', async (_event, options = {}) => {
  const result = await dialog.showOpenDialog({
    title: options.title || 'Choose folder',
    defaultPath: options.defaultPath || undefined,
    properties: ['openDirectory'],
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  return result.filePaths[0];
});

ipcMain.on('open-external', (_event, url) => {
  shell.openExternal(url);
});

function createWindow() {
  const win = new BrowserWindow({
    title: 'Snow',
    width: 1400,
    height: 900,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  win.setMenuBarVisibility(false);
  win.loadURL(TARGET_URL).catch(() => {
    win.loadURL(
      `data:text/html;charset=utf-8,${encodeURIComponent(`
        <html>
          <body style="font-family: system-ui, sans-serif; padding: 32px;">
            <h1>Snow UI is not available</h1>
            <p>Start Angular with <code>npm run start</code>, or use <code>npm run electron:dev</code>.</p>
          </body>
        </html>
      `)}`,
    );
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
