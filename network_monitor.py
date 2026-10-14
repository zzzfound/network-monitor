# -*- coding: utf-8 -*-
"""
网络监控工具 (Network Monitor)
==============================
功能：
  1. 定时检测目标主机是否在线（ping）
  2. 检测主机上的端口是否开放（socket）
  3. 检测结果带时间戳写入日志文件 monitor.log
  4. 连续多次失败才触发「告警」，避免网络抖动误报
  5. Ctrl+C 优雅退出

只使用 Python 标准库，无需安装第三方依赖。
运行方式：在项目文件夹下执行  python network_monitor.py
"""
import os
import json
import subprocess
import socket
import time
import datetime

# 以脚本所在目录为基准，定位配置文件和日志文件（避免受运行时目录影响）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_FILE = os.path.join(BASE_DIR, "monitor.log")

INTERVAL = 10          # 默认检测间隔（秒），可被 config.json 覆盖
FAIL_THRESHOLD = 3     # 连续失败多少次才算「告警」

# 记录每个主机连续失败的次数
_fail_count = {}


def load_config():
    """读取 config.json，返回配置字典"""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def ping(host):
    """检测主机是否在线，返回 True/False"""
    # Windows 用 -n（次数），Linux/Mac 用 -c；超时参数也不同
    if os.name == "nt":
        cmd = ["ping", "-n", "1", "-w", "1000", host]
    else:
        cmd = ["ping", "-c", "1", "-W", "1", host]

    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000  # 隐藏 Windows 弹出的命令行窗口

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=5, **kwargs)
        return result.returncode == 0  # ping 成功时返回码为 0
    except Exception:
        return False


def check_port(host, port):
    """检测主机的某个端口是否开放，返回 True/False"""
    try:
        socket.create_connection((host, port), timeout=2)
        return True
    except Exception:
        return False


def log(msg, level="INFO"):
    """写日志：屏幕打印 + 追加到文件"""
    line = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def check_target(target):
    """检测单个目标（主机 + 端口），返回是否全部正常"""
    host = target["host"]
    ok = True

    # 1. ping 检测主机是否在线
    if ping(host):
        log(f"在线  {host}")
    else:
        ok = False
        log(f"离线  {host}", level="WARN")

    # 2. 检测配置的端口是否开放
    for port in target.get("ports", []):
        if check_port(host, port):
            log(f"  端口 {host}:{port} 开放")
        else:
            ok = False
            log(f"  端口 {host}:{port} 不通", level="WARN")

    return ok


def main():
    config = load_config()
    interval = config.get("interval", INTERVAL)
    targets = config.get("targets", [])

    log(f"=== 网络监控启动，共 {len(targets)} 个目标，检测间隔 {interval} 秒 ===")

    while True:
        for target in targets:
            host = target["host"]
            ok = check_target(target)

            # 连续失败计数，达到阈值才告警，避免网络抖动误报
            if not ok:
                _fail_count[host] = _fail_count.get(host, 0) + 1
                if _fail_count[host] >= FAIL_THRESHOLD:
                    log(f"告警! {host} 连续 {_fail_count[host]} 次检测异常", level="ERROR")
            else:
                _fail_count[host] = 0

        time.sleep(interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("=== 监控已停止（Ctrl+C）===")
