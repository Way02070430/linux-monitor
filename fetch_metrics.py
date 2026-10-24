"""读取监控 HTTP 快照，并分别检查请求、数据格式和新鲜度。"""

import argparse
from datetime import datetime
import math

import requests


DEFAULT_URL = "http://127.0.0.1:8000/latest.json"
METRICS = (
    ("cpu_percent", "CPU"),
    ("memory_percent", "内存"),
    ("disk_percent", "磁盘"),
)


class SnapshotError(ValueError):
    """快照的格式或字段值不符合约定。"""


def validate_snapshot(data, now=None):
    """检查字段并返回数据年龄（秒）；None 指标表示采集失败。"""
    if not isinstance(data, dict):
        raise SnapshotError("预期收到 JSON 对象")

    for key in ("timestamp", *(key for key, _ in METRICS)):
        if key not in data:
            raise SnapshotError("缺少字段：" + key)

    if not isinstance(data["timestamp"], str):
        raise SnapshotError("timestamp 必须是时间字符串")
    try:
        sampled_at = datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S")
    except ValueError as error:
        raise SnapshotError("timestamp 格式应为 年-月-日 时:分:秒") from error

    for key, _ in METRICS:
        value = data[key]
        if value is None:
            continue
        # bool 是 int 的子类，必须单独排除，不能把 True 当作 1%。
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SnapshotError(key + " 必须是数字或 null")
        if not 0 <= value <= 100:
            raise SnapshotError(key + " 必须是 0～100 之间的有限数字")

    age = ((now if now is not None else datetime.now()) - sampled_at).total_seconds()
    if age < -5:
        raise SnapshotError("采集时间明显晚于当前时间，请检查时钟或时区")
    return max(age, 0.0)


def fetch_metrics(url, timeout):
    response = requests.get(url, timeout=timeout)
    try:
        response.raise_for_status()
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError as error:
            raise SnapshotError("响应正文不是合法 JSON") from error
    finally:
        response.close()


def positive_seconds(text):
    try:
        value = float(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("请输入正数秒数") from error
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("秒数必须是有限正数")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description="读取和检查监控快照")
    parser.add_argument("--url", default=DEFAULT_URL, help="快照地址")
    parser.add_argument("--timeout", type=positive_seconds, default=3.0,
                        help="连接/读取等待超时（秒），并非整个请求总时限")
    parser.add_argument("--max-age", type=positive_seconds, default=30.0,
                        help="允许的数据最大年龄（秒），默认 30 秒")
    args = parser.parse_args(argv)

    try:
        data = fetch_metrics(args.url, args.timeout)
        age = validate_snapshot(data)
    except requests.exceptions.Timeout:
        print("请求失败：等待连接或响应超时")
        return 1
    except requests.exceptions.ConnectionError:
        print("请求失败：无法连接服务，请检查地址、端口和服务状态")
        return 1
    except requests.exceptions.HTTPError as error:
        print("请求失败：HTTP 状态码异常：", error)
        return 1
    except requests.exceptions.RequestException as error:
        print("请求失败：", error)
        return 1
    except SnapshotError as error:
        print("数据错误：", error)
        return 2

    print("采集时间：", data["timestamp"])
    print("距采集时间：", round(age, 1), "秒")
    stale = age > args.max_age
    if stale:
        print("数据已过期：HTTP 请求成功，但快照没有及时更新；以下为历史数据。")
    else:
        print("数据新鲜度：正常")

    missing = False
    for key, name in METRICS:
        value = data[key]
        if value is None:
            print(name + " 使用率：采集失败，数据未知")
            missing = True
        else:
            print(name + " 使用率：", value, "%")

    if stale:
        return 3
    if missing:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
