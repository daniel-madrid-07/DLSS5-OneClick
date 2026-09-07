"""
Builds DLSS5-Toolkit.exe: a single executable, no Python install required.

    python build.py

The result lands in dist/DLSS5-Toolkit.exe.

What deliberately stays OUT:

  * nvngx_dlssnr.dll -- NVIDIA's property. Embedding it in the .exe would be
    redistribution just as much as shipping it loose: the container does not
    change the licence, and PyInstaller encrypts nothing (anyone can extract
    the bundled resources). On top of that, a 170 MB executable that drops
    DLLs into game folders is the exact profile antivirus engines flag as a
    trojan.

  * OptiScaler's binaries -- GPL-3.0. Redistributing them would force this
    whole project to be GPL instead of MIT. They are downloaded from their own
    official repository at run time, which is what the program already does.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

NAME = "DLSS5-Toolkit"
ENTRY = "dlss5.py"

# Our own modules, which PyInstaller misses because they are only imported
# from dlss5.py.
HIDDEN = ["dlss5_scan", "dlss5_apply", "dlss5_model", "dlss5_opts",
          "dlss5_editor"]

# What is not needed and only bloats the executable.
#
# Third-party packages ONLY. Nothing from the standard library: urllib pulls
# in email and http to download the OptiScaler package, and excluding them
# makes the .exe die at startup with ModuleNotFoundError. Verified.
EXCLUDE = ["numpy", "pandas", "matplotlib", "PIL", "pytest", "setuptools",
           "pip", "PyQt5", "PySide2", "PySide6", "scipy", "IPython",
           "notebook", "sphinx"]


def main() -> int:
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    if not os.path.isfile(ENTRY):
        print(f"Cannot find {ENTRY}. Run this from the project folder.")
        return 1

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is missing.  Install it with:  python -m pip install pyinstaller")
        return 1

    for d in ("build", "dist"):
        shutil.rmtree(os.path.join(root, d), ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",              # no console window behind the UI
        "--name", NAME,
        "--noconfirm",
        "--clean",
    ]
    for m in HIDDEN:
        cmd += ["--hidden-import", m]
    for m in EXCLUDE:
        cmd += ["--exclude-module", m]

    icon = os.path.join(root, "icono.ico")
    if os.path.isfile(icon):
        cmd += ["--icon", icon]

    cmd.append(ENTRY)

    print("Building...  (a couple of minutes the first time)\n")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("\nThe build failed.")
        return result.returncode

    exe = os.path.join(root, "dist", NAME + ".exe")
    if not os.path.isfile(exe):
        print("\nPyInstaller finished but produced no .exe.")
        return 1

    size = os.path.getsize(exe)
    print(f"\nDone:  dist/{NAME}.exe   ({size / (1 << 20):.1f} MB)")
    print("\nThis executable does NOT contain NVIDIA's model or "
          "OptiScaler's binaries. It downloads or locates them when used,")
    print("which is exactly what keeps it legal and free of antivirus "
          "false positives.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
