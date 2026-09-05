# DLSS 5 One-Click

Detecta qué juegos de tu PC admiten **DLSS 5 Neural Rendering**, lo instala en
un clic y sabe deshacerlo entero, byte a byte.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Sin dependencias](https://img.shields.io/badge/dependencias-ninguna-76b900)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?logo=windows&logoColor=white)
![Licencia](https://img.shields.io/badge/licencia-MIT-blue)

```
DLSS5.bat          (o:  python dlss5.py)
```

Solo necesita **Python 3.10+**. No usa `pip`, no instala nada, y no descarga
nada hasta que pulsas Aplicar.

> [!WARNING]
> Esto mete un DLL junto al ejecutable de tus juegos. Es exactamente lo que
> buscan los anticheat. **No lo uses en multijugador competitivo**: el programa
> detecta EAC, BattlEye, Vanguard y Denuvo AC y te pide confirmación, pero la
> decisión y el riesgo de baneo son tuyos.

---

## Qué es DLSS 5 y qué no es

DLSS 5 salió el **3 de septiembre de 2026** y no es un upscaler. Es
*3D-Guided Neural Rendering*: un modelo de difusión que reescribe la iluminación
y los materiales del fotograma ya renderizado. DLSS 4.5 sigue encargándose de
Super Resolution, Ray Reconstruction y Multi Frame Generation; DLSS 5 es una
capa aparte que se suma.

**No se puede aplicar a cualquier juego, y conviene saber por qué.** El modelo
necesita saber dónde está cada cosa en la escena. En la integración oficial de
NVIDIA eso llega por Streamline: color, motion vectors, albedo, normales y los
buffers de iluminación. Un juego que no entrega esos datos no tiene nada que
darle al modelo.

El atajo que usa esta herramienta —el fork de OptiScaler— no busca esos buffers
en el motor: **intercepta los que el juego ya le pasa a su upscaler cada
fotograma** (depth y motion vectors). Por eso funciona en cualquier título con
upscaler sin trabajo por juego, y por eso no hace absolutamente nada en un juego
que no tenga ninguno. Con menos guías que la integración oficial, el resultado
tampoco es idéntico al de un juego con DLSS 5 nativo.

Desde **v0.2.0** del fork (3 sept 2026) el paso ya no exige DLSS: se engancha
igual a FSR y a XeSS, y Vulkan pasó a estar soportado de forma nativa.

## Requisitos

| | |
|---|---|
| **GPU** | RTX 50 (Blackwell). En RTX 20/30/40 hace falta un DLL modificado que este programa no proporciona |
| **Driver** | 616.56 o superior |
| **Modelo** | `nvngx_dlssnr.dll` (~158 MB) — ver abajo, es la parte que atasca |
| **Juego** | Con cualquier upscaler temporal (DLSS, FSR o XeSS), en DX11, DX12 o Vulkan |

El programa comprueba las cuatro cosas al arrancar y te dice cuál falta.

## El modelo no está en el driver

Puedes tener el driver correcto instalado y no encontrar `nvngx_dlssnr.dll` por
ningún lado. **No viene ahí.**

Verificado el 5/9/2026 descargando el instalador oficial 616.64 (938 MB desde
`us.download.nvidia.com`) y abriéndolo: sus únicos `nvngx_*` son `nvngx.dll`,
`nvngx_dlssg.dll`, `nvngx_dlisr.dll` y `nvngx_update.exe`. Ni rastro de
`dlssnr`. Tampoco hay interruptor en la NVIDIA App — NVIDIA confirmó que no
habría override por juego.

**El modelo lo distribuye cada juego que implementa DLSS 5.** Se descubrió
dentro de NBA 2K27, en `data\streamline\nvngx_dlssnr.dll` (158 MB, se identifica
como "NVIDIA DLSSNR"), y a día de hoy ese es el único que lo trae.

> [!NOTE]
> Ojo con el anuncio de NVIDIA, que agrupa cosas distintas: **Onimusha: Way of
> the Sword**, **The Blood of Dawnwalker** y **STAR WARS Zero Company** salen en
> el mismo artículo pero solo reciben DLSS 4.5. **No llevan el modelo**, y la
> demo gratuita de Onimusha tampoco. Instalarlos para esto es tirar 100 GB.

El botón **Buscar modelo** mira, por este orden: la caché, tus juegos
instalados, y por último cualquier instalador de driver que tengas suelto. Basta
con tener el juego instalado — no hay que jugarlo. El DLL se copia a
`%LOCALAPPDATA%\DLSS5\modelo` y de ahí a todos los demás juegos, así que puedes
desinstalar el juego origen después.

**El programa nunca descarga el modelo de terceros.** Es de NVIDIA, y los sitios
que lo reempaquetan son justo los que conviene evitar.

### No hace falta esperar al modelo para instalar

El paso neuronal es **opcional dentro de OptiScaler**, no un requisito de
arranque. Sin el DLL se instala igual y funciona lo demás: cambiar el upscaler,
frame generation, RCAS, overrides de DLSS. Solo el paso de Neural Rendering
queda apagado, y el overlay dice exactamente por qué
(`"nvngx_dlssnr.dll was not found"`) en vez de fallar en silencio. Cuando
consigas el DLL, vuelves a darle a Aplicar y se copia.

## Uso

1. **Buscar juegos instalados** — recorre Steam, Epic y GOG. Unos 6 segundos
   para 40 juegos.
2. Selecciona uno y elige un ajuste.
3. **Aplicar DLSS 5**.
4. Dentro del juego, **Insert** abre el overlay; **F10** enciende y apaga el
   paso.

### Los niveles

- **Sí (DLSS)** — tiene DLSS. El caso ideal.
- **Sí (FSR/XeSS)** — sin DLSS, pero desde v0.2.0 el paso se engancha igual de
  bien a las entradas de FSR o XeSS.
- **No** — sin upscaler temporal. No hay depth ni motion vectors que
  interceptar. No hay truco que valga.

### Qué hace al aplicar

1. Descarga el release oficial del fork y lo cachea en `%LOCALAPPDATA%\DLSS5`.
2. Copia los archivos junto al ejecutable **real** del juego — que no siempre
   está en la raíz: Cyberpunk lo tiene en `bin\x64` y los Unreal en
   `<Juego>\Binaries\Win64`.
3. Renombra `OptiScaler.dll` a un nombre libre que el juego cargue solo
   (`dxgi.dll`, o el siguiente que quede libre si está ocupado).
4. Escribe `[DlssNr]` con el ajuste elegido, respetando los comentarios.
5. Copia el modelo desde la caché (hace falta una copia por juego: no existe
   ubicación compartida).
6. Actualiza los `nvngx_dlss*.dll` del juego si tienes una versión más nueva en
   otro sitio del PC. No baja DLL de NVIDIA de ningún sitio: usa los que tienes.

Todo lo que sobrescribe va antes a `_DLSS5_backup\` con un manifiesto.
**Revertir** deja la carpeta byte a byte como estaba.

## Ajustes

| Preset | Para qué |
|---|---|
| **Suave** | Respeta el arte original. Solo la luz lleva la opinión del modelo |
| **Equilibrado** | El recomendado |
| **Máximo detalle** | Empuja más allá de lo que el modelo pide. Se nota |
| **Supersampling** | El modelo corre por encima de nativo y se promedia de vuelta con Lanczos3: menos ruido. Caro |
| **Rendimiento** | El modelo trabaja a media resolución. El coste cae al cuadrado |

### Editor por juego

El botón **Ajustes...** abre un editor sobre el `OptiScaler.ini` del juego: 33
opciones en cinco grupos plegables — Neural Rendering, Upscaler, Calidad y
nitidez, Frame Generation y Sistema. Cada control lleva debajo lo que hace, con
los rangos reales que documenta el propio archivo.

Guarda **solo lo que cambies**; el resto queda intacto, comentarios incluidos.
Un valor en `auto` sigue en `auto` — un clic en la cifra de un deslizador lo
devuelve a `auto`. Los cambios entran al arrancar el juego.

### Lo que solo se toca dentro del juego

La mejora grande de v0.2.0 es el **proxy reversible**, y su modo recomendado es
*Hybrid proxy + composed*: mantiene los medios tonos y recupera el detalle que
la curva antigua aplastaba en las luces. **No existe como clave del INI**, así
que ninguna ventana externa puede preconfigurarlo. Se cambia con Insert →
Colour. Lo mismo vale para el anclaje multipunto del punto de blanco y el
"Hold frame".

### Cómo saber si de verdad hace algo

A ojo y en movimiento uno se autoengaña con facilidad. Dos formas honestas:

- **F10** apaga y enciende el paso sin abrir el menú. Quédate quieto en una
  escena con luz interesante y alterna.
- **DebugView → "Diferencia x20"** pinta lo que el modelo ha cambiado,
  amplificado. Un **gris plano** significa que no está tocando nada.

## Anticheat

Si detecta EAC, BattlEye, Vanguard, mhyprot o Denuvo AC, lo marca en la lista y
pide confirmación explícita antes de instalar. Meter un DLL junto al ejecutable
es justo lo que esos sistemas buscan.

## Aviso sobre repositorios falsos

Circulan repos que prometen "DLSS 5 en cualquier juego, incluido D3D9". Es
imposible: un juego de D3D9 no tiene motion vectors que dar. Uno de los que
circulaba al escribir esto tenía dos días de vida, 677 MB de binarios opacos, y
falsificaba los buffers con shaders de ReShade.

El equipo de OptiScaler avisa además de webs y "manager apps" falsas: sus únicos
sitios legítimos son su GitHub, su Discord y la página de Nitec en NexusMods.

Esta herramienta solo descarga de los repos oficiales listados en `SOURCES`
(`dlss5_apply.py`) y guarda el SHA-256 de todo lo que baja.

## Estructura

| Archivo | |
|---|---|
| `dlss5.py` | Interfaz principal |
| `dlss5_scan.py` | Detección: PE, motor, API, upscalers, GPU, anticheat |
| `dlss5_apply.py` | Descarga, instalación, INI y marcha atrás |
| `dlss5_model.py` | Conseguir `nvngx_dlssnr.dll` de los juegos que lo traen |
| `dlss5_opts.py` | Catálogo de ajustes, con tipos y rangos reales |
| `dlss5_editor.py` | Editor visual por juego |
| `pruebas.py` | 46 comprobaciones |

### Pruebas

```
python pruebas.py
```

Monta un juego falso, instala encima, comprueba el resultado y revierte,
comparando SHA-256 de todo el árbol. Si un solo byte cambia, falla. También
valida que **cada clave del catálogo existe de verdad** en el INI — una clave
inventada se escribe sin error y no hace nada, que es justo el fallo que tuvo
`Log.LoggingEnabled`.

## Créditos

El trabajo duro no es mío:

- **[OptiScaler](https://github.com/optiscaler/OptiScaler)** (cdozdil / Nitec),
  GPL-3.0 — el hook de DirectX y todo el puente entre upscalers.
- **[OptiScaler_DLSSNR](https://github.com/Dagherbou/OptiScaler_DLSSNR)** (dag),
  GPL-3.0 — el paso de Neural Rendering.
- **[RenoDX](https://github.com/clshortfuse/renodx)** (clshortfuse), MIT — la
  composición de color que hace que el resultado no se rompa.

Esta herramienta es un frontend: detecta, decide, configura y sabe deshacerlo.
No incluye ni redistribuye ninguno de los anteriores; los descarga de sus
propios releases cuando pulsas Aplicar.

## Licencia

MIT — ver [LICENSE](LICENSE). Cubre solo el código de este repositorio; el
software que descarga en tiempo de ejecución conserva su propia licencia.

No está afiliado a NVIDIA ni al equipo de OptiScaler.
