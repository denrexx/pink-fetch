#!/usr/bin/env python3
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = APP_DIR / "pinkfetch.json"

def run(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""

def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def load_config():
    path = Path(os.environ.get("PINKFETCH_CONFIG", DEFAULT_CONFIG))
    if len(sys.argv) > 1:
        path = Path(sys.argv[1]).expanduser()

    data = {
        "color_rgb": [255, 182, 193],
        "label_width": 10,
        "separator": " • ",
        "show_bars": True,
        "bar_width": 12,
        "logo": [
            "                   -`",
            "                  .o+`",
            "                 `ooo/",
            "                `+oooo:",
            "               `+oooooo:",
            "               -+oooooo+:",
            "             `/:-:++oooo+:",
            "            `/++++/+++++++:",
            "           `/++++++++++++++:",
            "          `/+++ooooooooooooo/`",
            "         ./ooosssso++osssssso+`",
            "        .oossssso-````/ossssss+`",
            "       -osssssso.      :ssssssso.",
            "      :osssssss/        osssso+++.",
            "     /ossssssss/        +ssssooo/-",
            "   `/ossssso+/:-        -:/+osssso+-",
            "  `+sso+:-`                 `.-/+oso:",
            " `++:.                           `-/+/",
            " .`                                 `/"
        ],
        "items": [
            ["OS", "os"],
            ["Host", "host"],
            ["Kernel", "kernel"],
            ["Uptime", "uptime"],
            ["Packages", "packages"],
            ["Shell", "shell"],
            ["Terminal", "terminal"],
            ["WM/DE", "wm"],
            ["CPU", "cpu"],
            ["GPU", "gpu"],
            ["RAM", "ram"],
            ["Disk", "disk"],
            ["IP", "ip"]
        ]
    }

    try:
        if path.exists():
            user_data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(user_data, dict):
                data.update(user_data)
    except Exception:
        pass
    return data


def ansi(rgb, bold=False):
    r, g, b = rgb
    return f"\033[{'1;' if bold else ''}38;2;{r};{g};{b}m"


def reset():
    return "\033[0m"


def fmt_bytes(n):
    units = ["B", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(n)
    for u in units:
        if size < 1024 or u == units[-1]:
            if u in {"B", "KB"}:
                return f"{int(size)} {u}"
            return f"{size:.1f} {u}"
        size /= 1024


def fmt_uptime(sec):
    sec = int(sec)
    d, sec = divmod(sec, 86400)
    h, sec = divmod(sec, 3600)
    m, _ = divmod(sec, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m or not parts:
        parts.append(f"{m}m")
    return " ".join(parts)


def fmt_bar(pct, width):
    pct = max(0.0, min(100.0, float(pct)))
    full = round(width * pct / 100)
    return "[" + "█" * full + "░" * (width - full) + "]"


def get_os():
    txt = read_text("/etc/os-release")
    fields = {}
    for line in txt.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            fields[k] = v.strip().strip('"')
    return fields.get("PRETTY_NAME") or platform.system()


def get_host():
    host = socket.gethostname()
    vendor = read_text("/sys/devices/virtual/dmi/id/sys_vendor").strip()
    product = read_text("/sys/devices/virtual/dmi/id/product_name").strip()
    model = " ".join(x for x in [vendor, product] if x)
    return f"{host} ({model})" if model else host


def get_cpu():
    name = ""
    for line in read_text("/proc/cpuinfo").splitlines():
        if line.lower().startswith("model name"):
            name = line.split(":", 1)[1].strip()
            break
    if not name or name.lower() == "unknown":
        name = run(["bash", "-lc", "lscpu 2>/dev/null | sed -n 's/^Model name:[[:space:]]*//p' | head -n1"])
    if not name or name.lower() == "unknown":
        name = platform.processor() or "unknown"
    cores = os.cpu_count()
    if cores and name != "unknown":
        return f"{name} ({cores}c)"
    return name or "unknown"


def get_gpu():
    line = run(["bash", "-lc", r"lspci 2>/dev/null | grep -Ei 'vga|3d|display' | head -n1 | sed -E 's/^.*: //' "])
    return line or "unknown"


def get_ram(cfg):
    mem = {}
    for line in read_text("/proc/meminfo").splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        mem[k] = int(v.strip().split()[0]) * 1024
    total = mem.get("MemTotal", 0)
    avail = mem.get("MemAvailable", 0)
    used = max(total - avail, 0)
    pct = (used / total * 100) if total else 0
    text = f"{fmt_bytes(used)} / {fmt_bytes(total)} ({pct:.0f}%)"
    if cfg.get("show_bars", True):
        text += f" {fmt_bar(pct, int(cfg.get('bar_width', 12)))}"
    return text


def get_disk(cfg):
    try:
        total, used, free = shutil.disk_usage("/")
        pct = (used / total * 100) if total else 0
        text = f"{fmt_bytes(used)} / {fmt_bytes(total)} ({pct:.0f}%)"
        if cfg.get("show_bars", True):
            text += f" {fmt_bar(pct, int(cfg.get('bar_width', 12)))}"
        return text
    except Exception:
        return "unknown"


def get_uptime():
    txt = read_text("/proc/uptime").split()
    return fmt_uptime(float(txt[0])) if txt else "unknown"


def get_packages():
    pacman_db = Path("/var/lib/pacman/local")
    if pacman_db.exists():
        try:
            return str(sum(1 for p in pacman_db.iterdir() if p.is_dir()))
        except Exception:
            pass
    out = run(["bash", "-lc", "command -v pacman >/dev/null && pacman -Qq 2>/dev/null | wc -l"])
    return out or "unknown"


def get_shell():
    shell = Path(os.environ.get("SHELL", "")).name
    ver = ""
    if shell == "bash":
        ver = run(["bash", "--version"]).splitlines()[0].split()[-1]
    elif shell == "zsh":
        ver = run(["zsh", "--version"]).split()[-1]
    elif shell == "fish":
        parts = run(["fish", "--version"]).split()
        ver = parts[-1] if parts else ""
    return f"{shell} {ver}".strip() or "unknown"


def get_terminal():
    return os.environ.get("TERM_PROGRAM") or os.environ.get("TERM") or "unknown"


def get_wm():
    return (
        os.environ.get("XDG_CURRENT_DESKTOP")
        or os.environ.get("DESKTOP_SESSION")
        or os.environ.get("WAYLAND_DISPLAY")
        or os.environ.get("DISPLAY")
        or "unknown"
    )


def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("1.1.1.1", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unknown"


def gather(cfg):
    return {
        "os": get_os(),
        "host": get_host(),
        "kernel": platform.release(),
        "uptime": get_uptime(),
        "packages": get_packages(),
        "shell": get_shell(),
        "terminal": get_terminal(),
        "wm": get_wm(),
        "cpu": get_cpu(),
        "gpu": get_gpu(),
        "ram": get_ram(cfg),
        "disk": get_disk(cfg),
        "ip": get_ip(),
    }


def print_fetch(cfg, info):
    color = tuple(cfg.get("color_rgb", [255, 182, 193]))
    pink = ansi(color, bold=True)
    pink_dim = ansi(color)
    rst = reset()
    logo = cfg.get("logo", [])
    items = cfg.get("items", [])
    label_w = int(cfg.get("label_width", 10))
    sep = cfg.get("separator", " • ")

    user = os.environ.get("USER", "arch")
    host = socket.gethostname()
    header = f"{user}@{host}"
    line = "─" * len(header)

    info_lines = [
        f"{pink}{header}{rst}",
        f"{pink_dim}{line}{rst}",
    ]
    for label, key in items:
        value = info.get(key, "unknown")
        info_lines.append(f"{pink}{label:<{label_w}}{rst}{sep}{pink_dim}{value}{rst}")

    width = max((len(x) for x in logo), default=0) + 3
    rows = max(len(logo), len(info_lines))
    for i in range(rows):
        left = logo[i] if i < len(logo) else ""
        right = info_lines[i] if i < len(info_lines) else ""
        print(f"{pink_dim}{left:<{width}}{rst}{right}")


if __name__ == "__main__":
    cfg = load_config()
    info = gather(cfg)
    print_fetch(cfg, info)