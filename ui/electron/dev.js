const { spawn } = require('node:child_process');
const fs = require('node:fs');
const http = require('node:http');
const net = require('node:net');
const path = require('node:path');
const os = require('node:os');

const uiRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(uiRoot, '..');

const children = [];

function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
    server.on('error', reject);
  });
}

function run(name, command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: options.cwd || uiRoot,
    env: { ...process.env, ...(options.env || {}) },
    shell: process.platform === 'win32',
    stdio: 'inherit',
  });
  children.push(child);
  child.on('exit', (code, signal) => {
    if (signal) return;
    if (code !== 0) {
      console.error(`${name} exited with code ${code}`);
      shutdown(code);
    }
  });
  return child;
}

function waitFor(url, timeoutMs = 30000) {
  const startedAt = Date.now();
  return new Promise((resolve, reject) => {
    function probe() {
      const request = http.get(url, (response) => {
        response.resume();
        resolve();
      });
      request.on('error', () => {
        if (Date.now() - startedAt > timeoutMs) {
          reject(new Error(`Timed out waiting for ${url}`));
          return;
        }
        setTimeout(probe, 500);
      });
      request.setTimeout(1000, () => {
        request.destroy();
      });
    }
    probe();
  });
}

function shutdown(code = 0) {
  for (const child of children) {
    if (!child.killed) child.kill();
  }
  process.exit(code);
}

process.on('SIGINT', () => shutdown());
process.on('SIGTERM', () => shutdown());

async function main() {
  const apiPort = await getFreePort();
  const uiPort = await getFreePort();
  const apiUrl = `http://127.0.0.1:${apiPort}/api/project`;
  const uiUrl = `http://localhost:${uiPort}`;
  const userDataDir = path.join(os.tmpdir(), `snow-electron-${uiPort}`);

  console.log(`Starting Snow API on port ${apiPort}`);
  run('snow api', 'uv', ['run', 'snow', 'serve', '--port', String(apiPort)], { cwd: repoRoot });

  console.log(`Starting Angular dev server on port ${uiPort}`);
  run('angular', 'npm', ['run', 'start', '--', '--port', String(uiPort)], {
    cwd: uiRoot,
    env: { SNOW_API_URL: `http://127.0.0.1:${apiPort}` },
  });

  await waitFor(apiUrl);
  await waitFor(uiUrl);

  console.log('Opening Electron');
  const env = { SNOW_UI_URL: uiUrl, SNOW_USER_DATA_DIR: userDataDir };
  if (process.platform !== 'win32') {
    env.DBUS_SYSTEM_BUS_ADDRESS = '';
  }
  const electron = run('electron', 'npm', ['run', 'electron'], {
    cwd: uiRoot,
    env,
  });
  electron.on('exit', () => shutdown());
}

main().catch((error) => {
  console.error(error.message);
  shutdown(1);
});
