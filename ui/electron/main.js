const path = require('path');
const { app, BrowserWindow, dialog, ipcMain, screen, shell } = require('electron');

if (process.env.SNOW_USER_DATA_DIR) {
  app.setPath('userData', process.env.SNOW_USER_DATA_DIR);
  app.setPath('sessionData', path.join(process.env.SNOW_USER_DATA_DIR, 'session'));
}

const TARGET_URL = process.env.SNOW_UI_URL || 'http://localhost:4200';
const BG = '#f8fafc';
const isMac = process.platform === 'darwin';

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

ipcMain.on('window-minimize', (event) => {
  BrowserWindow.fromWebContents(event.sender)?.minimize();
});

ipcMain.on('window-maximize-toggle', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (!win) return;
  if (win.snowMaximized) {
    if (win.snowRestoreBounds) win.setBounds(win.snowRestoreBounds);
    win.snowMaximized = false;
  } else {
    win.snowRestoreBounds = win.getBounds();
    const { workArea } = screen.getDisplayMatching(win.getBounds());
    win.setBounds(workArea);
    win.snowMaximized = true;
  }
  win.webContents.send('window-maximized', win.snowMaximized);
});

ipcMain.on('window-close', (event) => {
  BrowserWindow.fromWebContents(event.sender)?.close();
});

function createWindow() {
  const frameOptions = isMac
    ? { titleBarStyle: 'hiddenInset' }
    : { frame: false };

  const win = new BrowserWindow({
    title: 'Snow',
    width: 1400,
    height: 900,
    show: false,
    backgroundColor: BG,
    icon: path.join(__dirname, '..', 'public', 'favicon.ico'),
    ...frameOptions,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  win.once('ready-to-show', () => win.show());


  win.setMenuBarVisibility(false);
  win.loadURL(TARGET_URL).catch(() => {
    win.loadURL(
      `data:text/html;charset=utf-8,${encodeURIComponent(`
        <html>
          <body style="background:${BG};font-family:system-ui,sans-serif;padding:32px;">
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
