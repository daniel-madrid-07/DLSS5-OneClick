"""
Install, configuration and rollback.

The DirectX hook is not reimplemented here: OptiScaler does that, with years
and 10,000 stars of work behind it. This module decides what to copy, where,
with which settings, and how to undo all of it.
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

from dlss5_scan import Game, PROXY_NAMES
import dlss5_model

CACHE = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "DLSS5")
BACKUP_DIR = "_DLSS5_backup"
MANIFEST = "manifest.json"

UA = {"User-Agent": "dlss5-oneclick/1.0"}


# --------------------------------------------------------------------------
# Sources. Official repositories only - no mirrors, no "manager apps".
# --------------------------------------------------------------------------

SOURCES = {
    "dlssnr": {
        "repo": "Dagherbou/OptiScaler_DLSSNR",
        "label": "OptiScaler + DLSS 5 Neural Rendering",
        "match": lambda n: n.lower().endswith(".zip") and "dlssnr" in n.lower(),
        "note": "OptiScaler fork (GPL-3.0) adding the Neural Rendering pass.",
    },
    "stable": {
        "repo": "optiscaler/OptiScaler",
        "label": "OptiScaler stable",
        "match": lambda n: n.lower().endswith((".7z", ".zip")),
        "note": "Official build. No Neural Rendering, but better tested.",
    },
}


# --------------------------------------------------------------------------
# Presets for the Neural Rendering pass
# --------------------------------------------------------------------------
#
# Names and ranges come from the fork's own OptiScaler.ini:
#   TransferStrength  how far the frame moves toward the model's picture
#   ColourStrength    whether the model's colour arrives with its light
#   MaxRatio          cap on how much a pixel may brighten
#   WorkingScale      fraction of the frame the model works at
#
# WorkingScale above 1.0 supersamples the model (DX12 and Vulkan, since
# v0.2.0); ScalingDownscaler picks the filter that averages the answer back
# down: 4 = Lanczos3, the one the INI itself recommends.
PRESETS = {
    "subtle": {
        "label": "Subtle  -  respects the original art",
        "DlssNr": {"TransferStrength": "0.5", "ColourStrength": "0.35",
                   "MaxRatio": "1.5", "WorkingScale": "1.0", "Intensity": "1.0"},
    },
    "balanced": {
        "label": "Balanced  -  recommended",
        "DlssNr": {"TransferStrength": "1.0", "ColourStrength": "0.6",
                   "MaxRatio": "2.0", "WorkingScale": "1.0", "Intensity": "1.0"},
    },
    "maximum": {
        "label": "Maximum detail  -  visible, and you pay for it",
        "DlssNr": {"TransferStrength": "1.25", "ColourStrength": "1.0",
                   "MaxRatio": "2.5", "WorkingScale": "1.0", "Intensity": "1.2"},
    },
    "supersampling": {
        "label": "Supersampling  -  model above native, less noise",
        "DlssNr": {"TransferStrength": "1.0", "ColourStrength": "0.6",
                   "MaxRatio": "2.0", "WorkingScale": "1.5", "Intensity": "1.0",
                   "ScalingDownscaler": "4"},
    },
    "performance": {
        "label": "Performance  -  model runs at half resolution",
        "DlssNr": {"TransferStrength": "1.0", "ColourStrength": "0.6",
                   "MaxRatio": "2.0", "WorkingScale": "0.5", "Intensity": "1.0"},
    },
}


# --------------------------------------------------------------------------
# Cached download
# --------------------------------------------------------------------------

def _cache_dir(*parts) -> str:
    p = os.path.join(CACHE, *parts)
    os.makedirs(p, exist_ok=True)
    return p


def resolve_release(kind: str, log=print) -> dict:
    """Queries the GitHub API and returns the tag plus asset to download."""
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
    raise RuntimeError(f"Could not reach {repo}: {last_err}")


def download(url: str, dest: str, expected: int = 0, progress=None) -> str:
    """Downloads to dest unless already cached at the right size."""
    if os.path.isfile(dest) and (not expected or os.path.getsize(dest) == expected):
        if progress:
            progress(1.0, "already downloaded")
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
    """Returns the folder with the package extracted, downloading if needed."""
    rel = resolve_release(kind, log=log)
    log(f"Release: {rel['repo']} {rel['tag']}  ({rel['size'] >> 20} MB)")

    archive = os.path.join(_cache_dir("descargas"), rel["name"])
    download(rel["url"], archive, rel["size"], progress)

    out = os.path.join(_cache_dir("paquetes"), f"{kind}-{rel['tag']}")
    marker = os.path.join(out, ".ok")
    if os.path.isfile(marker):
        log("Package already extracted.")
        return out

    if os.path.isdir(out):
        shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out, exist_ok=True)

    if archive.lower().endswith(".zip"):
        log("Extracting...")
        with zipfile.ZipFile(archive) as z:
            z.extractall(out)
    else:
        _extract_7z(archive, out, log)

    with open(marker, "w", encoding="utf-8") as f:
        f.write(rel["tag"])
    return out


def _extract_7z(archive: str, out: str, log=print) -> None:
    """Stable releases ship as .7z; try 7z first, then Windows tar."""
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
    raise RuntimeError("Could not extract the .7z. Install 7-Zip or use the "
                       "DLSS 5 package, which ships as .zip.")


# --------------------------------------------------------------------------
# INI editing that preserves comments
# --------------------------------------------------------------------------

def read_ini(path: str) -> dict[str, dict[str, str]]:
    """Reads an INI into {section: {key: value}}. Comments are ignored.

    configparser is avoided because the file carries commented-out duplicate
    keys and values with characters it chokes on.
    """
    out: dict[str, dict[str, str]] = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            section = None
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith(";"):
                    continue
                if stripped.startswith("[") and stripped.endswith("]"):
                    section = stripped[1:-1]
                    out.setdefault(section, {})
                elif section and "=" in stripped:
                    key, _, value = stripped.partition("=")
                    out[section][key.strip()] = value.strip()
    except OSError:
        pass
    return out


def game_ini_path(exe_dir: str) -> str | None:
    """Path to a game's OptiScaler.ini, if it is installed."""
    p = os.path.join(exe_dir, "OptiScaler.ini")
    return p if os.path.isfile(p) else None


def set_ini(path: str, changes: dict[str, dict[str, str]]) -> None:
    """Applies {section: {key: value}} changes without losing the comments.

    OptiScaler's INI is largely documentation; rewriting it with configparser
    would leave it unreadable.
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

    # Keys that did not exist are appended to the end of their section,
    # bottom-up so the stored indices stay valid.
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
    """Builds the set of INI changes for this game."""
    cfg: dict[str, dict[str, str]] = {
        # F8 opens the overlay. OptiScaler defaults to Insert, but plenty of
        # games and the Steam/RTSS layers already use it. 0x77 = VK_F8.
        "Menu": {"OverlayMenu": "true", "ShortcutKey": "0x77"},
        # The key is LogToFile, not LoggingEnabled: that one does not exist in
        # the INI and was left at the end of [Log] doing nothing.
        "Log": {"LogToFile": "true" if log_on else "false"},
    }

    if neural:
        nr = dict(PRESETS[preset]["DlssNr"])
        nr.update({"Enabled": "true", "DebugView": "0", "AutoCapture": "false",
                   "AutoMask": "true"})
        # F10 toggles the pass in game without opening the overlay. It is the
        # only honest way to see whether it is doing anything.
        nr.setdefault("ToggleKey", "0x79")
        cfg["DlssNr"] = nr

    # DLSS is no longer forced as the output upscaler on FSR/XeSS games:
    # since v0.2.0 the neural pass reads the inputs of any of the three, so
    # swapping the upscaler would only add risk for nothing in return.
    return cfg


# --------------------------------------------------------------------------
# Install
# --------------------------------------------------------------------------

def pick_proxy(exe_dir: str) -> str:
    """Picks a free DLL name the game will load on its own."""
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


def install(game: Game, preset: str = "balanced", kind: str = "dlssnr",
            neural: bool = True, copy_model: bool = True,
            model_path: str | None = None,
            progress=None, log=print) -> dict:
    """Copies the package into the game, backs up, and writes the INI."""
    if not game.exe_dir:
        raise RuntimeError("Could not identify the executable folder.")

    exe_dir = game.exe_dir
    if read_manifest(exe_dir):
        raise RuntimeError("There is already an install here. Revert first.")

    pkg = ensure_package(kind, progress=progress, log=log)

    # The .zip may nest everything in a single folder; find the real root.
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
        raise RuntimeError("The downloaded package has no OptiScaler.dll.")

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
    log(f"OptiScaler will install as {proxy}")

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
        log(f"OptiScaler.ini configured ({preset}).")

    # --- Neural Rendering model ---------------------------------------
    if neural and copy_model:
        got = model_path or dlss5_model.obtain(log=log)["path"]
        if got:
            log(f"Copying the model ({os.path.getsize(got) >> 20} MB)...")
            dest_rel = dlss5_model.MODEL_NAME
            dest = os.path.join(exe_dir, dest_rel)
            if not os.path.exists(dest):
                manifest["creados"].append(dest_rel)
            shutil.copy2(got, dest)
            manifest["modelo"] = got
        else:
            log("NOTE: nvngx_dlssnr.dll was not found. OptiScaler is installed "
                "and working, but the neural pass stays off until you get the "
                "model (\"Find model\" button).")
            manifest["modelo"] = None

    with open(os.path.join(backup, MANIFEST), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    log("Install finished.")
    return manifest


# --------------------------------------------------------------------------
# Revert
# --------------------------------------------------------------------------

def revert(exe_dir: str, log=print) -> None:
    """Leaves the folder exactly as it was."""
    manifest = read_manifest(exe_dir)
    if not manifest:
        raise RuntimeError("There is no backup in this folder.")

    backup = _backup_path(exe_dir)

    for rel in manifest.get("creados", []):
        p = os.path.join(exe_dir, rel)
        if os.path.isfile(p):
            try:
                os.remove(p)
            except OSError as e:
                log(f"  could not delete {rel}: {e}")

    for rel in manifest.get("respaldados", {}):
        src = os.path.join(backup, rel)
        dest = os.path.join(exe_dir, rel)
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
            log(f"  restored {rel}")

    # Only folders we created are removed, derived from the manifest paths.
    # Sweeping the whole tree would take out empty folders that already
    # existed, and that would not be leaving it "as it was".
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
                os.rmdir(p)                       # fails on its own if not empty
            except OSError:
                pass

    for extra in ("OptiScaler.log", "dlssnr-capture"):
        p = os.path.join(exe_dir, extra)
        if os.path.isfile(p):
            os.remove(p)
        elif os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)

    shutil.rmtree(backup, ignore_errors=True)
    log("Reverted. The folder is back to its original state.")


# --------------------------------------------------------------------------
# Upgrade the game DLSS DLL with the newest copy on this PC
# --------------------------------------------------------------------------

def upgrade_dlss_dll(game: Game, harvest: dict, log=print) -> bool:
    """Replaces the game's nvngx_dlss*.dll with the newest version found.

    Downloads nothing: it uses what the driver or other games already put on
    disk, which is the only clean way to do it.
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
