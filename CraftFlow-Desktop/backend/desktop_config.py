"""桌面版路径适配模块

为 PyInstaller 打包环境提供统一的路径管理。
所有数据文件存储在 %APPDATA%/CraftFlow/ 目录下。
"""

import os
import shutil
import sys
from pathlib import Path


def get_data_dir() -> Path:
    """获取桌面版数据根目录

    Windows: %APPDATA%/CraftFlow/
    其他: ~/.craftflow/

    Returns:
        Path: 数据目录路径（已创建）
    """
    appdata = os.environ.get("APPDATA")
    if appdata:
        data_dir = Path(appdata) / "CraftFlow"
    else:
        data_dir = Path.home() / ".craftflow"

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_log_dir() -> Path:
    """获取日志目录

    Returns:
        Path: 日志目录路径（已创建）
    """
    log_dir = get_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_sqlite_dir() -> Path:
    """获取 SQLite 数据库目录

    Returns:
        Path: SQLite 目录路径（已创建）
    """
    sqlite_dir = get_data_dir() / "sqlite"
    sqlite_dir.mkdir(parents=True, exist_ok=True)
    return sqlite_dir


def get_checkpoints_dir() -> Path:
    """获取 Checkpoints 数据库目录

    Returns:
        Path: Checkpoints 目录路径（已创建）
    """
    checkpoints_dir = get_data_dir() / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    return checkpoints_dir


def get_env_file() -> Path:
    """获取 .env 文件路径

    如果不存在，从 .env.example 复制模板。

    Returns:
        Path: .env 文件路径
    """
    env_path = get_data_dir() / ".env"

    if not env_path.exists():
        # 尝试从打包资源中复制 .env.example
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包环境
            bundle_dir = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(sys.executable).parent
            example_path = bundle_dir / ".env.example"
        else:
            # 开发环境
            example_path = Path(__file__).parent / ".env.example"

        if example_path.exists():
            shutil.copy2(example_path, env_path)
            print(f"[desktop_config] 已从模板创建 .env: {env_path}")
        else:
            # 创建空的 .env 文件
            env_path.touch()
            print(f"[desktop_config] 已创建空 .env: {env_path}")

    return env_path


def is_desktop_mode() -> bool:
    """检测是否为桌面版（PyInstaller 打包）环境

    Returns:
        bool: True 表示桌面版环境
    """
    return getattr(sys, 'frozen', False)
