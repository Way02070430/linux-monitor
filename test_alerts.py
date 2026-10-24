from monitor import check_alert
from unittest.mock import patch

cpu_alerting = False
memory_alerting = False

samples = [
    (85,20),
    (90, 85),
    (30, 90),
    (20, 30),
]

for cpu, memory in samples:
    print("\n本轮CPU：", cpu ,"%,内存：",memory, "%")
    
    cpu_alerting = check_alert("CPU",cpu,80,cpu_alerting)
    memory_alerting = check_alert("内存",memory,80,memory_alerting)

# 两项最后都已恢复，状态应该是 False
assert cpu_alerting is False
assert memory_alerting is False

# 磁盘：测试低于阈值、恰好达到阈值、持续超限和恢复
disk_alerting = False

disk_alerting = check_alert("磁盘", 89, 90, disk_alerting)
assert disk_alerting is False

disk_alerting = check_alert("磁盘", 90, 90, disk_alerting)
assert disk_alerting is True

disk_alerting = check_alert("磁盘", 95, 90, disk_alerting)
assert disk_alerting is True

disk_alerting = check_alert("磁盘", 80, 90, disk_alerting)
assert disk_alerting is False

print("\n所有状态断言通过")

# 临时替换日志函数，记录它们被调用了多少次
with patch("monitor.logging.warning") as warning_mock:
    with patch("monitor.logging.info") as info_mock:
        alerting = False

        for value in [20, 85, 90, 30, 20, 85]:
            alerting = check_alert("CPU", value, 80, alerting)

        assert warning_mock.call_count == 2
        assert info_mock.call_count == 1
        assert alerting is True

print("告警次数和恢复次数检查通过")

# 模拟磁盘之前已处于告警状态
with patch("monitor.logging.info") as info_mock:
    state = check_alert("磁盘", None, 90, True)

    assert state is True
    info_mock.assert_not_called()

# 模拟磁盘之前处于正常状态
with patch("monitor.logging.warning") as warning_mock:
    state = check_alert("磁盘", None, 90, False)

    assert state is False
    warning_mock.assert_not_called()

print("采集失败时的告警状态检查通过")