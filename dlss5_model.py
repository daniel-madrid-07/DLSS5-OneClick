"""
Getting hold of nvngx_dlssnr.dll, which is what actually blocks everything else.

VERIFIED on 5 Sept 2026 by downloading and opening the official 616.64
installer (938 MB, us.download.nvidia.com): the model is NOT in the driver. The
package's only nvngx_* files are nvngx.dll, nvngx_dlssg.dll, nvngx_dlisr.dll
and nvngx_update.exe. No trace of dlssnr.

EVERY GAME that implements DLSS 5 ships the model itself. It was first found
inside NBA 2K27 (158 MB, "NVIDIA DLSSNR" v310.8.0.0), so the only clean source
is an installed game with official DLSS 5.

Ways to get it, cleanest first:

  1. Already next to this program, or a previous copy in the cache.
  2. Inside an installed game with official DLSS 5 -> copied out.
  3. Inside a driver installer -> extracted with 7-Zip. None ships it today,
     but that can change and looking costs nothing.
  4. Nothing at all -> say so, instead of sending anyone after a useless driver.

The DLL is never downloaded from third-party repositories. It is NVIDIA's, and
the sites that repackage it are precisely the ones to avoid.
"""

from __future__ import annotations

import os
import re
import sys
import glob
import shutil
import subprocess

# The model is ~165 MB. Anything far below that is not the model.
MIN_MODEL_MB = 100
MODEL_NAME = "nvngx_dlssnr.dll"

# Minimum driver version that supports it, per the fork release notes.
MIN_DRIVER = 616.56

SEVENZIP = [
    r"C:\Program Files\7-Zip\7z.exe",
    r"C:\Program Files (x86)\7-Zip\7z.exe",
    "7z",
]

# Where a driver installer usually ends up after downloading.
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
# 1. Look for copies that already exist
# --------------------------------------------------------------------------

# Games that ship the model inside their own files.
#
# Checked on 5 Sept 2026 against NVIDIA's announcement: the only title with
# Neural Rendering is NBA 2K27. Onimusha and Dawnwalker appear in the same
# article but only get DLSS 4.5 (Super Resolution and Multi Frame Generation),
# so they do NOT carry nvngx_dlssnr.dll. Onimusha's free demo does not either.
SHIPPING_GAMES = ["NBA 2K27"]

# Games that sound like DLSS 5 but do not ship the model. Listed so nobody is
# sent off to install 100 GB for nothing.
NOT_SHIPPING = {
    "Onimusha: Way of the Sword": "DLSS 4.5 only, and the free demo too",
    "The Blood of Dawnwalker": "DLSS 4.5 only",
    "STAR WARS Zero Company": "DLSS 4.5 only",
}


def find_in_games(log=print) -> dict | None:
    """Looks for the model inside the installed games.

    This is the real source: NBA 2K27 was the first to ship it, and any game
    with official DLSS 5 carries it in its own folder.
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
                    log(f"  found inside a game: {full}")
                    return {"path": full, "size": size,
                            "version": file_version(full)}
    return None


def app_dir() -> str:
    """The folder the program runs from.

    Under PyInstaller, sys.executable is the .exe while __file__ points at the
    temporary extraction directory, which is useless to anyone. What matters
    here is always the folder where the user put the executable.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def find_existing(extra_roots: list[str] | None = None) -> dict:
    """Looks for an nvngx_dlssnr.dll already present on the system.

    Also recognises the case the fork README warns about: a model-sized
    nvngx_dlssd.dll is not Ray Reconstruction, it is Neural Rendering under
    the wrong name.
    """
    result = {"path": None, "size": 0, "version": None, "misnamed": None}

    roots = [
        # First, next to the program itself: that is where anyone who gets the
        # DLL on their own will drop it, with no folder to hunt for.
        app_dir(),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "DLSS5", "model"),
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
# 2. Extract it from the driver installer
# --------------------------------------------------------------------------

def find_installers() -> list[dict]:
    """Any NVIDIA driver installers sitting on disk."""
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
            if size < 200 << 20:          # a full driver package exceeds 500 MB
                continue
            seen.add(key)
            ver = re.search(r"(\d{3}\.\d{2})", name)
            out.append({"path": path, "name": name, "size": size,
                        "version": ver.group(1) if ver else None})
    out.sort(key=lambda i: i["version"] or "", reverse=True)
    return out


def extract_from_installer(installer: str, dest_dir: str, log=print) -> str | None:
    """Pulls nvngx_dlssnr.dll out of the driver .exe with 7-Zip.

    NVIDIA's installer is a 7z archive with an executable header, so 7-Zip
    opens it directly without installing anything.
    """
    sz = _sevenzip()
    if not sz:
        raise RuntimeError(
            "Hace falta 7-Zip para abrir el instalador del driver. "
            "Instalalo desde 7-zip.org y vuelve a intentarlo.")

    os.makedirs(dest_dir, exist_ok=True)
    log(f"Abriendo {os.path.basename(installer)} con 7-Zip...")

    # First check whether the model is inside, without extracting anything.
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
    """Caches a copy of the model so the extraction is not repeated."""
    dest_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "DLSS5", "model")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, MODEL_NAME)
    if os.path.normcase(src) == os.path.normcase(dest):
        return dest
    if not os.path.isfile(dest) or os.path.getsize(dest) != os.path.getsize(src):
        log(f"Guardando copia en la cache ({os.path.getsize(src) >> 20} MB)...")
        shutil.copy2(src, dest)
    return dest


# --------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------

def obtain(log=print, allow_extract: bool = True) -> dict:
    """Obtains the model by the best available means.

    Returns {'path', 'source', 'detail'}; path is None when it could not.
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

    # The real source: a game that already ships it.
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
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "DLSS5", "model"),
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
    """True/False whether the driver is new enough; None when unknown."""
    if not driver:
        return None
    try:
        return float(driver.split(".")[0] + "." + driver.split(".")[1]) >= MIN_DRIVER
    except (ValueError, IndexError):
        return None


def help_text(driver: str | None) -> str:
    """What to do when the model does not turn up. No dead ends."""
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
