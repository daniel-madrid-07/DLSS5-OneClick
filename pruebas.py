"""
Pruebas de la parte peligrosa: que instalar y revertir deje la carpeta igual.

Monta un juego falso con un archivo que va a ser sobrescrito, instala encima,
comprueba el resultado y revierte. Si un solo byte cambia, falla.

    python pruebas.py
"""

import os
import sys
import shutil
import hashlib
import tempfile

import dlss5_scan as scan
import dlss5_apply as apply_mod
import dlss5_model as model_mod
import dlss5_opts as opts

OK, FAIL = [], []


def check(name: str, cond: bool, detail: str = ""):
    (OK if cond else FAIL).append(name)
    mark = "  ok  " if cond else " FALLO"
    print(f"[{mark}] {name}" + (f"   -> {detail}" if detail and not cond else ""))


def hash_tree(root: str) -> dict:
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            h = hashlib.sha256()
            with open(full, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            out[rel] = h.hexdigest()
    return out


def build_fake_game(base: str) -> str:
    """Un juego plausible: ejecutable real, DLSS presente, y un OptiScaler.ini
    previo que la instalacion debera respaldar y la marcha atras restaurar."""
    root = os.path.join(base, "JuegoFalso")
    os.makedirs(root, exist_ok=True)

    shutil.copy2(r"C:\Windows\System32\notepad.exe",
                 os.path.join(root, "JuegoFalso.exe"))
    # Un nvngx_dlss.dll cualquiera basta: solo se comprueba el nombre.
    shutil.copy2(r"C:\Windows\System32\d3d12.dll",
                 os.path.join(root, "nvngx_dlss.dll"))
    # dxgi.dll ocupado -> el proxy debe elegir otro nombre.
    shutil.copy2(r"C:\Windows\System32\version.dll",
                 os.path.join(root, "dxgi.dll"))
    with open(os.path.join(root, "OptiScaler.ini"), "w", encoding="utf-8") as f:
        f.write("; ini previo del usuario, no debe perderse\n[Menu]\nScale=1.5\n")
    return root


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="dlss5_test_")
    print(f"Carpeta de pruebas: {tmp}\n")
    try:
        root = build_fake_game(tmp)
        before = hash_tree(root)
        print(f"Juego falso con {len(before)} archivos.\n")

        # --- deteccion ---------------------------------------------------
        g = scan.analyze(root, "Juego Falso")
        check("detecta el ejecutable", os.path.basename(g.exe or "") == "JuegoFalso.exe",
              str(g.exe))
        check("detecta DLSS", "dlss" in g.upscalers, str(g.upscalers))
        check("nivel A", g.tier == "A", f"{g.tier}: {g.verdict}")

        # --- eleccion de proxy -------------------------------------------
        proxy = apply_mod.pick_proxy(g.exe_dir)
        check("evita el dxgi.dll ocupado", proxy != "dxgi.dll", proxy)

        # --- instalacion --------------------------------------------------
        print("\nInstalando (usa la cache si el paquete ya esta bajado)...")
        manifest = apply_mod.install(g, preset="equilibrado", kind="dlssnr",
                                     neural=True, copy_model=True,
                                     log=lambda m: print("   " + str(m)))

        after_install = hash_tree(root)
        check("OptiScaler colocado como proxy",
              os.path.isfile(os.path.join(root, manifest["proxy"])), manifest["proxy"])
        check("nvngx.dll_dlssnr.dll copiado",
              os.path.isfile(os.path.join(root, "nvngx.dll_dlssnr.dll")))
        check("binarios en la subcarpeta OptiScaler",
              os.path.isdir(os.path.join(root, "OptiScaler")))
        check("manifiesto escrito", apply_mod.read_manifest(root) is not None)
        check("el ini previo quedo respaldado",
              "OptiScaler.ini" in manifest["respaldados"],
              str(list(manifest["respaldados"])))

        # --- contenido del ini -------------------------------------------
        ini = os.path.join(root, "OptiScaler.ini")
        with open(ini, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        sec = text.split("[DlssNr]", 1)[-1]
        check("[DlssNr] Enabled=true", "\nEnabled=true" in sec)
        check("[DlssNr] TransferStrength=1.0", "\nTransferStrength=1.0" in sec)
        check("[DlssNr] WorkingScale=1.0", "\nWorkingScale=1.0" in sec)
        check("no quedan claves duplicadas",
              sec.count("\nEnabled=") == 1, str(sec.count("\nEnabled=")))
        check("los comentarios del ini sobreviven",
              "; DLSS 5 Neural Rendering" in text)

        check("[DlssNr] ToggleKey escrito (F10)", "\nToggleKey=0x79" in sec)

        # --- reanalisis ---------------------------------------------------
        g2 = scan.analyze(root, "Juego Falso")
        check("reconoce su propia instalacion", g2.installed_proxy is not None,
              str(g2.installed_proxy))

        # --- clasificacion v0.2.0 -----------------------------------------
        # NR ya no exige DLSS ni DirectX. Un juego solo-Vulkan con FSR debe
        # quedar como aplicable, no descartado.
        vk = scan.Game(name="vk", root=root, exe="x", exe_dir=root,
                       apis={"vulkan"}, upscalers={"fsr": "FSR"})
        scan._classify(vk)
        check("Vulkan + FSR es aplicable (v0.2.0)", vk.tier == "B",
              f"{vk.tier}: {vk.verdict}")

        xess = scan.Game(name="xe", root=root, exe="x", exe_dir=root,
                         apis={"dx12"}, upscalers={"xess": "XeSS"})
        scan._classify(xess)
        check("XeSS sin DLSS es aplicable", xess.tier == "B",
              f"{xess.tier}: {xess.verdict}")

        nada = scan.Game(name="n", root=root, exe="x", exe_dir=root,
                         apis={"dx12"}, upscalers={})
        scan._classify(nada)
        check("sin upscaler sigue siendo no", nada.tier == "D", nada.tier)

        # ya no se fuerza el upscaler de salida en juegos FSR/XeSS
        cfg = apply_mod.build_config(xess, "equilibrado", neural=True)
        check("no se fuerza Dx12Upscaler", "Upscalers" not in cfg,
              str(cfg.get("Upscalers")))

        # --- modelo --------------------------------------------------------
        check("preset de supersampling existe",
              "supersampling" in apply_mod.PRESETS)
        ss = apply_mod.PRESETS["supersampling"]["DlssNr"]
        check("supersampling pide WorkingScale > 1",
              float(ss["WorkingScale"]) > 1.0, ss["WorkingScale"])
        check("supersampling fija el downscaler",
              ss.get("ScalingDownscaler") == "4", str(ss.get("ScalingDownscaler")))
        check("busca el modelo en los juegos, no solo en el driver",
              callable(getattr(model_mod, "find_in_games", None)))

        # El flujo del usuario nuevo: deja el DLL junto al programa y ya.
        # app_dir() tiene que ser la carpeta del .exe, no la del descomprimido
        # temporal de PyInstaller.
        check("app_dir apunta a una carpeta real",
              os.path.isdir(model_mod.app_dir()), model_mod.app_dir())
        # Se comprueba de verdad: un archivo del tamano del modelo colocado en
        # una carpeta pasada como raiz extra tiene que encontrarse.
        # Archivo disperso: ocupa el tamano declarado sin escribir 100 MB.
        # Se hace deliberadamente MAS GRANDE que cualquier copia real que pueda
        # haber en esta maquina, porque find_existing se queda con la mayor.
        falso = os.path.join(root, "nvngx_dlssnr.dll")
        grande = 400 << 20
        with open(falso, "wb") as f:
            f.seek(grande - 1)
            f.write(b"\0")
        hallado = model_mod.find_existing(extra_roots=[root])
        check("encuentra un modelo dejado en una carpeta",
              hallado["path"] and os.path.normcase(hallado["path"])
              == os.path.normcase(falso), str(hallado["path"]))
        os.remove(falso)

        # Y uno por debajo del minimo no debe colarse como modelo.
        pequeno = os.path.join(root, "nvngx_dlssnr.dll")
        with open(pequeno, "wb") as f:
            f.write(b"\0" * 1024)
        tras = model_mod.find_existing(extra_roots=[root])
        check("descarta archivos demasiado pequenos para ser el modelo",
              os.path.normcase(str(tras["path"])) != os.path.normcase(pequeno),
              str(tras["path"]))
        os.remove(pequeno)
        check("la ayuda dice que basta con dejarlo al lado",
              "junto al programa" in model_mod.help_text("616.64"))
        check("la ayuda no manda a por el driver",
              "NO viene en el driver" in model_mod.help_text("616.64"))
        check("la ayuda nombra los juegos que si lo traen",
              "NBA 2K27" in model_mod.help_text("616.64"))
        # Onimusha y Dawnwalker salen en el anuncio de NVIDIA pero solo llevan
        # DLSS 4.5. Mandar a instalarlos seria hacer perder 100 GB a alguien.
        check("Onimusha NO figura como fuente del modelo",
              not any("onimusha" in g.lower() for g in model_mod.SHIPPING_GAMES),
              str(model_mod.SHIPPING_GAMES))
        check("Onimusha aparece avisado como que no sirve",
              any("Onimusha" in k for k in model_mod.NOT_SHIPPING))
        check("la ayuda dice que se puede instalar sin el modelo",
              "sin el modelo" in model_mod.help_text("616.64"))
        check("driver 616.64 se acepta", model_mod.driver_ok("616.64") is True)
        check("driver 580.00 se rechaza", model_mod.driver_ok("580.00") is False)
        check("driver desconocido no miente", model_mod.driver_ok(None) is None)
        check("find_existing ignora DLL pequenos",
              model_mod.find_existing()["path"] is None
              or os.path.getsize(model_mod.find_existing()["path"])
              >= model_mod.MIN_MODEL_MB << 20)

        # --- editor de ajustes ---------------------------------------------
        # Cada clave del catalogo tiene que existir de verdad en el INI. Una
        # clave inventada se escribe sin error y no hace nada: justo el fallo
        # que tenia Log.LoggingEnabled.
        ini_data = apply_mod.read_ini(ini)
        inventadas = [f"{s}.{k}" for _g, s, k, _l, _t, _e, _h
                      in opts.all_settings()
                      if k not in ini_data.get(s, {})]
        check("ningun ajuste del catalogo es inventado", not inventadas,
              str(inventadas))

        check("read_ini lee todas las secciones", len(ini_data) >= 38,
              str(len(ini_data)))

        # Escribir desde el editor no debe crecer ni duplicar el archivo.
        antes = open(ini, encoding="utf-8", errors="replace").read()
        apply_mod.set_ini(ini, {"DlssNr": {"ColourStrength": "0.80"},
                                "CAS": {"Enabled": "true"}})
        despues = open(ini, encoding="utf-8", errors="replace").read()
        check("editar no cambia el numero de lineas",
              antes.count("\n") == despues.count("\n"),
              f"{antes.count(chr(10))} -> {despues.count(chr(10))}")
        vuelto = apply_mod.read_ini(ini)
        check("el valor editado se relee igual",
              vuelto["DlssNr"]["ColourStrength"] == "0.80",
              vuelto["DlssNr"].get("ColourStrength"))
        check("editar una seccion no toca otra",
              vuelto["CAS"]["Enabled"] == "true")
        check("no se duplican claves al editar",
              despues.count("\nColourStrength=") == 1,
              str(despues.count("\nColourStrength=")))

        # El editor no debe inventarse cambios por el mero hecho de dibujarse:
        # ttk.Scale.set() dispara su callback al construir, y sin guarda eso
        # convertiria cada 'auto' en el minimo del deslizador al guardar.
        try:
            import tkinter as tk
            import dlss5_editor as editor_mod

            r = tk.Tk()
            r.withdraw()
            ed = editor_mod.Editor(r, g)
            ed.open_groups = {gid for gid, _t, _s, _i in opts.GROUPS}
            ed._render()
            ed.update()
            ed.update_idletasks()

            check("abrir el editor no marca cambios falsos",
                  not ed._collect(), str(ed._collect())[:120])

            ed.vars[("DlssNr", "ColourStrength")].set("0.75")
            solo = ed._collect()
            check("un cambio se cuenta como uno",
                  sum(len(v) for v in solo.values()) == 1, str(solo))
            check("el editor expone los 33 ajustes",
                  len(ed.vars) == len(opts.all_settings()),
                  f"{len(ed.vars)} vs {len(opts.all_settings())}")
            ed.destroy()
            r.destroy()
        except tk.TclError as e:                     # sin escritorio disponible
            print(f"[ aviso ] editor no probado: {e}")

        # --- marcha atras --------------------------------------------------
        print("\nRevirtiendo...")
        apply_mod.revert(root, log=lambda m: print("   " + str(m)))
        after_revert = hash_tree(root)

        missing = sorted(set(before) - set(after_revert))
        extra = sorted(set(after_revert) - set(before))
        changed = sorted(k for k in before
                         if k in after_revert and before[k] != after_revert[k])

        check("no falta ningun archivo original", not missing, str(missing[:5]))
        check("no queda ningun archivo de sobra", not extra, str(extra[:5]))
        check("ningun archivo original quedo alterado", not changed, str(changed[:5]))
        check("la carpeta vuelve a su estado exacto",
              before == after_revert,
              f"{len(missing)} faltan, {len(extra)} sobran, {len(changed)} cambiados")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{len(OK)} correctas, {len(FAIL)} fallidas")
    if FAIL:
        print("Fallos: " + ", ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
