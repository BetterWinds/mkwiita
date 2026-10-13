# Building Mario Kart Wii for PS Vita

The build makes two things:
- **`build/vita/mkw.vpk`:** the program.
- **`build/vita/data/mkw/`:** the game files, converted from your own disc.

## 1. Install the tools (once)

| Tool | Notes |
|---|---|
| [VitaSDK](https://vitasdk.org) | Set the `VITASDK` environment variable to its folder, e.g. `C:\vitasdk`. On Windows, extract the `vitasdk-x86_64-w64-mingw32` snapshot from [vitasdk/autobuilds](https://github.com/vitasdk/autobuilds/releases) to `C:\vitasdk`, then run `vdpm refresh nightly` once. |
| [Python 3.11+](https://www.python.org/downloads/) | Tick "Add python.exe to PATH" |
| [Node.js LTS](https://nodejs.org) | Used by the model exporters |
| [Git](https://git-scm.com) | |

The build fetches the rest itself:
- vitaGL and its dependencies, through VitaSDK's `vdpm`
- CMake and Ninja, through pip
- `tex3ds`, devkitPro's texture converter, into `.toolchain/`
- the pinned sources (Kinoko, citro3d, libctru, noclip, gclib) into `vendor/`

## 2. Build

**Windows:** double-click `Build MKW Vita.bat`, drag in your Mario Kart Wii
(USA) `.iso` or `.wbfs`, and press Enter. Output is also saved to
`build-vita-log.txt`.

**Any OS, from a terminal:**

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt    # .venv/bin/python elsewhere
.venv/Scripts/python tools/vita/build.py "Mario Kart Wii (USA).wbfs"
```

**First build:**
- It takes 30–60 minutes.
- Every step is skipped once done, so rerun the same command to resume after a failure.
- After changing only code, `tools/vita/build.py --skip-assets` rebuilds just the VPK in a minute or two.

**What the steps do:**
1. **Disc check:** unpacks the disc and checks every file against the clean USA disc (`tools/release/usa-disc.json`).
2. **Cook:** 43 steps that convert courses, characters, vehicles, menus, movies and sound (`tools/release/build_cia.py` `COOK_STEPS`).
3. **Package:** stages the files into `build/vita/data/mkw` and makes the LiveArea art from the disc's title screen.
4. **Compile:** builds the game with CMake (`CMakeLists.txt`) and packs `mkw.vpk`.

## 3. Install

1. Install `build/vita/mkw.vpk` with VitaShell.
2. Copy the contents of `build/vita/data/mkw/` to `ux0:data/mkw/`.
3. Make sure `ur0:data/libshacccg.suprx` exists. If it doesn't, run [ShaRKF00D](https://github.com/Rinnegatamante/ShaRKF00D) once.

## Build options

| | |
|---|---|
| `tools/vita/build.py --release` | No test hooks or `runtime.log` |
| `cmake -G Ninja -B build/vita && cmake --build build/vita` | The VPK only (VITASDK set, sources bootstrapped) |
| `tools/vita/build_assets.py <disc>` | The game files only |

## Debug switches

Create these files (they can be empty) to change behaviour at start-up:

| File | Effect |
|---|---|
| `ux0:data/mkw/gpu-sync.txt` | Wait for the GPU every frame, as the 3DS does. Slower; use it to compare when something flickers. |
| `ux0:data/mkw/gpu-trace.txt` | Log every draw's state in a few frames to `vita.log` |
| `ux0:data/mkw/no-shader-cache.txt` | Always compile shaders (ignore `ux0:data/mkw/shaders/`) |
