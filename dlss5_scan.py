"""
Detection: NVIDIA hardware, game executables, graphics API and upscalers present.

Standard library only. No pip, no external binaries. The PE parsing is written
here because 'pefile' would be one more dependency just to read four header
fields.
"""

from __future__ import annotations

import os
import re
import json
import struct
import subprocess
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# File markers
# --------------------------------------------------------------------------

# DLL -> (family, readable label)
UPSCALER_DLLS = {
    "nvngx_dlss.dll":       ("dlss",    "DLSS Super Resolution"),
    "nvngx_dlssg.dll":      ("dlssg",   "DLSS Frame Generation"),
    "nvngx_dlssd.dll":      ("dlssd",   "DLSS Ray Reconstruction"),
    "nvngx_dlssnr.dll":     ("dlssnr",  "DLSS 5 Neural Rendering"),
    "sl.interposer.dll":    ("sl",      "Streamline"),
    "sl.dlss.dll":          ("dlss",    "DLSS (Streamline)"),
    "sl.dlss_g.dll":        ("dlssg",   "DLSS-G (Streamline)"),
    "libxess.dll":          ("xess",    "XeSS"),
    "libxess_dx11.dll":     ("xess",    "XeSS DX11"),
    "libxess_fg.dll":       ("xefg",    "XeSS Frame Generation"),
    "amd_fidelityfx_dx12.dll":              ("fsr", "FidelityFX DX12"),
    "amd_fidelityfx_vk.dll":                ("fsr", "FidelityFX Vulkan"),
    "amd_fidelityfx_upscaler_dx12.dll":     ("fsr", "FSR Upscaler"),
    "amd_fidelityfx_framegeneration_dx12.dll": ("fsrfg", "FSR Frame Generation"),
    "amdxcffx64.dll":       ("fsr4",    "FSR 4"),
}

# Names OptiScaler can take so the game loads it on its own.
PROXY_NAMES = ["dxgi.dll", "winmm.dll", "version.dll", "dbghelp.dll",
               "d3d12.dll", "wininet.dll", "winhttp.dll"]

# Installers and utilities: never hold the executable or an upscaler DLL.
SKIP_DIRS = {
    "_commonredist", "commonredist", "redist", "directx", "dotnet", "vcredist",
    "easyanticheat", "easyanticheat_eos", "battleye", "punkbuster",
    "soundtrack", "artbook", "support", "__installer", "dxsetup",
    "installers", "_dlss5_backup",
}

# Content folders. Pruned for speed, not relevance: they can hold hundreds
# of thousands of files and never an upscaler DLL.
# 'Engine' is NOT here: Unreal keeps nvngx_dlss.dll inside it.
CONTENT_DIRS = {
    "content", "paks", "movies", "audio", "sounds", "music", "videos",
    "textures", "localization", "intermediate", "saved", "logs", "crashes",
    "shadercache", "derivedatacache", "deriveddatacache", "streamingassets",
    "media", "cinematics", "levels", "maps", "meshes", "animations",
}

# Name fragments that give away a launcher or a tool, not the game.
LAUNCHER_HINTS = (
    "launcher", "crashhandler", "crashreport", "crashpad", "unitycrashhandler",
    "setup", "install", "uninstall", "unins", "eosbootstrapper", "bootstrap",
    "vcredist", "dxsetup", "activation", "anticheat", "battleye", "beservice",
    "redist", "config", "touchup", "dotnet", "helper", "service", "updater",
    "cleanup", "diagnostic", "reporter", "webengine", "cefprocess",
    "vconsole", "hammer", "resourcecompiler", "workshop", "dedicated",
    "steamerrorreporter", "benchmark", "editor", "shipping_bootstrap",
)

# Checked in order, most specific marker first, because '/binaries/win64/'
# also shows up in games that are not Unreal.
ENGINE_MARKERS = [
    ("RE Engine",     ("re_chunk_000.pak",)),
    ("REDengine",     ("r6/", "archive/pc/", "red4ext/")),
    ("Creation",      ("data/skyrim.esm", "data/fallout4.esm",
                       "data/starfield.esm", "data/oblivion.esm")),
    ("Unity",         ("unityplayer.dll", "gameassembly.dll")),
    ("Source 2",      ("game/bin/win64/", "game/core/")),
    ("Source",        ("hl2/", "bin/engine.dll")),
    ("id Tech",       ("base/pak000.resources", "idstudiodata/")),
    ("Unreal Engine", ("engine/binaries", "engine/config", "/binaries/win64/")),
]

# Anti-cheats that react badly to a new DLL next to the executable.
ANTICHEAT_MARKERS = {
    "easyanticheat":       "Easy Anti-Cheat",
    "easyanticheat_eos":   "Easy Anti-Cheat (EOS)",
    "battleye":            "BattlEye",
    "beclient.dll":        "BattlEye",
    "beclient_x64.dll":    "BattlEye",
    "eac_launcher.exe":    "Easy Anti-Cheat",
    "easyanticheat_x64.dll": "Easy Anti-Cheat",
    "vanguard":            "Riot Vanguard",
    "mhyprot":             "mhyprot",
    "denuvo":              "Denuvo Anti-Cheat",
}


# --------------------------------------------------------------------------
# PE (Portable Executable) reading
# --------------------------------------------------------------------------

MACHINE = {0x014C: "x86", 0x8664: "x64", 0xAA64: "arm64"}


def pe_info(path: str) -> dict:
    """Architecture and imported DLLs of an .exe/.dll. Headers only."""
    out = {"ok": False, "arch": None, "imports": set(), "subsystem": None}
    try:
        with open(path, "rb") as f:
            if f.read(2) != b"MZ":
                return out
            f.seek(0x3C)
            lfanew = struct.unpack("<I", f.read(4))[0]
            f.seek(lfanew)
            if f.read(4) != b"PE\0\0":
                return out

            machine, nsec, _, _, _, opt_size, _ = struct.unpack("<HHIIIHH", f.read(20))
            out["arch"] = MACHINE.get(machine, hex(machine))
            opt_off = lfanew + 24

            f.seek(opt_off)
            magic = struct.unpack("<H", f.read(2))[0]
            if magic == 0x10B:
                dd_off = opt_off + 96
            elif magic == 0x20B:
                dd_off = opt_off + 112
            else:
                return out

            f.seek(opt_off + 68)
            out["subsystem"] = struct.unpack("<H", f.read(2))[0]

            f.seek(dd_off - 4)
            n_rva = struct.unpack("<I", f.read(4))[0]
            if n_rva < 2:
                out["ok"] = True
                return out

            f.seek(dd_off + 8)              # entry 1 = import table
            imp_rva, _imp_size = struct.unpack("<II", f.read(8))

            # Section table, to translate RVA -> file offset.
            sections = []
            f.seek(opt_off + opt_size)
            for _ in range(nsec):
                raw = f.read(40)
                if len(raw) < 40:
                    break
                vsize, vaddr, rsize, raddr = struct.unpack("<IIII", raw[8:24])
                sections.append((vaddr, max(vsize, rsize), raddr, rsize))

            def rva2off(rva: int):
                for vaddr, vsize, raddr, rsize in sections:
                    if vaddr <= rva < vaddr + vsize:
                        delta = rva - vaddr
                        if delta < rsize:
                            return raddr + delta
                return None

            out["ok"] = True
            if not imp_rva:
                return out

            desc_off = rva2off(imp_rva)
            if desc_off is None:
                return out

            for i in range(1024):           # sanity cap
                f.seek(desc_off + i * 20)
                desc = f.read(20)
                if len(desc) < 20 or desc == b"\0" * 20:
                    break
                name_rva = struct.unpack("<I", desc[12:16])[0]
                name_off = rva2off(name_rva)
                if name_off is None:
                    continue
                f.seek(name_off)
                raw = f.read(96).split(b"\0", 1)[0]
                if raw:
                    out["imports"].add(raw.decode("latin1").lower())
    except Exception:
        pass
    return out


def file_version(path: str) -> str | None:
    """File version, read straight from the bytes of VS_FIXEDFILEINFO.

    Looks for signature 0xFEEF04BD, which is unique and always sits at the
    start of that structure. Cheaper than a full resource parser.
    """
    SIG = b"\xbd\x04\xef\xfe"
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            # Resources usually live at the end, so look there first.
            for start in ((max(0, size - 4 * 1024 * 1024), size), (0, size)):
                f.seek(start[0])
                remaining = start[1] - start[0]
                carry = b""
                pos = start[0]
                while remaining > 0:
                    chunk = f.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    buf = carry + chunk
                    idx = buf.find(SIG)
                    if idx >= 0 and len(buf) >= idx + 16:
                        ms, ls = struct.unpack("<II", buf[idx + 8:idx + 16])
                        return "%d.%d.%d.%d" % (ms >> 16, ms & 0xFFFF,
                                                ls >> 16, ls & 0xFFFF)
                    carry = buf[-4:]
                    pos += len(chunk)
                if start[0] == 0:
                    break
    except Exception:
        pass
    return None


def version_tuple(v: str | None):
    if not v:
        return (0, 0, 0, 0)
    parts = (v.split(".") + ["0"] * 4)[:4]
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return (0, 0, 0, 0)


def contains_text(path: str, needle: str, limit_mb: int = 64) -> bool:
    """Searches a binary for a string, both ASCII and UTF-16LE."""
    a = needle.encode("ascii", "ignore")
    w = needle.encode("utf-16-le")
    try:
        with open(path, "rb") as f:
            left = limit_mb << 20
            carry = b""
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                left -= len(chunk)
                buf = carry + chunk
                if a in buf or w in buf:
                    return True
                carry = buf[-len(w):]
    except Exception:
        pass
    return False


def scan_strings(path: str, needles: list[str], limit_mb: int = 48) -> set[str]:
    """Searches a binary for several strings in a single pass.

    Modern engines load d3d12.dll at run time, so the import table lies by
    omission: the name only appears as a literal inside the .exe.
    """
    found: set[str] = set()
    pats = [(n, n.encode("ascii", "ignore"), n.encode("utf-16-le"))
            for n in needles]
    longest = max((len(p[2]) for p in pats), default=8)
    try:
        with open(path, "rb") as f:
            left = limit_mb << 20
            carry = b""
            while left > 0 and len(found) < len(pats):
                chunk = f.read(1 << 20)
                if not chunk:
                    break
                left -= len(chunk)
                buf = carry + chunk
                for name, a, w in pats:
                    if name not in found and (a in buf or w in buf):
                        found.add(name)
                carry = buf[-longest:]
    except Exception:
        pass
    return found


def is_optiscaler(path: str) -> bool:
    """True if this DLL is really OptiScaler under another name."""
    try:
        if os.path.getsize(path) < 2 << 20:
            return False
    except OSError:
        return False
    return contains_text(path, "OptiScaler")


# --------------------------------------------------------------------------
# System: GPU, driver and Neural Rendering model
# --------------------------------------------------------------------------

RTX50_RE = re.compile(r"RTX\s*50\d0", re.I)

DRIVER_SEARCH = [
    r"C:\Windows\System32",
    r"C:\Windows\System32\DriverStore\FileRepository",
    r"C:\ProgramData\NVIDIA\NGX\models",
    r"C:\Program Files\NVIDIA Corporation\NGX",
]


def _run(cmd: list[str], timeout: int = 12) -> str:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return (p.stdout or "").strip()
    except Exception:
        return ""


def gpu_info() -> dict:
    """GPU name and driver version. nvidia-smi if present, else WMI."""
    info = {"name": None, "driver": None, "rtx50": False, "vendor": None}

    out = _run(["nvidia-smi", "--query-gpu=name,driver_version",
                "--format=csv,noheader"])
    if out:
        first = out.splitlines()[0]
        parts = [p.strip() for p in first.split(",")]
        if parts:
            info["name"] = parts[0]
        if len(parts) > 1:
            info["driver"] = parts[1]

    if not info["name"]:
        out = _run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_VideoController | "
                    "Where-Object {$_.Name -match 'NVIDIA'} | "
                    "Select-Object -First 1 -ExpandProperty Name"], timeout=20)
        if out:
            info["name"] = out.strip()

    if info["name"]:
        info["vendor"] = "NVIDIA" if "nvidia" in info["name"].lower() \
            or "geforce" in info["name"].lower() else "otro"
        info["rtx50"] = bool(RTX50_RE.search(info["name"]))
    return info


def find_dlssnr_model() -> dict:
    """Locates nvngx_dlssnr.dll on the system.

    Also catches the trap the fork README warns about: a ~165 MB
    nvngx_dlssd.dll is not Ray Reconstruction, it is the Neural Rendering
    model under the wrong name.
    """
    result = {"path": None, "size": 0, "version": None, "misnamed": None}

    def consider(p: str):
        try:
            sz = os.path.getsize(p)
        except OSError:
            return
        if sz > result["size"]:
            result["path"] = p
            result["size"] = sz
            result["version"] = file_version(p)

    for root in DRIVER_SEARCH:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # Do not descend more than 4 levels below the search root.
            depth = dirpath[len(root):].count(os.sep)
            if depth >= 4:
                dirnames[:] = []
            for fn in filenames:
                low = fn.lower()
                if low == "nvngx_dlssnr.dll":
                    consider(os.path.join(dirpath, fn))
                elif low == "nvngx_dlssd.dll":
                    full = os.path.join(dirpath, fn)
                    try:
                        if os.path.getsize(full) > 100 << 20:
                            result["misnamed"] = full
                    except OSError:
                        pass
    return result


def harvest_dlss_dlls() -> dict:
    """Finds the newest copy of each nvngx_dlss*.dll already on this PC.

    Lets a game be upgraded without downloading anything: the DLLs are
    already in the driver or in other games.
    """
    best: dict[str, tuple] = {}
    roots = [r"C:\Windows\System32\DriverStore\FileRepository",
             r"C:\Program Files\NVIDIA Corporation"]
    for lib in steam_libraries():
        common = os.path.join(lib, "steamapps", "common")
        if os.path.isdir(common):
            roots.append(common)

    targets = {"nvngx_dlss.dll", "nvngx_dlssg.dll", "nvngx_dlssd.dll"}
    seen = 0
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS]
            if dirpath[len(root):].count(os.sep) >= 6:
                dirnames[:] = []
            for fn in filenames:
                low = fn.lower()
                if low in targets:
                    full = os.path.join(dirpath, fn)
                    ver = file_version(full)
                    cur = best.get(low)
                    if cur is None or version_tuple(ver) > version_tuple(cur[1]):
                        best[low] = (full, ver)
                    seen += 1
            if seen > 400:
                break
    return best


# --------------------------------------------------------------------------
# Installed game libraries
# --------------------------------------------------------------------------

def steam_libraries() -> list[str]:
    libs: list[str] = []
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    for name in ("SteamPath", "InstallPath"):
                        try:
                            p = winreg.QueryValueEx(k, name)[0]
                            if p and os.path.isdir(p):
                                libs.append(os.path.normpath(p))
                        except OSError:
                            pass
            except OSError:
                pass
    except ImportError:
        pass

    extra: list[str] = []
    for base in list(libs):
        vdf = os.path.join(base, "steamapps", "libraryfolders.vdf")
        if os.path.isfile(vdf):
            try:
                with open(vdf, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
                for m in re.finditer(r'"path"\s+"([^"]+)"', text):
                    p = os.path.normpath(m.group(1).replace("\\\\", "\\"))
                    if os.path.isdir(p):
                        extra.append(p)
            except OSError:
                pass
    out, seen = [], set()
    for p in libs + extra:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def installed_games() -> list[dict]:
    """Steam, Epic and GOG game folders. Name and path, not analysed yet."""
    found: list[dict] = []
    seen: set[str] = set()

    def add(name: str, path: str, store: str):
        key = os.path.normcase(os.path.normpath(path))
        if key in seen or not os.path.isdir(path):
            return
        seen.add(key)
        found.append({"name": name, "path": os.path.normpath(path), "store": store})

    # Steam: the .acf files give the exact name and folder.
    for lib in steam_libraries():
        apps = os.path.join(lib, "steamapps")
        if not os.path.isdir(apps):
            continue
        try:
            entries = os.listdir(apps)
        except OSError:
            continue
        for fn in entries:
            if not (fn.startswith("appmanifest_") and fn.endswith(".acf")):
                continue
            try:
                with open(os.path.join(apps, fn), "r", encoding="utf-8",
                          errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            name = re.search(r'"name"\s+"([^"]*)"', text)
            folder = re.search(r'"installdir"\s+"([^"]*)"', text)
            if name and folder:
                add(name.group(1), os.path.join(apps, "common", folder.group(1)),
                    "Steam")

    # Epic: one JSON .item per game.
    epic = r"C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests"
    if os.path.isdir(epic):
        for fn in os.listdir(epic):
            if not fn.lower().endswith(".item"):
                continue
            try:
                with open(os.path.join(epic, fn), "r", encoding="utf-8",
                          errors="replace") as f:
                    data = json.load(f)
                add(data.get("DisplayName") or fn,
                    data.get("InstallLocation") or "", "Epic")
            except Exception:
                pass

    # GOG Galaxy: one registry key per game.
    try:
        import winreg
        for key in (r"SOFTWARE\WOW6432Node\GOG.com\Games",
                    r"SOFTWARE\GOG.com\Games"):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        sub = winreg.EnumKey(k, i)
                        with winreg.OpenKey(k, sub) as g:
                            try:
                                path = winreg.QueryValueEx(g, "path")[0]
                                name = winreg.QueryValueEx(g, "gameName")[0]
                                add(name, path, "GOG")
                            except OSError:
                                pass
            except OSError:
                pass
    except ImportError:
        pass

    found.sort(key=lambda g: g["name"].lower())
    return found


# --------------------------------------------------------------------------
# Analysing a game folder
# --------------------------------------------------------------------------

@dataclass
class Game:
    name: str
    root: str
    store: str = "manual"
    exe: str | None = None            # full path to the chosen executable
    exe_dir: str | None = None        # where the OptiScaler DLLs go
    arch: str | None = None
    engine: str | None = None
    apis: set = field(default_factory=set)         # {'dx12','dx11','vulkan'}
    upscalers: dict = field(default_factory=dict)  # family -> label
    dll_paths: dict = field(default_factory=dict)  # dll name -> path
    dlss_version: str | None = None
    installed_proxy: str | None = None             # OptiScaler already present
    anticheat: set = field(default_factory=set)
    tier: str = "D"
    verdict: str = ""
    notes: list = field(default_factory=list)

    @property
    def key(self) -> str:
        return os.path.normcase(os.path.normpath(self.root))


def _walk_game(root: str, max_depth: int = 9, max_files: int = 200_000):
    """Bounded walk. Returns (exes, dlls_by_name, relative_paths).

    Depth has to reach 9 because Unreal hides the DLL in
    Engine/Plugins/Runtime/Nvidia/DLSS/Binaries/ThirdParty/Win64.
    """
    exes: list[tuple[str, int]] = []
    dlls: dict[str, str] = {}
    rels: set[str] = set()
    anticheat: set[str] = set()
    count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root).replace("\\", "/").lower()
        if rel == ".":
            rel = ""
        depth = 0 if not rel else rel.count("/") + 1
        if depth >= max_depth:
            dirnames[:] = []

        # Anti-cheat is noted before pruning: its folders are in SKIP_DIRS
        # precisely because we do not want to walk them, only to know they exist.
        for d in dirnames:
            hit = ANTICHEAT_MARKERS.get(d.lower())
            if hit:
                anticheat.add(hit)

        dirnames[:] = [d for d in dirnames
                       if d.lower() not in SKIP_DIRS
                       and d.lower() not in CONTENT_DIRS
                       and not d.lower().endswith("_data")]
        if rel:
            rels.add(rel + "/")

        for fn in filenames:
            count += 1
            if count > max_files:
                return exes, dlls, rels, anticheat
            low = fn.lower()
            full = os.path.join(dirpath, fn)
            hit = ANTICHEAT_MARKERS.get(low)
            if hit:
                anticheat.add(hit)
            if low.endswith(".exe"):
                try:
                    exes.append((full, os.path.getsize(full)))
                except OSError:
                    pass
            elif low.endswith(".dll"):
                if low in UPSCALER_DLLS or low in PROXY_NAMES \
                        or low == "unityplayer.dll":
                    dlls.setdefault(low, full)
            rels.add((rel + "/" + low).lstrip("/"))
    return exes, dlls, rels, anticheat


def _score_exe(path: str, size: int, root: str) -> float:
    name = os.path.basename(path).lower()
    rel = os.path.relpath(path, root).replace("\\", "/").lower()
    score = min(size / (1 << 20), 400.0)          # el juego real suele pesar
    if any(h in name for h in LAUNCHER_HINTS):
        score -= 1000
    if "binaries/win64" in rel:
        score += 300
    if "binaries/win32" in rel:
        score += 120
    if "/bin/" in "/" + rel or rel.startswith("bin/"):
        score += 60
    score -= rel.count("/") * 8                   # preferir cerca de la raiz
    if "shipping" in name:
        score += 200
    return score


def analyze(root: str, name: str | None = None, store: str = "manual") -> Game:
    """Analyses a game folder and decides what can be applied to it."""
    g = Game(name=name or os.path.basename(os.path.normpath(root)),
             root=os.path.normpath(root), store=store)

    if not os.path.isdir(root):
        g.verdict = "That folder does not exist."
        return g

    exes, dlls, rels, anticheat = _walk_game(root)
    g.anticheat = anticheat

    # --- main executable -------------------------------------------
    if exes:
        ranked = sorted(exes, key=lambda e: _score_exe(e[0], e[1], root),
                        reverse=True)
        g.exe = ranked[0][0]
        g.exe_dir = os.path.dirname(g.exe)
        pe = pe_info(g.exe)
        g.arch = pe["arch"]
        imports = pe["imports"]
        if any(d.startswith("d3d12") for d in imports):
            g.apis.add("dx12")
        if any(d.startswith("d3d11") for d in imports):
            g.apis.add("dx11")
        if "vulkan-1.dll" in imports:
            g.apis.add("vulkan")
        if any(d.startswith("d3d9") for d in imports):
            g.apis.add("dx9")

    # Imports fall short: almost every engine loads d3d12.dll with
    # LoadLibrary, so the binary strings and whatever sits in the folder have
    # to be checked too.
    if "d3d12core.dll" in dlls or "d3d12.dll" in dlls:
        g.apis.add("dx12")
    scan_target = g.exe
    if "unityplayer.dll" in dlls:
        scan_target = dlls["unityplayer.dll"]     # the Unity .exe is a shell
    if scan_target and "dx12" not in g.apis:
        hits = scan_strings(scan_target,
                            ["d3d12.dll", "d3d11.dll", "vulkan-1.dll"])
        for needle, api in (("d3d12.dll", "dx12"), ("d3d11.dll", "dx11"),
                            ("vulkan-1.dll", "vulkan")):
            if needle in hits:
                g.apis.add(api)

    # DX9 only matters when it is all there is; behind DX11/12 it is just
    # compatibility noise cluttering the report.
    if g.apis & {"dx11", "dx12"}:
        g.apis.discard("dx9")

    # --- engine ------------------------------------------------------------
    joined = "\n".join(rels)
    for label, markers in ENGINE_MARKERS:
        if any(m in joined for m in markers):
            g.engine = label
            break

    # --- upscalers present ---------------------------------------------
    for dll_name, (family, label) in UPSCALER_DLLS.items():
        if dll_name in dlls:
            g.upscalers[family] = label
            g.dll_paths[dll_name] = dlls[dll_name]

    if "nvngx_dlss.dll" in g.dll_paths:
        g.dlss_version = file_version(g.dll_paths["nvngx_dlss.dll"])

    # --- OptiScaler already installed -----------------------------------------
    for proxy in PROXY_NAMES:
        p = dlls.get(proxy)
        if p and is_optiscaler(p):
            g.installed_proxy = p
            break

    _classify(g)
    return g


def _classify(g: Game) -> None:
    """Assigns tier and verdict. No optimism: if it cannot be done, say so."""
    has_dlss = "dlss" in g.upscalers or "sl" in g.upscalers
    has_other = any(k in g.upscalers for k in ("fsr", "xess", "fsr4"))
    dx12 = "dx12" in g.apis
    dx11 = "dx11" in g.apis
    vk = "vulkan" in g.apis
    vulkan_only = vk and not (dx12 or dx11)

    if not g.exe:
        g.tier = "D"
        g.verdict = "No executable found."
        return

    # Since v0.2.0 the neural pass reads the inputs of ANY temporal upscaler,
    # not just DLSS, and Vulkan became natively supported. The one remaining
    # hard requirement is that some upscaler exists to take depth and motion
    # vectors from.
    if has_dlss:
        g.tier = "A"
        g.verdict = "DLSS 5 Neural Rendering applies."
    elif has_other:
        g.tier = "B"
        g.verdict = "Neural Rendering applies over FSR/XeSS."
        g.notes.append("Since v0.2.0 the pass does not need DLSS: it hooks "
                       "FSR or XeSS inputs just as well.")
    else:
        g.tier = "D"
        g.verdict = "No temporal upscaler: nothing to take the vectors from."
        g.notes.append("The pass needs depth and motion vectors, and takes the "
                       "ones the game already hands its upscaler. With no "
                       "upscaler there is nothing to intercept.")
        return

    if dx11 and not dx12:
        g.notes.append("DX11: goes through the D3D11-on-D3D12 bridge, which in "
                       "v0.2.0 carries DLSS directly.")
    if vulkan_only:
        g.notes.append("Native Vulkan: supported since v0.2.0.")
    if not g.apis:
        g.notes.append("Could not confirm the graphics API, but all three "
                       "(DX11, DX12 and Vulkan) are supported.")

    if g.anticheat:
        g.notes.append("ANTI-CHEAT: " + ", ".join(sorted(g.anticheat)) +
                       ". Dropping a DLL next to the executable can get you "
                       "banned. In competitive multiplayer, do not.")


def summary_upscalers(g: Game) -> str:
    if not g.upscalers:
        return "none"
    order = ["dlss", "dlssg", "dlssd", "sl", "xess", "xefg", "fsr", "fsrfg", "fsr4"]
    short = {"dlss": "DLSS", "dlssg": "DLSS-FG", "dlssd": "DLSS-RR", "sl": "SL",
             "xess": "XeSS", "xefg": "XeFG", "fsr": "FSR", "fsrfg": "FSR-FG",
             "fsr4": "FSR4"}
    return " ".join(short[k] for k in order if k in g.upscalers)
