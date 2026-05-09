# -*- mode: python ; coding: utf-8 -*-
"""
CraftFlow 后端 PyInstaller 打包配置

使用目录模式（COLLECT）而非单文件模式（--onefile），
因为 LangGraph/LangChain 的隐式导入较多，单文件模式启动慢且容易遗漏模块。
"""

import sys
from pathlib import Path

block_cipher = None

# 源码根目录
src_root = Path(SPECPATH)

a = Analysis(
    # 入口文件
    [str(src_root / 'app' / 'main.py')],

    # 搜索路径
    pathex=[str(src_root)],

    # 二进制文件（通常为空）
    binaries=[],

    # 数据文件：复制 app/ 和 .env.example 到打包目录
    datas=[
        (str(src_root / 'app'), 'app'),
        (str(src_root / '.env.example'), '.'),
        (str(src_root / 'desktop_config.py'), '.'),
    ],

    # 隐式导入：PyInstaller 无法自动检测的模块
    hiddenimports=[
        # FastAPI
        'fastapi',
        'fastapi.responses',
        'fastapi.requests',
        'fastapi.exceptions',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'fastapi.staticfiles',
        'starlette',
        'starlette.responses',
        'starlette.requests',
        'starlette.middleware',
        'starlette.middleware.cors',
        'starlette.routing',
        'starlette.exceptions',

        # Uvicorn
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',

        # AioSQLite
        'aiosqlite',

        # LangGraph
        'langgraph',
        'langgraph.checkpoint',
        'langgraph.checkpoint.base',
        'langgraph.checkpoint.memory',
        'langgraph.checkpoint.sqlite',
        'langgraph.checkpoint.sqlite.aio',

        # LangChain
        'langchain',
        'langchain_core',
        'langchain_openai',
        'langchain_community',
        'langchain_core.messages',
        'langchain_core.prompts',
        'langchain_core.output_parsers',
        'langchain_core.callbacks',
        'langchain_core.callbacks.manager',

        # Pydantic
        'pydantic',
        'pydantic_settings',
        'pydantic.fields',
        'pydantic.deprecated',
        'pydantic.deprecated.decorator',

        # 其他
        'loguru',
        'dotenv',
        'httpx',
        'httpx._transports',
        'httpx._transports.asgi',

        # Tavily
        'tavily',

        # E2B
        'e2b',
        'e2b_code_interpreter',

        # WebSocket
        'websockets',
        'websockets.legacy',

        # OpenAI
        'openai',
        'openai.resources',
        'openai.resources.chat',
        'openai._client',
    ],

    # Hook 路径
    hookspath=[],
    hooksconfig={},

    # 运行时 Hook
    runtime_hooks=[],

    # 排除的模块（减小体积）
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'numpy.testing',
        'pytest',
        'black',
        'ruff',
    ],

    # Windows 特定选项
    win_no_prefer_redirects=False,
    win_private_assemblies=False,

    # 加密（通常不使用）
    cipher=block_cipher,

    # 不归档
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='craftflow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 保留控制台用于查看日志
    icon=None,  # 图标路径（如果有）
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='craftflow',
)
