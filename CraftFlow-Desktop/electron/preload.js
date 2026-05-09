/**
 * CraftFlow Desktop - 预加载脚本
 *
 * 通过 contextBridge 暴露安全的 API 给渲染进程。
 */

const { contextBridge } = require('electron');

// 暴露给渲染进程的 API
contextBridge.exposeInMainWorld('electronAPI', {
  // 平台信息
  platform: process.platform,

  // 后端配置
  backend: {
    host: '127.0.0.1',
    port: 8000,
  },

  // 应用信息
  app: {
    name: 'CraftFlow',
    version: '0.1.0',
  },
});
