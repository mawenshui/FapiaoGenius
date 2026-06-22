"""日志配置 — 项目级调试日志系统

特性:
- 日志输出到项目路径的 logs/ 目录
- 每次启动新建一个带时间戳的日志文件
- 控制台输出 INFO 级别，文件输出 DEBUG 级别
- 详细格式包含模块名、函数名、行号
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


def _get_project_dir() -> Path:
    """获取项目根目录（main.py 所在目录）"""
    # core/logger.py → core/ → 项目根目录
    return Path(__file__).resolve().parent.parent


def setup_logger(name: str = "ai_fapiao") -> logging.Logger:
    """配置并返回日志记录器"""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # === 控制台处理器：INFO 级别，简洁格式 ===
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # === 文件处理器：DEBUG 级别，详细格式，每次启动新文件 ===
    try:
        project_dir = _get_project_dir()
        log_dir = project_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # 生成带时间戳的文件名: ai_fapiao_20260617_120000.log
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"ai_fapiao_{timestamp}.log"

        file_handler = logging.FileHandler(
            log_file, encoding='utf-8', mode='w'
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | '
            '%(module)s.%(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

        # 启动标记
        logger.info(f"{'='*60}")
        logger.info(f"智票通启动")
        logger.info(f"日志文件: {log_file}")
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"{'='*60}")

    except Exception as e:
        logger.warning(f"无法创建日志文件: {e}")

    return logger


def cleanup_old_logs(max_files: int = 50):
    """清理旧日志文件，保留最新的 max_files 个"""
    try:
        project_dir = _get_project_dir()
        log_dir = project_dir / "logs"
        if not log_dir.exists():
            return

        log_files = sorted(
            log_dir.glob("ai_fapiao_*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        for old_file in log_files[max_files:]:
            try:
                old_file.unlink()
            except Exception:
                pass

    except Exception:
        pass


# 全局日志实例
logger = setup_logger()

# 启动时清理旧日志（保留最近 50 个）
cleanup_old_logs(50)
