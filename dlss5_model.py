"""
Conseguir nvngx_dlssnr.dll, que es lo que de verdad bloquea todo lo demas.

COMPROBADO el 5/9/2026 descargando y abriendo el instalador oficial 616.64
(938 MB, us.download.nvidia.com): el modelo NO viene en el driver. Los unicos
nvngx_* del paquete son nvngx.dll, nvngx_dlssg.dll, nvngx_dlisr.dll y
nvngx_update.exe. Ni rastro de dlssnr.

El modelo lo distribuye CADA JUEGO que implementa DLSS 5. Se encontro por
primera vez dentro de NBA 2K27 (158 MB, "NVIDIA DLSSNR" v310.8.0.0). Asi que
la unica fuente limpia es un juego con DLSS 5 oficial ya instalado.

Formas de conseguirlo, de mas limpia a menos:

  1. Ya lo tienes (una copia previa en la cache).
  2. Esta dentro de un juego con DLSS 5 oficial instalado -> se copia.
  3. Esta dentro de un instalador de driver -> se extrae con 7-Zip.
     Ninguno lo trae a dia de hoy, pero puede cambiar y sale gratis mirar.
  4. No hay nada -> se dice la verdad en vez de mandar a por un driver inutil.

Nunca se descarga el DLL de repositorios de terceros. Es de NVIDIA, y los
sitios que lo reempaquetan son justo los que hay que evitar.
"""

from __future__ import annotations

import os
import re
import sys
import glob
import shutil
import subprocess

# El modelo pesa ~165 MB. Cualquier cosa muy por debajo no es el modelo.
MIN_MODEL_MB = 100
MODEL_NAME = "nvngx_dlssnr.dll"

# Version minima de driver que lo incluye, segun las notas del fork.
MIN_DRIVER = 616.56

SEVENZIP = [
    r"C:\Program Files\7-Zip\7z.exe",
    r"C:\Program Files (x86)\7-Zip\7z.exe",
    "7z",
]

# Donde suele quedarse un instalador de driver despues de bajarlo.
INSTALLER_DIRS = [
    os.path.expandvars(r"%USERPROFILE%\Downloads"),
    os.path.expandvars(r"%USERPROFILE%\Desktop"),
    r"C:\NVIDIA",
    os.path.expandvars(r"%ProgramData%\NVIDIA Corporation\Downloader"),
]

INSTALLER_RE = re.compile(
    r"(\d{3}\.\d{2}).*?(desktop|notebook|win).*?\.exe$|"
    r"^\d{3}\.\d{2}[-_].*\.exe$", re.I)


def _sevenzip() -> str | None:
    for cand in SEVENZIP:
        if os.path.isfile(cand):
            return cand
        if cand == "7z" and shutil.which("7z"):
            return "7z"
    return None


def _run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


# --------------------------------------------------------------------------
# 1. Buscar copias que ya existan
# --------------------------------------------------------------------------

# Juegos que envian el modelo en sus propios archivos.
#
# Comprobado el 5/9/2026 contra el anuncio de NVIDIA: el unico con Neural
# Rendering es NBA 2K27. Onimusha y Dawnwalker aparecen en el mismo articulo
# pero solo reciben DLSS 4.5 (Super Resolution y Multi Frame Generation), asi
# que NO traen nvngx_dlssnr.dll. La demo gratuita de Onimusha tampoco sirve.
SHIPPING_GAMES = ["NBA 2K27"]

# Juegos que suenan a DLSS 5 pero no traen el modelo. Se listan para no mandar
# a nadie a instalar 100 GB para nada.
NOT_SHIPPING = {
    "Onimusha: Way of the Sword": "solo DLSS 4.5, la demo gratuita tampoco vale",
    "The Blood of Dawnwalker": "solo DLSS 4.5",
    "STAR WARS Zero Company": "solo DLSS 4.5",
}


def find_in_games(log=print) -> dict | None:
    """Busca el modelo dentro de los juegos instalados.

    Es la fuente real: NBA 2K27 fue el primero en traerlo, y cualquier juego
    con DLSS 5 oficial lo lleva en su carpeta.
    """
    from dlss5_scan import steam_libraries, installed_games, file_version

    roots: list[str] = []
    for lib in steam_libraries():
        common = os.path.join(lib, "steamapps", "common")
        if os.path.isdir(common):
            roots.append(common)
    for g in installed_games():
        if os.path.isdir(g["path"]):
            roots.append(g["path"])

    seen: set[str] = set()
    for root in roots:
        key = os.path.normcase(root)
        if key in seen:
            continue
        seen.add(key)
        for dirpath, dirnames, filenames in os.walk(root):
            if dirpath[len(root):].count(os.sep) >= 6:
                dirnames[:] = []
            for fn in filenames:
                if fn.lower() != MODEL_NAME:
                    continue
                full = os.path.join(dirpath, fn)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    continue
                if size >= MIN_MODEL_MB << 20:
                    log(f"  encontrado en un juego: {full}")
                    return {"path": full, "size": size,
                            "version": file_version(full)}
    return None


def app_dir() -> str:
    """Carpeta desde la que se ejecuta el programa.

    Con PyInstaller, sys.executable es el .exe y __file__ apunta al descomprimido
    temporal, que no le sirve a nadie. Aqui interesa siempre la carpeta donde el
    usuario dejo el ejecutable.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def find_existing(extra_roots: list[str] | None = None) -> dict:
    """Busca un nvngx_dlssnr.dll ya presente en el sistema.

    Tambien reconoce el caso que avisa el README del fork: un nvngx_dlssd.dll
    de tamano de modelo no es Ray Reconstruction, es Neural Rendering con el
    nombre cambiado.
    """
    result = {"path": None, "size": 0, "version": None, "misnamed": None}

    roots = [
        # Lo primero, junto al propio programa: es donde lo deja cualquiera que
        # consiga el DLL por su cuenta, sin tener que buscar ninguna carpeta.
        app_dir(),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "DLSS5", "modelo"),
        r"C:\Windows\System32",
        r"C:\Windows\System32\DriverStore\FileRepository",
        r"C:\ProgramData\NVIDIA\NGX\models",
        r"C:\Program Files\NVIDIA Corporation",
    ] + (extra_roots or [])

    from dlss5_scan import file_version

    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            if dirpath[len(root):].count(os.sep) >= 5:
                dirnames[:] = []
            for fn in filenames:
                low = fn.lower()
                if low not in (MODEL_NAME, "nvngx_dlssd.dll"):
                    continue
                full = os.path.join(dirpath, fn)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    continue
                if size < MIN_MODEL_MB << 20:
                    continue
                if low == MODEL_NAME:
                    if size > result["size"]:
                        result.update(path=full, size=size,
                                      version=file_version(full))
                else:
                    result["misnamed"] = full
    return result


# --------------------------------------------------------------------------
# 2. Extraerlo del instalador del driver
# --------------------------------------------------------------------------

def find_installers() -> list[dict]:
    """Instaladores de driver NVIDIA que haya por el disco."""
    out: list[dict] = []
    seen: set[str] = set()
    for d in INSTALLER_DIRS:
        if not d or not os.path.isdir(d):
            continue
        for path in glob.glob(os.path.join(d, "*.exe")) + \
                glob.glob(os.path.join(d, "*", "*.exe")):
            name = os.path.basename(path)
            low = name.lower()
            if not any(k in low for k in ("nvidia", "geforce", "desktop-win",
                                          "notebook-win", "dch")):
                if not re.match(r"^\d{3}\.\d{2}", name):
                    continue
            key = os.path.normcase(path)
            if key in seen:
                continue
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size < 200 << 20:          # un driver completo pasa de 500 MB
                continue
            seen.add(key)
            ver = re.search(r"(\d{3}\.\d{2})", name)
            out.append({"path": path, "name": name, "size": size,
                        "version": ver.group(1) if ver else None})
    out.sort(key=lambda i: i["version"] or "", reverse=True)
    return out


def extract_from_installer(installer: str, dest_dir: str, log=print) -> str | None:
    """Saca nvngx_dlssnr.dll de dentro del .exe del driver con 7-Zip.

    El instalador de NVIDIA es un archivo 7z con cabecera ejecutable, asi que
    7-Zip lo abre directamente sin instalar nada.
    """
    sz = _sevenzip()
    if not sz:
        raise RuntimeError(
            "Hace falta 7-Zip para abrir el instalador del driver. "
            "Instalalo desde 7-zip.org y vuelve a intentarlo.")

    os.makedirs(dest_dir, exist_ok=True)
    log(f"Abriendo {os.path.basename(installer)} con 7-Zip...")

    # Primero se mira si el modelo esta dentro, sin extraer nada.
    listing = _run([sz, "l", installer, "-r", f"*{MODEL_NAME}"], timeout=600)
    if MODEL_NAME not in (listing.stdout or "").lower():
        log(f"  {MODEL_NAME} no esta en este instalador.")
        return None

    log("  encontrado dentro; extrayendo (tarda un poco, son ~165 MB)...")
    res = _run([sz, "e", installer, f"-o{dest_dir}", "-r", f"*{MODEL_NAME}", "-y"],
               timeout=1800)
    got = os.path.join(dest_dir, MODEL_NAME)
    if res.returncode != 0 or not os.path.isfile(got):
        raise RuntimeError("7-Zip no pudo extraer el modelo: "
                           + (res.stderr or res.stdout or "")[-300:])

    size = os.path.getsize(got)
    if size < MIN_MODEL_MB << 20:
        os.remove(got)
        raise RuntimeError(f"Lo extraido pesa {size >> 20} MB, muy poco para "
                           "ser el modelo. Descartado.")

    from dlss5_scan import file_version
    log(f"  listo: {size >> 20} MB, v{file_version(got)}")
    return got


def cache_model(src: str, log=print) -> str:
    """Guarda una copia del modelo en la cache para no repetir la extraccion."""
    dest_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "DLSS5", "modelo")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, MODEL_NAME)
    if os.path.normcase(src) == os.path.normcase(dest):
        return dest
    if not os.path.isfile(dest) or os.path.getsize(dest) != os.path.getsize(src):
        log(f"Guardando copia en la cache ({os.path.getsize(src) >> 20} MB)...")
        shutil.copy2(src, dest)
    return dest


# --------------------------------------------------------------------------
# Orquestador
# --------------------------------------------------------------------------

def obtain(log=print, allow_extract: bool = True) -> dict:
    """Consigue el modelo por el mejor medio disponible.

    Devuelve {'path', 'source', 'detail'}; path es None si no se pudo.
    """
    found = find_existing()
    if found["path"]:
        log(f"Modelo encontrado: {found['path']}")
        return {"path": found["path"], "source": "sistema",
                "detail": f"{found['size'] >> 20} MB, v{found['version']}"}

    if found["misnamed"]:
        log("Encontrado un nvngx_dlssd.dll con tamano de modelo. El README del "
            "fork avisa de que a veces el modelo llega con ese nombre.")
        return {"path": found["misnamed"], "source": "renombrado",
                "detail": "nvngx_dlssd.dll de tamano de modelo"}

    if not allow_extract:
        return {"path": None, "source": None, "detail": "no encontrado"}

    # La fuente real: un juego que ya lo trae.
    log("Buscando el modelo dentro de los juegos instalados...")
    in_game = find_in_games(log=log)
    if in_game:
        return {"path": in_game["path"], "source": "juego",
                "detail": f"{in_game['size'] >> 20} MB, v{in_game['version']}"}

    installers = find_installers()
    if not installers:
        return {"path": None, "source": None, "detail":
                "Ningun juego instalado lo trae, y no hay instaladores de "
                "driver que mirar."}

    for inst in installers:
        log(f"Probando instalador {inst['name']} ({inst['size'] >> 20} MB)...")
        try:
            got = extract_from_installer(
                inst["path"],
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "DLSS5", "modelo"),
                log=log)
        except Exception as e:                      # noqa: BLE001
            log(f"  fallo: {e}")
            continue
        if got:
            return {"path": got, "source": "instalador",
                    "detail": f"extraido de {inst['name']}"}

    return {"path": None, "source": None, "detail":
            "Ninguno de los instaladores encontrados contiene el modelo."}


def driver_ok(driver: str | None) -> bool | None:
    """True/False si el driver es suficientemente nuevo; None si no se sabe."""
    if not driver:
        return None
    try:
        return float(driver.split(".")[0] + "." + driver.split(".")[1]) >= MIN_DRIVER
    except (ValueError, IndexError):
        return None


def help_text(driver: str | None) -> str:
    """Que hacer cuando no aparece el modelo. Sin mandar a callejones sin salida."""
    ok = driver_ok(driver)
    if ok is False:
        return (f"Tu driver ({driver}) es anterior al 616.56, el minimo que "
                "soporta DLSS 5. Actualizalo, aunque eso solo no basta: sigue "
                "haciendo falta el modelo.")
    return (
        "Falta nvngx_dlssnr.dll (~158 MB).\n\n"
        "LO MAS FACIL: si ya tienes el archivo, dejalo en esta misma carpeta,\n"
        f"junto al programa:\n\n    {app_dir()}\n\n"
        "Se detecta solo, sin pulsar nada mas.\n\n"
        "-------------------------------------------------------------\n\n"
        "Si no lo tienes, de donde sale:\n\n"
        "NO viene en el driver. Se comprobo abriendo el instalador oficial "
        "616.64 (938 MB): sus unicos nvngx_* son nvngx.dll, nvngx_dlssg.dll y "
        "nvngx_dlisr.dll. El modelo no esta.\n\n"
        "Lo distribuye cada JUEGO que implementa DLSS 5. A dia de hoy solo uno:\n"
        "  - " + "\n  - ".join(SHIPPING_GAMES) + "\n\n"
        "Cuidado con estos, que salen en el mismo anuncio de NVIDIA pero NO lo "
        "traen:\n  - "
        + "\n  - ".join(f"{k} ({v})" for k, v in NOT_SHIPPING.items()) + "\n\n"
        "Instalalo y pulsa \"Buscar modelo\": se copia de sus archivos y queda "
        "en cache para todos los demas juegos. No hace falta jugarlo.\n\n"
        "El modelo pesa ~158 MB y se identifica como \"NVIDIA DLSSNR\".\n\n"
        "MIENTRAS TANTO: puedes instalar igualmente en tus juegos. OptiScaler "
        "funciona entero sin el modelo (cambio de upscaler, frame generation, "
        "RCAS...); solo el paso neuronal queda apagado, y el overlay dice por "
        "que. Cuando consigas el DLL, vuelve a aplicar y se copia.")
