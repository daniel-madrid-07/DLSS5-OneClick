"""
Instalacion, configuracion y marcha atras.

No se reimplementa el hook de DirectX: eso lo hace OptiScaler, que lleva anos
y 10.000 estrellas de trabajo encima. Aqui se decide que copiar, donde, con que
ajustes, y como deshacerlo entero.
"""

from __future__ import annotations

import os
import json
import shutil
import zipfile
import hashlib
import tempfile
import datetime
import urllib.request

from dlss5_scan import Game, PROXY_NAMES, find_dlssnr_model

CACHE = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "DLSS5")
BACKUP_DIR = "_DLSS5_backup"
MANIFEST = "manifest.json"

UA = {"User-Agent": "dlss5-oneclick/1.0"}


# --------------------------------------------------------------------------
# Origenes. Solo repositorios oficiales, nada de mirrors ni "manager apps".
# --------------------------------------------------------------------------

SOURCES = {
    "dlssnr": {
        "repo": "Dagherbou/OptiScaler_DLSSNR",
        "label": "OptiScaler + DLSS 5 Neural Rendering",
        "match": lambda n: n.lower().endswith(".zip") and "dlssnr" in n.lower(),
        "note": "Fork de OptiScaler (GPL-3.0) que anade el paso de Neural Rendering.",
    },
    "stable": {
        "repo": "optiscaler/OptiScaler",
        "label": "OptiScaler estable",
        "match": lambda n: n.lower().endswith((".7z", ".zip")),
        "note": "Version oficial. Sin Neural Rendering, pero mas probada.",
    },
}


# --------------------------------------------------------------------------
# Ajustes preestablecidos para el paso de Neural Rendering
# --------------------------------------------------------------------------
#
# Los nombres y rangos salen del propio OptiScaler.ini del fork:
#   TransferStrength  cuanto se mueve el fotograma hacia la imagen del modelo
#   ColourStrength    si llega tambien el color del modelo o solo su luz
#   MaxRatio          tope de cuanto puede aclarar un pixel
#   WorkingScale      fraccion del fotograma a la que trabaja el modelo
#
PRESETS = {
    "suave": {
        "label": "Suave  -  respeta el arte original",
        "DlssNr": {"TransferStrength": "0.5", "ColourStrength": "0.35",
                   "MaxRatio": "1.5", "WorkingScale": "1.0", "Intensity": "1.0"},
    },
    "equilibrado": {
        "label": "Equilibrado  -  recomendado",
        "DlssNr": {"TransferStrength": "1.0", "ColourStrength": "0.6",
                   "MaxRatio": "2.0", "WorkingScale": "1.0", "Intensity": "1.0"},
    },
    "maximo": {
        "label": "Maximo detalle  -  se nota, y se paga",
        "DlssNr": {"TransferStrength": "1.25", "ColourStrength": "1.0",
                   "MaxRatio": "2.5", "WorkingScale": "1.0", "Intensity": "1.2"},
    },
    "rendimiento": {
        "label": "Rendimiento  -  el modelo trabaja a media resolucion",
        "DlssNr": {"TransferStrength": "1.0", "ColourStrength": "0.6",
                   "MaxRatio": "2.0", "WorkingScale": "0.5", "Intensity": "1.0"},
    },
}


# --------------------------------------------------------------------------
# Descarga con cache
# --------------------------------------------------------------------------

def _cache_dir(*parts) -> str:
    p = os.path.join(CACHE, *parts)
    os.makedirs(p, exist_ok=True)
    return p


def resolve_release(kind: str, log=print) -> dict:
    """Consulta la API de GitHub y devuelve tag + asset a descargar."""
    src = SOURCES[kind]
    repo = src["repo"]
    urls = [f"https://api.github.com/repos/{repo}/releases/latest",
            f"https://api.github.com/repos/{repo}/releases?per_page=10"]

    last_err = None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:                       # noqa: BLE001
            last_err = e
            continue

        releases = data if isinstance(data, list) else [data]
        for rel in releases:
            if rel.get("draft"):
                continue
            for asset in rel.get("assets", []):
                if src["match"](asset["name"]):
                    return {"tag": rel["tag_name"], "name": asset["name"],
                            "url": asset["browser_download_url"],
                            "size": asset.get("size", 0), "repo": repo}
    raise RuntimeError(f"No se pudo consultar {repo}: {last_err}")


def download(url: str, dest: str, expected: int = 0, progress=None) -> str:
    """Descarga a dest si no esta ya cacheado con el tamano correcto."""
    if os.path.isfile(dest) and (not expected or os.path.getsize(dest) == expected):
        if progress:
            progress(1.0, "ya descargado")
        return dest

    tmp = dest + ".part"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        total = int(r.headers.get("Content-Length") or expected or 0)
        done = 0
        h = hashlib.sha256()
        with open(tmp, "wb") as f:
            while True:
                chunk = r.read(1 << 18)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done / total, f"{done >> 20} / {total >> 20} MB")
    os.replace(tmp, dest)
    with open(dest + ".sha256", "w", encoding="utf-8") as f:
        f.write(h.hexdigest())
    return dest


def ensure_package(kind: str, progress=None, log=print) -> str:
    """Devuelve la carpeta con el paquete ya extraido, descargandolo si hace falta."""
    rel = resolve_release(kind, log=log)
    log(f"Release: {rel['repo']} {rel['tag']}  ({rel['size'] >> 20} MB)")

    archive = os.path.join(_cache_dir("descargas"), rel["name"])
    download(rel["url"], archive, rel["size"], progress)

    out = os.path.join(_cache_dir("paquetes"), f"{kind}-{rel['tag']}")
    marker = os.path.join(out, ".ok")
    if os.path.isfile(marker):
        log("Paquete ya extraido.")
        return out

    if os.path.isdir(out):
        shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out, exist_ok=True)

    if archive.lower().endswith(".zip"):
        log("Extrayendo...")
        with zipfile.ZipFile(archive) as z:
            z.extractall(out)
    else:
        _extract_7z(archive, out, log)

    with open(marker, "w", encoding="utf-8") as f:
        f.write(rel["tag"])
    return out


def _extract_7z(archive: str, out: str, log=print) -> None:
    """Los releases estables vienen en .7z; se prueba 7z y luego tar de Windows."""
    for cmd in (["7z", "x", "-y", f"-o{out}", archive],
                ["C:\\Program Files\\7-Zip\\7z.exe", "x", "-y", f"-o{out}", archive],
                ["tar", "-xf", archive, "-C", out]):
        try:
            import subprocess
            p = subprocess.run(cmd, capture_output=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if p.returncode == 0 and os.listdir(out):
                return
        except Exception:                            # noqa: BLE001
            continue
    raise RuntimeError("No se pudo extraer el .7z. Instala 7-Zip o usa el paquete "
                       "DLSS 5 (que viene en .zip).")


# --------------------------------------------------------------------------
# Edicion del INI conservando comentarios
# --------------------------------------------------------------------------

def set_ini(path: str, changes: dict[str, dict[str, str]]) -> None:
    """Aplica cambios {seccion: {clave: valor}} sin perder los comentarios.

    El INI de OptiScaler es en buena parte documentacion; reescribirlo con
    configparser lo dejaria ilegible.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()

    pending = {s: dict(kv) for s, kv in changes.items()}
    out: list[str] = []
    section = None
    section_end: dict[str, int] = {}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if section in pending:
                section_end[section] = len(out)
            section = stripped[1:-1]
        elif section in pending and "=" in stripped and not stripped.startswith(";"):
            key = stripped.split("=", 1)[0].strip()
            if key in pending[section]:
                line = f"{key}={pending[section].pop(key)}"
        out.append(line)

    if section in pending:
        section_end[section] = len(out)

    # Claves que no existian: se anaden al final de su seccion, de abajo arriba
    # para que los indices guardados sigan siendo validos.
    for sect in sorted(pending, key=lambda s: section_end.get(s, len(out)), reverse=True):
        leftovers = pending[sect]
        if not leftovers:
            continue
        block = [f"{k}={v}" for k, v in leftovers.items()]
        if sect in section_end:
            at = section_end[sect]
            out[at:at] = block
        else:
            out += ["", f"[{sect}]"] + block

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def build_config(game: Game, preset: str, neural: bool, log_on: bool = False) -> dict:
    """Construye el conjunto de cambios del INI para este juego."""
    cfg: dict[str, dict[str, str]] = {
        "Menu": {"OverlayMenu": "true"},
        "Log": {"LoggingEnabled": "true" if log_on else "false"},
    }

    if neural:
        nr = dict(PRESETS[preset]["DlssNr"])
        nr.update({"Enabled": "true", "DebugView": "0", "AutoCapture": "false",
                   "AutoMask": "true"})
        cfg["DlssNr"] = nr

    # Si el juego no trae DLSS, se le pide a OptiScaler que lo use de salida.
    if game.tier == "B":
        cfg["Upscalers"] = {"Dx12Upscaler": "dlss", "Dx11Upscaler": "dlss"}

    return cfg


# --------------------------------------------------------------------------
# Instalar
# --------------------------------------------------------------------------

def pick_proxy(exe_dir: str) -> str:
    """Elige un nombre de DLL libre que el juego cargue automaticamente."""
    for name in PROXY_NAMES:
        if not os.path.exists(os.path.join(exe_dir, name)):
            return name
    return "winmm.dll"


def _backup_path(exe_dir: str) -> str:
    return os.path.join(exe_dir, BACKUP_DIR)


def read_manifest(exe_dir: str) -> dict | None:
    p = os.path.join(_backup_path(exe_dir), MANIFEST)
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:                            # noqa: BLE001
            return None
    return None


def install(game: Game, preset: str = "equilibrado", kind: str = "dlssnr",
            neural: bool = True, copy_model: bool = True,
            progress=None, log=print) -> dict:
    """Copia el paquete al juego, deja copia de seguridad y escribe el INI."""
    if not game.exe_dir:
        raise RuntimeError("No se identifico la carpeta del ejecutable.")

    exe_dir = game.exe_dir
    if read_manifest(exe_dir):
        raise RuntimeError("Ya hay una instalacion aqui. Revierte antes de repetir.")

    pkg = ensure_package(kind, progress=progress, log=log)

    # El .zip puede traer todo dentro de una carpeta unica; se busca la raiz real.
    root = pkg
    entries = os.listdir(pkg)
    if len(entries) == 1 and os.path.isdir(os.path.join(pkg, entries[0])):
        root = os.path.join(pkg, entries[0])
    if not os.path.isfile(os.path.join(root, "OptiScaler.dll")):
        for dirpath, _dirs, files in os.walk(pkg):
            if "OptiScaler.dll" in files:
                root = dirpath
                break

    if not os.path.isfile(os.path.join(root, "OptiScaler.dll")):
        raise RuntimeError("El paquete descargado no contiene OptiScaler.dll.")

    backup = _backup_path(exe_dir)
    os.makedirs(backup, exist_ok=True)

    manifest = {
        "version": 1,
        "fecha": datetime.datetime.now().isoformat(timespec="seconds"),
        "paquete": os.path.basename(pkg),
        "origen": SOURCES[kind]["repo"],
        "exe_dir": exe_dir,
        "juego": game.name,
        "preset": preset,
        "neural": neural,
        "creados": [],
        "respaldados": {},
    }

    def place(src: str, rel_dest: str) -> None:
        dest = os.path.join(exe_dir, rel_dest)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            saved = os.path.join(backup, rel_dest)
            os.makedirs(os.path.dirname(saved), exist_ok=True)
            if not os.path.exists(saved):
                shutil.copy2(dest, saved)
                manifest["respaldados"][rel_dest] = rel_dest
        else:
            manifest["creados"].append(rel_dest)
        shutil.copy2(src, dest)

    proxy = pick_proxy(exe_dir)
    log(f"OptiScaler se instalara como {proxy}")

    skip = {"optiscaler.dll", "setup_windows.bat", "setup_linux.sh",
            "streamlined_fetcher_windows.bat"}
    for name in os.listdir(root):
        full = os.path.join(root, name)
        if os.path.isdir(full):
            for dirpath, _dirs, files in os.walk(full):
                for fn in files:
                    src = os.path.join(dirpath, fn)
                    rel = os.path.relpath(src, root)
                    place(src, rel)
        elif name.lower() not in skip and not name.startswith("!!"):
            place(full, name)

    place(os.path.join(root, "OptiScaler.dll"), proxy)
    manifest["proxy"] = proxy

    # --- INI ---------------------------------------------------------------
    ini = os.path.join(exe_dir, "OptiScaler.ini")
    if os.path.isfile(ini):
        set_ini(ini, build_config(game, preset, neural))
        log(f"OptiScaler.ini configurado ({preset}).")

    # --- modelo de Neural Rendering ---------------------------------------
    if neural and copy_model:
        model = find_dlssnr_model()
        src = model["path"] or model["misnamed"]
        if src:
            if model["misnamed"] and not model["path"]:
                log("Usando un nvngx_dlssd.dll de tamano de modelo: el README "
                    "del fork avisa de que a veces llega con ese nombre.")
            log(f"Copiando el modelo ({os.path.getsize(src) >> 20} MB)...")
            dest_rel = "nvngx_dlssnr.dll"
            dest = os.path.join(exe_dir, dest_rel)
            if not os.path.exists(dest):
                manifest["creados"].append(dest_rel)
            shutil.copy2(src, dest)
            manifest["modelo"] = src
        else:
            log("AVISO: no hay nvngx_dlssnr.dll en el sistema. Neural Rendering "
                "quedara apagado hasta que instales un driver que lo incluya.")
            manifest["modelo"] = None

    with open(os.path.join(backup, MANIFEST), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    log("Instalacion terminada.")
    return manifest


# --------------------------------------------------------------------------
# Revertir
# --------------------------------------------------------------------------

def revert(exe_dir: str, log=print) -> None:
    """Deja la carpeta exactamente como estaba."""
    manifest = read_manifest(exe_dir)
    if not manifest:
        raise RuntimeError("No hay copia de seguridad en esta carpeta.")

    backup = _backup_path(exe_dir)

    for rel in manifest.get("creados", []):
        p = os.path.join(exe_dir, rel)
        if os.path.isfile(p):
            try:
                os.remove(p)
            except OSError as e:
                log(f"  no se pudo borrar {rel}: {e}")

    for rel in manifest.get("respaldados", {}):
        src = os.path.join(backup, rel)
        dest = os.path.join(exe_dir, rel)
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
            log(f"  restaurado {rel}")

    # Solo se borran las carpetas que creamos nosotros, deducidas de las rutas
    # del manifiesto. Barrer todo el arbol se llevaria por delante carpetas
    # vacias que ya existian antes, y eso no seria dejarlo "como estaba".
    ours: set[str] = set()
    for rel in manifest.get("creados", []):
        parent = os.path.dirname(rel)
        while parent:
            ours.add(parent)
            parent = os.path.dirname(parent)
    for rel in sorted(ours, key=lambda p: p.count(os.sep), reverse=True):
        p = os.path.join(exe_dir, rel)
        if os.path.isdir(p):
            try:
                os.rmdir(p)                       # falla sola si no esta vacia
            except OSError:
                pass

    for extra in ("OptiScaler.log", "dlssnr-capture"):
        p = os.path.join(exe_dir, extra)
        if os.path.isfile(p):
            os.remove(p)
        elif os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)

    shutil.rmtree(backup, ignore_errors=True)
    log("Revertido. La carpeta esta como al principio.")


# --------------------------------------------------------------------------
# Actualizar el DLL de DLSS con la copia mas nueva del propio PC
# --------------------------------------------------------------------------

def upgrade_dlss_dll(game: Game, harvest: dict, log=print) -> bool:
    """Sustituye nvngx_dlss*.dll del juego por la version mas nueva encontrada.

    No descarga nada: usa lo que ya hay en el driver o en otros juegos, que es
    la unica forma limpia de hacerlo.
    """
    from dlss5_scan import version_tuple

    if not game.exe_dir:
        return False
    changed = False
    backup = _backup_path(game.exe_dir)

    for dll_name, (src, newver) in harvest.items():
        cur_path = game.dll_paths.get(dll_name)
        if not cur_path:
            continue
        curver = None
        from dlss5_scan import file_version
        curver = file_version(cur_path)
        if version_tuple(newver) <= version_tuple(curver):
            continue

        os.makedirs(backup, exist_ok=True)
        saved = os.path.join(backup, dll_name)
        if not os.path.exists(saved):
            shutil.copy2(cur_path, saved)
        shutil.copy2(src, cur_path)
        log(f"  {dll_name}: {curver} -> {newver}")
        changed = True

    return changed
