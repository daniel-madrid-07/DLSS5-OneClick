"""
Construye DLSS5-OneClick.exe: un ejecutable unico, sin Python instalado.

    python build.py

Deja el resultado en dist/DLSS5-OneClick.exe.

Lo que NO va dentro, a proposito:

  * nvngx_dlssnr.dll -- propietario de NVIDIA. Embeberlo en el .exe seria
    redistribuirlo igual que ponerlo suelto: el formato no cambia la licencia,
    y PyInstaller no cifra nada (cualquiera extrae los recursos). Ademas un
    ejecutable de 170 MB que suelta DLLs en carpetas de juegos es el perfil
    exacto que los antivirus marcan como troyano.

  * Los binarios de OptiScaler -- GPL-3.0. Redistribuirlos obligaria a este
    proyecto entero a ser GPL en vez de MIT. Se descargan de su repo oficial
    en tiempo de ejecucion, que es lo que ya hace el programa.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

NAME = "DLSS5-OneClick"
ENTRY = "dlss5.py"

# Modulos propios que PyInstaller no ve porque solo se importan desde dlss5.py
HIDDEN = ["dlss5_scan", "dlss5_apply", "dlss5_model", "dlss5_opts",
          "dlss5_editor"]

# Lo que no hace falta y solo engorda el ejecutable.
#
# Aqui solo van paquetes de terceros. NADA de la biblioteca estandar: urllib
# arrastra email y http para descargar el paquete de OptiScaler, y excluirlos
# hace que el .exe muera al arrancar con ModuleNotFoundError. Comprobado.
EXCLUDE = ["numpy", "pandas", "matplotlib", "PIL", "pytest", "setuptools",
           "pip", "PyQt5", "PySide2", "PySide6", "scipy", "IPython",
           "notebook", "sphinx"]


def main() -> int:
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    if not os.path.isfile(ENTRY):
        print(f"No encuentro {ENTRY}. Ejecuta esto desde la carpeta del proyecto.")
        return 1

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Falta PyInstaller.  Instalalo con:  python -m pip install pyinstaller")
        return 1

    for d in ("build", "dist"):
        shutil.rmtree(os.path.join(root, d), ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",              # sin consola detras de la ventana
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

    print("Compilando...  (un par de minutos la primera vez)\n")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("\nLa compilacion fallo.")
        return result.returncode

    exe = os.path.join(root, "dist", NAME + ".exe")
    if not os.path.isfile(exe):
        print("\nPyInstaller termino pero no hay .exe.")
        return 1

    size = os.path.getsize(exe)
    print(f"\nListo:  dist/{NAME}.exe   ({size / (1 << 20):.1f} MB)")
    print("\nEste ejecutable NO contiene el modelo de NVIDIA ni los binarios")
    print("de OptiScaler. Los descarga o los localiza al usarse, que es")
    print("justo lo que lo mantiene legal y libre de falsos positivos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
