"""
增强日志系统

提供：
- 按天自动轮转的文件日志
- 彩色控制台输出
- 统一的日志格式
"""
import logging
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler


def setup_logger(name: str = "auto_trader", log_dir: str = "logs",
                 level: int = logging.INFO) -> logging.Logger:
    """
    初始化日志系统。

    Args:
        name: 日志器名称
        log_dir: 日志文件目录
        level: 日志级别

    Returns:
        配置好的Logger实例
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 文件Handler（每天轮转，保留30天）
    fh = TimedRotatingFileHandler(
        log_path / f"{name}.log",
        when="midnight",
        backupCount=30,
        encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    fh.setLevel(level)
    logger.addHandler(fh)

    # 控制台Handler（彩色输出）
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(
        '\033[90m%(asctime)s\033[0m [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    ))
    ch.setLevel(level)
    logger.addHandler(ch)

    return logger


def get_logger(name: str) -> logging.Logger:
    """获取已存在的日志器。"""
    return logging.getLogger(name)
