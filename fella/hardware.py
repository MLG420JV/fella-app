"""Reads what this PC actually has - CPU, GPU, RAM, disk, installed apps,
driver version, temperatures. All read-only. Nothing is changed, nothing sent.
Fella uses this so it genuinely knows your machine.
"""

import shutil
import subprocess


def _run(cmd: str) -> str:
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return (p.stdout or "").strip()
    except Exception:
        return ""


def cpu() -> str:
    out = _run("lscpu | grep 'Model name' | head -1 | cut -d: -f2")
    return out.strip() or "unknown CPU"


def gpu() -> str:
    if shutil.which("nvidia-smi"):
        name = _run("nvidia-smi --query-gpu=name --format=csv,noheader")
        drv = _run("nvidia-smi --query-gpu=driver_version --format=csv,noheader")
        if name:
            return f"{name} (driver {drv})"
    out = _run("lspci | grep -Ei 'vga|3d|display' | head -1 | cut -d: -f3")
    return out.strip() or "unknown GPU"


def ram_gb() -> str:
    kb = _run("grep MemTotal /proc/meminfo | awk '{print $2}'")
    try:
        return f"{int(kb) / 1024 / 1024:.0f} GB"
    except ValueError:
        return "unknown"


def disk_free() -> str:
    out = _run("df -h / | tail -1 | awk '{print $4\" free of \"$2}'")
    return out or "unknown"


def gpu_temp() -> str:
    if shutil.which("nvidia-smi"):
        t = _run("nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader")
        return f"{t}°C" if t else "n/a"
    return "n/a"


def has_app(name: str) -> bool:
    return bool(shutil.which(name)) or bool(_run(f"pacman -Qq {name} 2>/dev/null"))


def installed_highlights() -> str:
    checks = {
        "Steam": "steam",
        "Lutris": "lutris",
        "Heroic": "heroic",
        "GameMode": "gamemoderun",
        "MangoHud": "mangohud",
        "Discord": "discord",
        "Firefox": "firefox",
    }
    found = [label for label, cmd in checks.items() if has_app(cmd)]
    return ", ".join(found) if found else "none of the usual gaming apps yet"


def full_report() -> str:
    return (
        f"CPU: {cpu()}\n"
        f"GPU: {gpu()}, currently {gpu_temp()}\n"
        f"Memory: {ram_gb()}\n"
        f"Disk: {disk_free()}\n"
        f"Gaming apps installed: {installed_highlights()}"
    )


def summary_for_model() -> str:
    """A compact one-liner fed to Fella's brain so it always knows the hardware."""
    return f"[This PC: {cpu()} | {gpu()} | {ram_gb()} RAM | {disk_free()}]"


if __name__ == "__main__":
    print(full_report())
