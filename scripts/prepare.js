/**
 * CraftFlow Desktop 文件准备脚本
 *
 * 从原始项目复制必要文件到 craftflow-desktop/，排除开发文件和缓存。
 */

const fs = require('fs');
const path = require('path');

const ROOT_DIR = path.resolve(__dirname, '..');
const TARGET_DIR = path.join(ROOT_DIR, 'craftflow-desktop');

/**
 * 递归复制目录
 */
function copyDirSync(src, dest, excludes = []) {
  if (!fs.existsSync(src)) {
    console.warn(`[跳过] 源目录不存在: ${src}`);
    return;
  }

  fs.mkdirSync(dest, { recursive: true });

  const entries = fs.readdirSync(src, { withFileTypes: true });

  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    // 检查是否在排除列表中
    if (excludes.includes(entry.name)) {
      console.log(`  [排除] ${entry.name}`);
      continue;
    }

    if (entry.isDirectory()) {
      copyDirSync(srcPath, destPath, excludes);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

/**
 * 复制单个文件
 */
function copyFileSync(src, dest) {
  if (!fs.existsSync(src)) {
    console.warn(`[跳过] 文件不存在: ${src}`);
    return;
  }

  const destDir = path.dirname(dest);
  fs.mkdirSync(destDir, { recursive: true });
  fs.copyFileSync(src, dest);
  console.log(`  [复制] ${path.basename(src)}`);
}

// ============================================
// 主流程
// ============================================

console.log('=== CraftFlow Desktop 文件准备 ===\n');

// 1. 复制后端源码
console.log('[1/4] 复制后端源码...');
const backendSrc = path.join(ROOT_DIR, 'craftflow-backend');
const backendDest = path.join(TARGET_DIR, 'backend');

// Desktop 独有文件/目录（保留）
const backendKeepList = ['desktop_config.py', '.venv'];

// 删除副本中不在保留列表中的文件
console.log('  清理 backend/...');
if (fs.existsSync(backendDest)) {
  const entries = fs.readdirSync(backendDest, { withFileTypes: true });
  for (const entry of entries) {
    if (backendKeepList.includes(entry.name)) {
      continue;
    }
    const fullPath = path.join(backendDest, entry.name);
    if (entry.isDirectory()) {
      fs.rmSync(fullPath, { recursive: true, force: true });
    } else {
      fs.unlinkSync(fullPath);
    }
    console.log(`    [删除] ${entry.name}`);
  }
}

// 复制 app/ 目录
console.log('  复制 app/...');
copyDirSync(
  path.join(backendSrc, 'app'),
  path.join(backendDest, 'app'),
  ['__pycache__']
);

// 复制配置文件
const backendFiles = [
  'pyproject.toml',
  'uv.lock',
  '.env.example',
  '.env.standalone',
  'README.md',
  'craftflow.spec',
];
for (const file of backendFiles) {
  copyFileSync(
    path.join(backendSrc, file),
    path.join(backendDest, file)
  );
}

// 2. 复制前端源码
console.log('\n[2/4] 复制前端源码...');
const frontendSrc = path.join(ROOT_DIR, 'craftflow-web');
const frontendDest = path.join(TARGET_DIR, 'frontend');

// Desktop 独有文件/目录（保留）
const frontendKeepList = ['.env.production'];

// 删除副本中不在保留列表中的文件
console.log('  清理 frontend/...');
if (fs.existsSync(frontendDest)) {
  const entries = fs.readdirSync(frontendDest, { withFileTypes: true });
  for (const entry of entries) {
    if (frontendKeepList.includes(entry.name)) {
      continue;
    }
    const fullPath = path.join(frontendDest, entry.name);
    if (entry.isDirectory()) {
      fs.rmSync(fullPath, { recursive: true, force: true });
    } else {
      fs.unlinkSync(fullPath);
    }
    console.log(`    [删除] ${entry.name}`);
  }
}

// 复制 src/ 目录
console.log('  复制 src/...');
copyDirSync(
  path.join(frontendSrc, 'src'),
  path.join(frontendDest, 'src'),
  ['__pycache__']
);

// 复制 public/ 目录
console.log('  复制 public/...');
copyDirSync(
  path.join(frontendSrc, 'public'),
  path.join(frontendDest, 'public')
);

// 复制配置文件
const frontendFiles = [
  'package.json',
  'package-lock.json',
  'tsconfig.json',
  'tsconfig.app.json',
  'tsconfig.node.json',
  'vite.config.ts',
  'index.html',
  'env.d.ts',
  '.gitignore',
];
for (const file of frontendFiles) {
  copyFileSync(
    path.join(frontendSrc, file),
    path.join(frontendDest, file)
  );
}

// 3. 创建前端 .env.production
console.log('\n[3/4] 创建前端环境配置...');
const envProduction = `VITE_API_BASE_URL=http://127.0.0.1:8000/api
VITE_WS_URL=ws://127.0.0.1:8000/ws
`;
fs.writeFileSync(path.join(frontendDest, '.env.production'), envProduction);
console.log('  [创建] .env.production');

// 4. 完成
console.log('\n[4/4] 完成！');
console.log(`\n目标目录: ${TARGET_DIR}`);
