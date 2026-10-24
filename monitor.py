import psutil
import time
from datetime import datetime
import logging
from pathlib import Path
import config
import json

from logging.handlers import RotatingFileHandler

def validate_config():
    thresholds = [
        ("CPU", config.cpu_threshold),
        ("内存", config.memory_threshold),
        ("磁盘", config.disk_threshold),
    ]

    for name, threshold in thresholds:
        if not 0 <= threshold <= 100:
            raise ValueError(name + "阈值必须在 0～100 之间")

    if config.wait_seconds <= 0:
        raise ValueError("等待时间必须大于 0")

# 采集各个指标的数值
def collect_metrics():
    # 各项独立处理错误，失败返回 None，不冒充 0% 或使用旧数据。
    try:
        cpu = psutil.cpu_percent(interval=1)
    except (OSError, psutil.Error):
        logging.exception("CPU 采集失败")
        cpu = None

    try:
        memory_percent = psutil.virtual_memory().percent
    except (OSError, psutil.Error):
        logging.exception("内存采集失败")
        memory_percent = None

    try:
        disk_percent = psutil.disk_usage(config.disk_path).percent
    except (OSError, psutil.Error):
        logging.exception("磁盘采集失败")
        disk_percent = None

    return cpu, memory_percent, disk_percent


def format_metric(value):
    # 终端和日志统一显示缺失数据，避免输出 None%。
    if value is None:
        return "采集失败"
    return str(value) + "%"


# 告警函数
def check_alert(name, value, threshold, alerting):

    if value is None:
        return alerting
    
    if value >= threshold:
        if not alerting:
            print("告警：", name, "使用率达到阈值")
            logging.warning(
                "%s 使用率 %.1f%%，达到阈值 %.1f%%",
                name,
                value,
                threshold,
            )
        return True

    if alerting:
        print("恢复：", name, "使用率已低于阈值")
        logging.info("%s 恢复正常，当前使用率 %.1f%%", name, value)

    return False

def save_snapshot(timestamp,cpu,memory,disk):
    data = {
        "timestamp" : timestamp,
        "cpu_percent" : cpu,
        "memory_percent" : memory,
        "disk_percent" : disk,
    }

    snapshot_file = Path(__file__).resolve().parent / "latest.json"

    try:
        with open(snapshot_file, "w", encoding="utf-8") as file :
            json.dump(data, file, ensure_ascii=False, indent=2)

    except OSError as error:
        print("快照保存失败：",error)
        logging.exception("快照保存失败")

if __name__ == "__main__":

    validate_config()

    log_file = Path(__file__).resolve().parent / "monitor.log"

    handler = RotatingFileHandler(
        log_file,
        maxBytes=1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )

    logging.basicConfig(
        handlers=[handler],
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    logging.info("监控程序启动")

    cpu_alerting = False
    memory_alerting = False
    disk_alerting = False

    #test_cpu_values = iter([20, 85, 90, 30, 20, 85])

    try:
        while True:
            cpu, memory, disk = collect_metrics()
            #cpu = next(test_cpu_values)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_snapshot(timestamp,cpu,memory,disk)
            print("采集时间：", timestamp)

            print("CPU 使用率：", format_metric(cpu))
            print("内存使用率：", format_metric(memory))
            print("磁盘使用率：", format_metric(disk))

            logging.info(
                "CPU：%s，内存：%s，磁盘：%s",
                format_metric(cpu),
                format_metric(memory),
                format_metric(disk),
            )

            cpu_alerting = check_alert(
                "CPU", cpu, config.cpu_threshold, cpu_alerting
            )

            memory_alerting = check_alert(
                "内存", memory, config.memory_threshold, memory_alerting
            )

            disk_alerting = check_alert(
                "磁盘", disk, config.disk_threshold, disk_alerting
            )
            
            print("--------------------")
            time.sleep(config.wait_seconds)
    except KeyboardInterrupt:
        print("\n监控已停止。")
        logging.info("用户停止监控。")
