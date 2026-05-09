/**
 * CraftFlow Desktop - Electron 主进程
 *
 * 职责：
 * 1. 启动 PyInstaller 打包的后端子进程
 * 2. 等待后端就绪（轮询 /health）
 * 3. 创建 BrowserWindow 加载前端
 * 4. 应用退出时关闭后端子进程
 */

const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

// 全局引用
let mainWindow = null;
let backendProcess = null;
let splashWindow = null;

// 后端配置
const BACKEND_PORT = 8000;
const BACKEND_HOST = '127.0.0.1';
const HEALTH_CHECK_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}/health`;
const MAX_RETRIES = 30;
const RETRY_INTERVAL = 1000; // 1 秒

/**
 * 获取后端可执行文件路径
 */
function getBackendPath() {
  const isDev = !app.isPackaged;

  if (isDev) {
    // 开发环境：假设后端在 CraftFlow-Desktop/backend/dist/craftflow/
    return path.join(__dirname, '..', 'backend', 'dist', 'craftflow', 'craftflow.exe');
  }

  // 生产环境：从 resources 目录读取
  return path.join(process.resourcesPath, 'backend', 'craftflow.exe');
}

/**
 * 启动后端子进程
 */
function startBackend() {
  const backendPath = getBackendPath();
  const backendDir = path.dirname(backendPath);

  console.log(`[Electron] 启动后端: ${backendPath}`);

  backendProcess = spawn(backendPath, [], {
    cwd: backendDir,
    env: {
      ...process.env,
      ENVIRONMENT: 'production',
    },
    windowsHide: true, // 隐藏后端控制台窗口
  });

  backendProcess.stdout.on('data', (data) => {
    console.log(`[Backend] ${data.toString().trim()}`);
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`[Backend] ${data.toString().trim()}`);
  });

  backendProcess.on('error', (err) => {
    console.error('[Electron] 后端启动失败:', err);
    showErrorDialog('后端启动失败', err.message);
  });

  backendProcess.on('exit', (code, signal) => {
    console.log(`[Electron] 后端已退出 (code: ${code}, signal: ${signal})`);
    backendProcess = null;

    // 如果是意外退出，显示错误
    if (code !== 0 && code !== null) {
      showErrorDialog('后端异常退出', `后端进程以代码 ${code} 退出`);
    }
  });
}

/**
 * 等待后端就绪
 */
async function waitForBackend() {
  console.log('[Electron] 等待后端就绪...');

  for (let i = 0; i < MAX_RETRIES; i++) {
    try {
      await new Promise((resolve, reject) => {
        http.get(HEALTH_CHECK_URL, (res) => {
          if (res.statusCode === 200) {
            resolve();
          } else {
            reject(new Error(`状态码: ${res.statusCode}`));
          }
        }).on('error', reject);
      });

      console.log('[Electron] 后端已就绪');
      return true;
    } catch {
      // 继续重试
      await new Promise(r => setTimeout(r, RETRY_INTERVAL));
    }
  }

  console.error('[Electron] 后端启动超时');
  return false;
}

/**
 * 创建启动画面
 */
function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: 400,
    height: 300,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  splashWindow.loadFile(path.join(__dirname, 'splash.html'));
  splashWindow.center();
}

/**
 * 创建主窗口
 */
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 768,
    show: false, // 先隐藏，等加载完成后再显示
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // 加载前端
  const isDev = !app.isPackaged;

  if (isDev) {
    // 开发环境：加载构建产物
    mainWindow.loadFile(path.join(__dirname, '..', 'frontend', 'dist', 'index.html'));
  } else {
    // 生产环境
    mainWindow.loadFile(path.join(process.resourcesPath, 'frontend', 'index.html'));
  }

  // 页面加载完成后显示
  mainWindow.once('ready-to-show', () => {
    if (splashWindow) {
      splashWindow.close();
      splashWindow = null;
    }
    mainWindow.show();
  });

  // 窗口关闭时清理
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

/**
 * 显示错误对话框
 */
function showErrorDialog(title, message) {
  dialog.showErrorBox(title, message);
  app.quit();
}

/**
 * 关闭后端子进程
 */
function killBackend() {
  if (backendProcess) {
    console.log('[Electron] 关闭后端进程...');
    backendProcess.kill();

    // 等待进程退出
    setTimeout(() => {
      if (backendProcess) {
        backendProcess.kill('SIGKILL');
      }
    }, 5000);
  }
}

// ============================================
// 应用生命周期
// ============================================

app.whenReady().then(async () => {
  // 显示启动画面
  createSplashWindow();

  // 启动后端
  startBackend();

  // 等待后端就绪
  const ready = await waitForBackend();

  if (!ready) {
    showErrorDialog(
      '启动失败',
      '后端服务启动超时，请检查日志或重启应用。'
    );
    return;
  }

  // 创建主窗口
  createMainWindow();
});

app.on('window-all-closed', () => {
  killBackend();
  app.quit();
});

app.on('before-quit', () => {
  killBackend();
});

app.on('activate', () => {
  // macOS: 点击 dock 图标时重新创建窗口
  if (mainWindow === null) {
    createMainWindow();
  }
});
