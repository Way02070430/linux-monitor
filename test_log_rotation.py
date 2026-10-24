import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tempfile import TemporaryDirectory

# 创建临时目录，测试结束后自动清理
with TemporaryDirectory() as directory:
    log_file = Path(directory) / "test.log"

    logger = logging.getLogger("rotation_test")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = RotatingFileHandler(
        log_file,
        maxBytes=100,
        backupCount=2,
        encoding="utf-8",
    )
    logger.addHandler(handler)

    try:
        for i in range(20):
            logger.info("This is test log message number %d", i)

        assert log_file.exists()
        assert Path(str(log_file) + ".1").exists()
        assert Path(str(log_file) + ".2").exists()
        assert not Path(str(log_file) + ".3").exists()

        latest = log_file.read_text(encoding="utf-8")
        assert "number 19" in latest

        print("日志轮转测试通过")

    finally:
        logger.removeHandler(handler)
        handler.close()