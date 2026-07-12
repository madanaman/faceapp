from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def command_name(name: str) -> str:
    if os.name == "nt":
        candidate = shutil.which(f"{name}.cmd") or shutil.which(f"{name}.exe")
        if candidate:
            return candidate
    return name


def copy_desktop_assets() -> None:
    desktop = ROOT / "desktop"
    desktop.mkdir(exist_ok=True)
    for name in ("index.html", "styles.css", "app.js"):
        shutil.copy2(ROOT / name, desktop / name)


def rust_target() -> str:
    try:
        result = subprocess.run(
            ["rustc", "-vV"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines():
            if line.startswith("host: "):
                return line.removeprefix("host: ").strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    system = platform.system()
    machine = platform.machine().lower()
    if system == "Darwin" and machine in {"arm64", "aarch64"}:
        return "aarch64-apple-darwin"
    if system == "Darwin":
        return "x86_64-apple-darwin"
    if system == "Windows" and machine in {"arm64", "aarch64"}:
        return "aarch64-pc-windows-msvc"
    if system == "Windows":
        return "x86_64-pc-windows-msvc"
    if system == "Linux" and machine in {"arm64", "aarch64"}:
        return "aarch64-unknown-linux-gnu"
    if system == "Linux":
        return "x86_64-unknown-linux-gnu"
    raise RuntimeError("Could not infer Tauri sidecar target. Install Rust and rerun.")


def build_backend() -> None:
    env = os.environ.copy()
    env.setdefault("PYINSTALLER_CONFIG_DIR", str(ROOT / ".build" / "pyinstaller"))
    env.setdefault("MPLCONFIGDIR", str(ROOT / ".build" / "matplotlib"))
    env.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")
    Path(env["PYINSTALLER_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(env["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    run([sys.executable, "-m", "PyInstaller", "packaging/local-face-backend.spec", "--noconfirm", "--clean"], env=env)

    dist_name = "local-face-backend.exe" if os.name == "nt" else "local-face-backend"
    binary_suffix = ".exe" if os.name == "nt" else ""
    source = ROOT / "dist" / dist_name
    target = ROOT / "src-tauri" / "binaries" / f"local-face-backend-{rust_target()}{binary_suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"Copied backend sidecar to {target.relative_to(ROOT)}")


def bundle_target() -> str:
    configured = os.environ.get("TAURI_BUNDLES")
    if configured:
        return configured
    system = platform.system()
    if system == "Darwin":
        return "dmg"
    if system == "Windows":
        return "nsis"
    return "appimage"


def main() -> None:
    copy_desktop_assets()
    build_backend()
    run([command_name("npm"), "run", "tauri:build", "--", "--bundles", bundle_target()])


if __name__ == "__main__":
    main()
