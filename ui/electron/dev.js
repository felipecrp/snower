const { spawn } = require('node:child_process');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');

const uiRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(uiRoot, '..');
const apiUrl = process.env.SNOW_API_URL || 'http://127.0.0.1:8000/api/project';
const uiUrl = process.env.SNOW_UI_URL || 'http://localhost:4200';

const children = [];

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
  console.log('Starting Snow API');
  run('snow api', 'uv', ['run', 'snow', 'serve'], { cwd: repoRoot });

  console.log('Starting Angular dev server');
  run('angular', 'npm', ['run', 'start'], { cwd: uiRoot });

  await waitFor(apiUrl);
  await waitFor(uiUrl);

  console.log('Opening Electron');
  const electron = run('electron', 'npm', ['run', 'electron'], {
    cwd: uiRoot,
    env: { SNOW_UI_URL: uiUrl },
  });
  electron.on('exit', () => shutdown());
}

main().catch((error) => {
  console.error(error.message);
  shutdown(1);
});
