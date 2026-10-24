# Linux 系统监控与异常告警

基于 Python 和 psutil 的单机监控学习项目。

## 已实现功能

- 周期采集 CPU、内存和根文件系统的使用率。
- 支持独立配置三项告警阈值。
- 首次超限告警，持续超限不重复通知，恢复后记录恢复。
- 保存运行日志和最新 JSON 快照。
- CPU、内存、磁盘独立处理采集错误，单项失败不影响其他指标。
- 失败指标显示“采集失败”，JSON 保存为 null，保留原有告警状态。
- JSON 快照打开失败时记录错误。
- 支持 Ctrl + C 停止。

告警目前输出到终端和日志，尚未接入邮件或其他通知渠道。

## 运行环境

- Ubuntu 24.04，运行于 WSL2
- Python 3.12
- psutil 7.2.2

监控对象是 WSL 中的 Linux 环境。
根文件系统容量不等于 Windows D 盘的整体容量。

## 安装与运行

在项目目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python monitor.py
```

按 Ctrl + C 停止。

## 配置

修改 config.py 后，保存并重新启动程序。

- cpu_threshold：CPU 告警阈值。
- memory_threshold：内存告警阈值。
- disk_threshold：磁盘告警阈值。
- disk_path：查询磁盘空间的路径。
- wait_seconds：每轮处理完成后的等待时间。

CPU 采样约需 1 秒，因此实际输出间隔还包含采样和处理耗时。

## 输出文件

- monitor.log：运行、告警、恢复和错误日志。
- latest.json：最新一轮指标，每轮覆盖。

## 测试

```bash
python test_alerts.py
python test_snapshot.py
python -m unittest -v test_collectors
python test_log_rotation.py
```