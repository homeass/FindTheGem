const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

let mainWindow = null;
let streamlitProcess = null;
let isQuitting = false;
let loadingWindow = null;

const STREAMLIT_PORT = 8501;
const STREAMLIT_URL = `http://localhost:${STREAMLIT_PORT}`;
const MAX_STARTUP_WAIT = 30000; // 30 seconds
const POLL_INTERVAL = 1000; // 1 second

const PROJECT_ROOT = '/Users/kyuhwanlee/Code/Agent-Reach';
const VENV_PYTHON = path.join(PROJECT_ROOT, '.venv', 'bin', 'python');
const STREAMLIT_APP = path.join(PROJECT_ROOT, 'findthegem_app.py');

function createLoadingWindow() {
  loadingWindow = new BrowserWindow({
    width: 500,
    height: 400,
    frame: false,
    transparent: true,
    resizable: false,
    alwaysOnTop: true,
    center: true,
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  loadingWindow.loadFile(path.join(__dirname, 'loading.html'));
  
  loadingWindow.once('ready-to-show', () => {
    loadingWindow.show();
  });

  loadingWindow.on('closed', () => {
    loadingWindow = null;
  });
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 1000,
    minHeight: 700,
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 15, y: 15 },
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: true,
      allowRunningInsecureContent: false
    },
    icon: path.join(__dirname, 'icon.icns')
  });

  mainWindow.loadURL(STREAMLIT_URL);

  mainWindow.once('ready-to-show', () => {
    if (loadingWindow) {
      loadingWindow.close();
      loadingWindow = null;
    }
    mainWindow.show();
    mainWindow.focus();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    require('electron').shell.openExternal(url);
    return { action: 'deny' };
  });

  // Handle navigation
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (url !== STREAMLIT_URL && !url.startsWith(STREAMLIT_URL)) {
      event.preventDefault();
      require('electron').shell.openExternal(url);
    }
  });
}

function spawnStreamlitServer() {
  return new Promise((resolve, reject) => {
    console.log('Starting Streamlit server...');
    console.log(`Python: ${VENV_PYTHON}`);
    console.log(`App: ${STREAMLIT_APP}`);
    console.log(`Working dir: ${PROJECT_ROOT}`);

    streamlitProcess = spawn(VENV_PYTHON, [
      '-m', 'streamlit', 'run', STREAMLIT_APP,
      '--server.port', STREAMLIT_PORT.toString(),
      '--server.headless', 'true',
      '--browser.gatherUsageStats', 'false',
      '--server.enableCORS', 'false',
      '--server.enableXsrfProtection', 'false'
    ], {
      cwd: PROJECT_ROOT,
      env: {
        ...process.env,
        PYTHONPATH: PROJECT_ROOT,
        STREAMLIT_SERVER_PORT: STREAMLIT_PORT.toString(),
        STREAMLIT_SERVER_HEADLESS: 'true',
        STREAMLIT_BROWSER_GATHER_USAGE_STATS: 'false'
      },
      stdio: ['ignore', 'pipe', 'pipe']
    });

    streamlitProcess.stdout.on('data', (data) => {
      const output = data.toString();
      console.log(`[Streamlit] ${output.trim()}`);
      if (output.includes('You can now view your Streamlit app') || 
          output.includes('Local URL:') ||
          output.includes('Network URL:')) {
        console.log('Streamlit server appears to be ready');
      }
    });

    streamlitProcess.stderr.on('data', (data) => {
      console.error(`[Streamlit Error] ${data.toString().trim()}`);
    });

    streamlitProcess.on('error', (err) => {
      console.error('Failed to start Streamlit process:', err);
      reject(err);
    });

    streamlitProcess.on('exit', (code, signal) => {
      console.log(`Streamlit process exited with code ${code}, signal ${signal}`);
      streamlitProcess = null;
    });

    // Wait for server to be ready
    waitForServerReady()
      .then(resolve)
      .catch(reject);
  });
}

function waitForServerReady() {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();
    
    const checkServer = () => {
      http.get(STREAMLIT_URL, (res) => {
        if (res.statusCode === 200) {
          console.log('Streamlit server is ready!');
          resolve();
        } else {
          scheduleCheck();
        }
      }).on('error', () => {
        scheduleCheck();
      });
    };

    const scheduleCheck = () => {
      if (Date.now() - startTime > MAX_STARTUP_WAIT) {
        reject(new Error(`Streamlit server failed to start within ${MAX_STARTUP_WAIT}ms`));
        return;
      }
      setTimeout(checkServer, POLL_INTERVAL);
    };

    // Initial delay before first check
    setTimeout(checkServer, 2000);
  });
}

function killStreamlitServer() {
  if (streamlitProcess) {
    console.log('Stopping Streamlit server...');
    streamlitProcess.kill('SIGTERM');
    
    // Force kill after 3 seconds
    setTimeout(() => {
      if (streamlitProcess) {
        console.log('Force killing Streamlit server...');
        streamlitProcess.kill('SIGKILL');
        streamlitProcess = null;
      }
    }, 3000);
  }
}

function setupAppEvents() {
  app.on('ready', async () => {
    app.setName('Find the Gem');
    
    createLoadingWindow();
    
    try {
      await spawnStreamlitServer();
      createMainWindow();
    } catch (error) {
      console.error('Failed to start Streamlit server:', error);
      if (loadingWindow) {
        loadingWindow.webContents.send('server-error', error.message);
      }
      dialog.showErrorBox(
        'Failed to Start Research Engine',
        `Could not start the Streamlit server:\n${error.message}\n\nPlease ensure the virtual environment is set up correctly.`
      );
      app.quit();
    }
  });

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
      killStreamlitServer();
      app.quit();
    }
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0 && !isQuitting) {
      createMainWindow();
    }
  });

  app.on('before-quit', (event) => {
    isQuitting = true;
    killStreamlitServer();
  });

  app.on('will-quit', () => {
    killStreamlitServer();
  });
}

// IPC handlers
ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

ipcMain.handle('get-streamlit-url', () => {
  return STREAMLIT_URL;
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught exception:', error);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled rejection at:', promise, 'reason:', reason);
});

setupAppEvents();