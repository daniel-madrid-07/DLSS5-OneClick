"""
Catalogo de ajustes editables, con sus tipos y rangos reales.

Todo lo de aqui esta sacado leyendo OptiScaler.ini de v0.2.0 clave por clave.
Los rangos son los que documenta el propio archivo, no estimaciones.

Lo que NO esta aqui, porque no existe como clave del INI y solo vive en el
overlay del juego (Insert):
  - El proxy reversible (Off / Neutwo / Hybrid, composed o replace)
  - El anclaje multipunto del punto de blanco
  - Hold frame para comparar ajustes
Se avisa de ello en la interfaz en vez de fingir que se pueden tocar.
"""

from __future__ import annotations

# Tipos de control:
#   bool   -> interruptor
#   float  -> deslizador (min, max, paso)
#   int    -> deslizador entero
#   choice -> desplegable [(valor_ini, etiqueta), ...]

DOWNSCALERS = [("0", "FSR1"), ("1", "Bicubic"), ("2", "Catmull-Rom"),
               ("3", "Lanczos2"), ("4", "Lanczos3"), ("5", "Kaiser2"),
               ("6", "Kaiser3"), ("7", "MAGIC")]

DLSS_PRESETS = [("0", "Por defecto"), ("11", "K  (transformer)"),
                ("12", "L"), ("13", "M"), ("14", "N"), ("15", "O"),
                ("3", "C"), ("5", "E"), ("6", "F"), ("7", "G")]

# Cada grupo: (id, titulo, subtitulo, [ajustes])
# Cada ajuste: (seccion_ini, clave, etiqueta, tipo, extra, ayuda)

GROUPS = [
    ("nr", "Neural Rendering", "El paso de DLSS 5. Necesita nvngx_dlssnr.dll.", [
        ("DlssNr", "Enabled", "Activado", "bool", None,
         "Enciende el paso neuronal. Sin el modelo no arranca aunque este en true."),
        ("DlssNr", "TransferStrength", "Fuerza del detalle", "float", (0.0, 2.0, 0.05),
         "Cuanto se mueve el fotograma hacia la imagen del modelo. 0 devuelve "
         "exactamente lo que produjo el upscaler; 1 es la imagen del modelo; por "
         "encima sigue mas alla de lo que el modelo pidio."),
        ("DlssNr", "ColourStrength", "Fuerza del color", "float", (0.0, 4.0, 0.05),
         "Si llega tambien el color del modelo o solo su luz. 0 mantiene el tono "
         "exacto del juego. Valores muy altos pueden parpadear."),
        ("DlssNr", "MaxRatio", "Tope de brillo", "float", (1.0, 4.0, 0.1),
         "Lo maximo que el paso puede aclarar un pixel. Evita que una luz se "
         "convierta en celdas de colores. Oscurecer no tiene tope."),
        ("DlssNr", "WorkingScale", "Resolucion del modelo", "float", (0.25, 2.0, 0.05),
         "Fraccion del fotograma a la que trabaja el modelo. El coste cae con el "
         "cuadrado. Por encima de 1.0 hace supersampling: mas limpio, mas caro."),
        ("DlssNr", "ScalingDownscaler", "Filtro de reduccion", "choice", DOWNSCALERS,
         "Solo se usa cuando la resolucion del modelo pasa de 1.0. Lanczos3 es "
         "el valor por defecto y el recomendado."),
        ("DlssNr", "WhitePointScale", "Punto de blanco", "float", (0.1, 4.0, 0.05),
         "Multiplica el blanco antes de que el modelo vea el fotograma. Es el "
         "control de paper white."),
        ("DlssNr", "Intensity", "Intensidad", "float", (0.0, 2.0, 0.05),
         "Parametro propio de NVIDIA, sin documentar."),
        ("DlssNr", "AutoMask", "Mascara automatica", "bool", None,
         "Deja que el modelo reconozca objetos y se aplique de forma selectiva."),
        ("DlssNr", "DebugView", "Vista de depuracion", "choice",
         [("0", "Apagada"), ("1", "Lo que ve el modelo"),
          ("2", "Su respuesta cruda"), ("3", "Diferencia x20")],
         "La opcion 3 es la util: muestra lo que ha cambiado amplificado. "
         "Un gris plano significa que no esta tocando nada."),
    ]),

    ("upscaler", "Upscaler", "Que tecnica de escalado usa el juego.", [
        ("Upscalers", "Dx12Upscaler", "DirectX 12", "choice",
         [("auto", "Automatico"), ("dlss", "DLSS"), ("xess", "XeSS"),
          ("ffx", "FSR 3.1 / 4.x"), ("fsr22", "FSR 2.2"), ("fsr21", "FSR 2.1")],
         "Automatico elige DLSS en tarjetas NVIDIA."),
        ("Upscalers", "Dx11Upscaler", "DirectX 11", "choice",
         [("auto", "Automatico"), ("dlss", "DLSS"), ("xess", "XeSS"),
          ("fsr22", "FSR 2.2 nativo"), ("fsr31", "FSR 3.1 nativo")], ""),
        ("Upscalers", "VulkanUpscaler", "Vulkan", "choice",
         [("auto", "Automatico"), ("dlss", "DLSS"), ("xess", "XeSS nativo"),
          ("ffx", "FSR 2.3 / 3.1 nativo"), ("fsr21", "FSR 2.1 nativo")], ""),
        ("DLSS", "RenderPresetOverride", "Forzar preset de DLSS", "bool", None,
         "Permite imponer un preset concreto en lugar del que elija el juego."),
        ("DLSS", "RenderPresetForAll", "Preset para todos los modos", "choice",
         DLSS_PRESETS,
         "K es el modelo transformer actual. Solo tiene efecto con la opcion "
         "de arriba activada."),
    ]),

    ("quality", "Calidad y nitidez", "Escalado de salida y afilado.", [
        ("OutputScaling", "Enabled", "Escalado de salida", "bool", None,
         "Renderiza por encima de la resolucion de pantalla y reduce despues. "
         "Solo DX12 y DX11-sobre-DX12."),
        ("OutputScaling", "Multiplier", "Multiplicador", "float", (0.5, 3.0, 0.1),
         "Cuanto se renderiza por encima. 1.5 es el valor por defecto."),
        ("OutputScaling", "Downscaler", "Filtro de reduccion", "choice", DOWNSCALERS, ""),
        ("CAS", "Enabled", "Afilado RCAS", "bool", None,
         "Afilado por contraste adaptativo."),
        ("Sharpness", "OverrideSharpness", "Forzar nitidez", "bool", None,
         "Ignora el valor de nitidez que pida el juego."),
        ("Sharpness", "Sharpness", "Nitidez", "float", (0.0, 1.0, 0.05),
         "0.3 por defecto. Con RCAS el limite util llega a 1.3."),
        ("CAS", "MotionSharpnessEnabled", "Nitidez en movimiento", "bool", None,
         "Anade o quita afilado segun cuanto se mueva cada pixel."),
        ("CAS", "MotionSharpness", "Cantidad en movimiento", "float", (-1.3, 1.3, 0.05),
         "Negativo quita afilado al moverse; positivo lo anade."),
    ]),

    ("fg", "Frame Generation", "Fotogramas intercalados. Ojo con la latencia.", [
        ("FrameGen", "Enabled", "Activado", "bool", None,
         "Enciende la generacion de fotogramas."),
        ("FrameGen", "FGOutput", "Metodo", "choice",
         [("auto", "Automatico"), ("dlssg", "DLSS-G (NVIDIA)"),
          ("fsrfg", "FSR-FG"), ("xefg", "XeSS-FG"), ("optifg", "OptiFG")],
         "DLSS-G necesita que el juego ya lo soporte."),
        ("FrameGen", "AllowedFrameAhead", "Fotogramas de adelanto", "int", (1, 3, 1),
         "Cuantos fotogramas puede adelantarse. Menos adelanto, menos latencia."),
        ("Framerate", "FramerateLimit", "Limite de FPS", "float", (0.0, 360.0, 5.0),
         "0 lo desactiva. Usa Reflex cuando esta disponible, asi que baja la "
         "latencia mejor que un limitador externo."),
        ("FrameGen", "DebugView", "Vista de depuracion", "bool", None,
         "Marca visualmente los fotogramas generados."),
    ]),

    ("system", "Sistema", "Pantalla y diagnostico.", [
        ("HDR", "ForceHDR", "Forzar HDR", "bool", None,
         "Fuerza el espacio de color HDR. Solo si tu pantalla lo admite."),
        ("HDR", "UseHDR10", "Usar HDR10", "bool", None,
         "R10G10B10A2 en lugar de R16G16B16A16 en coma flotante."),
        ("V-Sync", "OverrideVsync", "Controlar V-Sync", "bool", None,
         "Permite que OptiScaler gestione la sincronia vertical."),
        ("Menu", "OverlayMenu", "Overlay con Insert", "bool", None,
         "El menu dentro del juego. Sin esto pierdes el proxy reversible."),
        ("Log", "LogToFile", "Registro a archivo", "bool", None,
         "Escribe OptiScaler.log junto al juego. Hace falta activarlo antes "
         "de reportar cualquier problema. Cuesta algo de rendimiento."),
    ]),
]


def all_settings():
    """Aplana el catalogo: [(grupo_id, seccion, clave, etiqueta, tipo, extra, ayuda)]"""
    out = []
    for gid, _t, _s, items in GROUPS:
        for sect, key, label, kind, extra, help_ in items:
            out.append((gid, sect, key, label, kind, extra, help_))
    return out


def group_of(section: str, key: str) -> str | None:
    for gid, _t, _s, items in GROUPS:
        for sect, k, *_ in items:
            if sect == section and k == key:
                return gid
    return None


# Ajustes que solo existen dentro del overlay del juego. Se muestran para que
# nadie los busque aqui sin encontrarlos.
OVERLAY_ONLY = [
    ("Proxy reversible",
     "Colour -> Off / Neutwo / Hybrid, en variante composed o replace. "
     "\"Hybrid proxy + composed\" es el recomendado de v0.2.0: mantiene los "
     "medios tonos y recupera el detalle de las luces."),
    ("Anclaje del punto de blanco",
     "Varios puntos de calibracion para que el blanco aguante cuando cambia "
     "mucho la luz de la escena."),
    ("Hold frame",
     "Congela el fotograma sobre el que trabaja el modelo para comparar dos "
     "ajustes sobre la misma imagen."),
    ("Apply the model",
     "Con el fotograma congelado, apaga el efecto sin parar el modelo: la "
     "misma imagen con y sin Neural Rendering."),
]
