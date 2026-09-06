# Third-party notices

The [MIT licence](LICENSE) of this repository covers **only the code kept
here**.

It does not cover the software the tool downloads at run time. That software
keeps its own licence and is **never redistributed in this repository**: it is
fetched from its own official releases when you press Apply.

| Component | Licence | How it is used |
|---|---|---|
| [OptiScaler](https://github.com/optiscaler/OptiScaler) (cdozdil / Nitec) | GPL-3.0 | Its release is downloaded. This project includes none of its source and links against none of its binaries: it copies the published files and writes its `.ini` |
| [OptiScaler_DLSSNR](https://github.com/Dagherbou/OptiScaler_DLSSNR) (dag) | GPL-3.0 | Same as above. It is the fork that adds the Neural Rendering pass |
| [RenoDX](https://github.com/clshortfuse/renodx) (clshortfuse) | MIT | Its colour composition is used internally by the fork, not by this code |
| `nvngx_dlssnr.dll` and the other NGX libraries | Proprietary — NVIDIA | **Never downloaded, never redistributed.** The tool only copies files already present on your machine, put there by a game that installed them or by your driver |

## About NVIDIA's model

`nvngx_dlssnr.dll` is NVIDIA's property. This project:

- does **not** include it in the repository,
- does **not** download it from the internet,
- does **not** obtain it from third-party repositories that repackage it,
- only **copies** it from a location on your own disk into the game folder that
  needs it.

If you have no legitimate copy on your machine, the tool says so and does
nothing further.

## No affiliation

This project is not affiliated with, sponsored by, or endorsed by NVIDIA
Corporation, the OptiScaler team, or any of the authors credited above. All
trademarks belong to their respective owners.
