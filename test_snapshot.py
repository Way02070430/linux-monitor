from unittest.mock import patch
from monitor import save_snapshot

with patch("builtins.open", side_effect=OSError("模拟文件写入失败")):
    with patch("monitor.logging.exception") as error_mock:
        save_snapshot("2026-10-24 12:00:00", 10, 20, 30)

        error_mock.assert_called_once()

print("快照写入失败处理通过，程序继续执行")