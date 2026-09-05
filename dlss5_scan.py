"""
Deteccion: hardware NVIDIA, ejecutables de juego, API grafica y upscalers presentes.

Todo con la libreria estandar de Python. Nada de pip, nada de binarios externos.
El parseo de PE es propio porque 'pefile' seria una dependencia mas para leer
cuatro campos de una cabecera.
"""

from __future__ import annotations

import os
import re
import json
import struct
import subprocess
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Marcadores de archivos
# --------------------------------------------------------------------------

# DLL -> (familia, etiqueta legible)
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

# Nombres que OptiScaler puede adoptar para que el juego lo cargue solo.
PROXY_NAMES = ["dxgi.dll", "winmm.dll", "version.dll", "dbghelp.dll",
               "d3d12.dll", "wininet.dll", "winhttp.dll"]

# Instaladores y utilidades: nunca contienen el ejecutable ni DLL de upscaler.
SKIP_DIRS = {
    "_commonredist", "commonredist", "redist", "directx", "dotnet", "vcredist",
    "easyanticheat", "easyanticheat_eos", "battleye", "punkbuster",
    "soundtrack", "artbook", "support", "__installer", "dxsetup",
    "installers", "_dlss5_backup",
}

# Carpetas de contenido. Se podan por velocidad, no por relevancia: pueden
# tener cientos de miles de archivos y jamas un DLL de upscaler.
# 'Engine' NO esta aqui: Unreal guarda ahi nvngx_dlss.dll.
CONTENT_DIRS = {
    "content", "paks", "movies", "audio", "sounds", "music", "videos",
    "textures", "localization", "intermediate", "saved", "logs", "crashes",
    "shadercache", "derivedatacache", "deriveddatacache", "streamingassets",
    "media", "cinematics", "levels", "maps", "meshes", "animations",
}

# Fragmentos de nombre que delatan un lanzador o una herramienta, no el juego.
LAUNCHER_HINTS = (
    "launcher", "crashhandler", "crashreport", "crashpad", "unitycrashhandler",
    "setup", "install", "uninstall", "unins", "eosbootstrapper", "bootstrap",
    "vcredist", "dxsetup", "activation", "anticheat", "battleye", "beservice",
    "redist", "config", "touchup", "dotnet", "helper", "service", "updater",
    "cleanup", "diagnostic", "reporter", "webengine", "cefprocess",
    "vconsole", "hammer", "resourcecompiler", "workshop", "dedicated",
    "steamerrorreporter", "benchmark", "editor", "shipping_bootstrap",
)

# Se comprueban en orden: del marcador mas especifico al mas generico, porque
# '/binaries/win64/' aparece tambien en juegos que no son Unreal.
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

# Anticheats que reaccionan mal a un DLL nuevo junto al ejecutable.
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
# Lectura de PE (Portable Executable)
# --------------------------------------------------------------------------

MACHINE = {0x014C: "x86", 0x8664: "x64", 0xAA64: "arm64"}


def pe_info(path: str) -> dict:
    """Arquitectura y DLLs importadas de un .exe/.dll. Solo lee cabeceras."""
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

            f.seek(dd_off + 8)              # entrada 1 = tabla de importaciones
            imp_rva, _imp_size = struct.unpack("<II", f.read(8))

            # Tabla de secciones, para traducir RVA -> offset en disco.
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

            for i in range(1024):           # tope de cordura
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
    """Version de archivo leyendo VS_FIXEDFILEINFO directamente de los bytes.

    Busca la firma 0xFEEF04BD, que es unica y esta siempre al inicio de esa
    estructura. Mas barato que montar un parser de recursos completo.
    """
    SIG = b"\xbd\x04\xef\xfe"
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            # Los recursos suelen vivir al final; se mira ahi primero.
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
    """Busca una cadena (ASCII y UTF-16LE) dentro de un binario."""
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
    """Busca varias cadenas en un binario en una sola pasada.

    Los motores modernos cargan d3d12.dll en tiempo de ejecucion, asi que la
    tabla de importaciones miente por omision: el nombre solo aparece como
    literal dentro del .exe.
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
    """True si este DLL es en realidad OptiScaler renombrado."""
    try:
        if os.path.getsize(path) < 2 << 20:
            return False
    except OSError:
        return False
    return contains_text(path, "OptiScaler")


# --------------------------------------------------------------------------
# Sistema: GPU, driver y modelo de Neural Rendering
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
    """Nombre de GPU y version de driver. nvidia-smi si esta; si no, WMI."""
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
    """Localiza nvngx_dlssnr.dll en el sistema.

    Tambien detecta la trampa que avisa el README del fork: un nvngx_dlssd.dll
    de ~165 MB no es Ray Reconstruction, es el modelo de Neural Rendering con
    el nombre cambiado.
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
            # No bajar mas de 4 niveles por debajo de la raiz de busqueda.
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
    """Busca la copia mas nueva de cada nvngx_dlss*.dll ya instalada en el PC.

    Sirve para actualizar un juego sin descargar nada de internet: los DLL ya
    estan en el driver o en otros juegos.
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
# Bibliotecas de juegos instaladas
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
    """Carpetas de juego de Steam, Epic y GOG. Nombre + ruta, sin analizar aun."""
    found: list[dict] = []
    seen: set[str] = set()

    def add(name: str, path: str, store: str):
        key = os.path.normcase(os.path.normpath(path))
        if key in seen or not os.path.isdir(path):
            return
        seen.add(key)
        found.append({"name": name, "path": os.path.normpath(path), "store": store})

    # Steam: los .acf dan el nombre exacto y la carpeta.
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

    # Epic: un .item JSON por juego.
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

    # GOG Galaxy: una clave de registro por juego.
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
# Analisis de una carpeta de juego
# --------------------------------------------------------------------------

@dataclass
class Game:
    name: str
    root: str
    store: str = "manual"
    exe: str | None = None            # ruta completa al ejecutable elegido
    exe_dir: str | None = None        # donde van los DLL de OptiScaler
    arch: str | None = None
    engine: str | None = None
    apis: set = field(default_factory=set)         # {'dx12','dx11','vulkan'}
    upscalers: dict = field(default_factory=dict)  # familia -> etiqueta
    dll_paths: dict = field(default_factory=dict)  # nombre dll -> ruta
    dlss_version: str | None = None
    installed_proxy: str | None = None             # OptiScaler ya presente
    anticheat: set = field(default_factory=set)
    tier: str = "D"
    verdict: str = ""
    notes: list = field(default_factory=list)

    @property
    def key(self) -> str:
        return os.path.normcase(os.path.normpath(self.root))


def _walk_game(root: str, max_depth: int = 9, max_files: int = 200_000):
    """Recorrido acotado. Devuelve (exes, dlls_por_nombre, rutas_relativas).

    La profundidad tiene que llegar a 9 porque Unreal esconde el DLL en
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

        # El anticheat se anota antes de podar: sus carpetas estan en SKIP_DIRS
        # justamente porque no queremos recorrerlas, pero si saber que existen.
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
    """Analiza una carpeta de juego y decide que se le puede aplicar."""
    g = Game(name=name or os.path.basename(os.path.normpath(root)),
             root=os.path.normpath(root), store=store)

    if not os.path.isdir(root):
        g.verdict = "La carpeta no existe."
        return g

    exes, dlls, rels, anticheat = _walk_game(root)
    g.anticheat = anticheat

    # --- ejecutable principal -------------------------------------------
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

    # Las importaciones se quedan cortas: casi todos los motores cargan
    # d3d12.dll con LoadLibrary, asi que hay que mirar tambien las cadenas del
    # binario y lo que haya suelto en la carpeta.
    if "d3d12core.dll" in dlls or "d3d12.dll" in dlls:
        g.apis.add("dx12")
    scan_target = g.exe
    if "unityplayer.dll" in dlls:
        scan_target = dlls["unityplayer.dll"]     # el .exe de Unity es un cascaron
    if scan_target and "dx12" not in g.apis:
        hits = scan_strings(scan_target,
                            ["d3d12.dll", "d3d11.dll", "vulkan-1.dll"])
        for needle, api in (("d3d12.dll", "dx12"), ("d3d11.dll", "dx11"),
                            ("vulkan-1.dll", "vulkan")):
            if needle in hits:
                g.apis.add(api)

    # DX9 solo importa si es lo unico que hay; con DX11/12 delante es ruido de
    # compatibilidad que ensucia la ficha.
    if g.apis & {"dx11", "dx12"}:
        g.apis.discard("dx9")

    # --- motor ------------------------------------------------------------
    joined = "\n".join(rels)
    for label, markers in ENGINE_MARKERS:
        if any(m in joined for m in markers):
            g.engine = label
            break

    # --- upscalers presentes ---------------------------------------------
    for dll_name, (family, label) in UPSCALER_DLLS.items():
        if dll_name in dlls:
            g.upscalers[family] = label
            g.dll_paths[dll_name] = dlls[dll_name]

    if "nvngx_dlss.dll" in g.dll_paths:
        g.dlss_version = file_version(g.dll_paths["nvngx_dlss.dll"])

    # --- OptiScaler ya instalado -----------------------------------------
    for proxy in PROXY_NAMES:
        p = dlls.get(proxy)
        if p and is_optiscaler(p):
            g.installed_proxy = p
            break

    _classify(g)
    return g


def _classify(g: Game) -> None:
    """Asigna nivel y veredicto. Sin optimismo: si no se puede, se dice."""
    has_dlss = "dlss" in g.upscalers or "sl" in g.upscalers
    has_other = any(k in g.upscalers for k in ("fsr", "xess", "fsr4"))
    dx12 = "dx12" in g.apis
    dx11 = "dx11" in g.apis
    vk = "vulkan" in g.apis
    vulkan_only = vk and not (dx12 or dx11)

    if not g.exe:
        g.tier = "D"
        g.verdict = "No se encontro ningun ejecutable."
        return

    # Desde v0.2.0 el paso neuronal lee las entradas de CUALQUIER upscaler
    # temporal, no solo de DLSS, y Vulkan pasó a estar soportado de forma
    # nativa. Lo unico que sigue siendo condicion indispensable es que exista
    # un upscaler del que sacar depth y motion vectors.
    if has_dlss:
        g.tier = "A"
        g.verdict = "DLSS 5 Neural Rendering aplicable."
    elif has_other:
        g.tier = "B"
        g.verdict = "Neural Rendering aplicable sobre FSR/XeSS."
        g.notes.append("Desde v0.2.0 el paso no necesita DLSS: se engancha a "
                       "las entradas de FSR o XeSS igual de bien.")
    else:
        g.tier = "D"
        g.verdict = "Sin upscaler temporal: no hay de donde sacar los vectores."
        g.notes.append("El paso necesita depth y motion vectors, y los toma de "
                       "los que el juego ya entrega a su upscaler. Sin upscaler "
                       "no hay nada que interceptar.")
        return

    if dx11 and not dx12:
        g.notes.append("DX11: pasa por el puente D3D11-on-D3D12, que en v0.2.0 "
                       "ya admite DLSS directamente.")
    if vulkan_only:
        g.notes.append("Vulkan nativo: soportado desde v0.2.0.")
    if not g.apis:
        g.notes.append("No se pudo confirmar la API grafica, pero las tres "
                       "(DX11, DX12 y Vulkan) estan soportadas.")

    if g.anticheat:
        g.notes.append("ANTICHEAT: " + ", ".join(sorted(g.anticheat)) +
                       ". Meter un DLL junto al ejecutable puede costarte el "
                       "baneo. En multijugador competitivo, no lo hagas.")


def summary_upscalers(g: Game) -> str:
    if not g.upscalers:
        return "ninguno"
    order = ["dlss", "dlssg", "dlssd", "sl", "xess", "xefg", "fsr", "fsrfg", "fsr4"]
    short = {"dlss": "DLSS", "dlssg": "DLSS-FG", "dlssd": "DLSS-RR", "sl": "SL",
             "xess": "XeSS", "xefg": "XeFG", "fsr": "FSR", "fsrfg": "FSR-FG",
             "fsr4": "FSR4"}
    return " ".join(short[k] for k in order if k in g.upscalers)
