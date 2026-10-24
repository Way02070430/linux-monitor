import psutil

try:
    disk = psutil.disk_usage("/this-path-does-not-exist")
    print("磁盘使用率：", disk.percent, "%")

except OSError as error:
    print("磁盘采集失败：", error)

print("程序还能继续执行")