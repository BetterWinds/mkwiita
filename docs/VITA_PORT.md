# How the Vita port works

MKW-3DS is written against libctru (the 3DS system library) and citro3d (its
GPU library). This port leaves the game's code (`src/`, `include/`) almost
untouched. It replaces those two libraries with Vita implementations in
`platform/vita/`.

```
src/ (game)  ──►  <3ds.h>, <citro3d.h>  ──►  platform/vita/  ──►  VitaSDK, vitaGL
Kinoko (physics)                              ctru_*.cpp: system, input, sound
                                              c3d_*.cpp:  GPU
```

## Files

| File | What it replaces |
|---|---|
| `platform/vita/include/3ds.h` | libctru's header: the types, GPU enums and shader-binary structures are libctru's own (`vendor/libctru`); the functions are declared here |
| `platform/vita/src/ctru_sys.cpp` | Threads, locks, events, timing, buttons/stick/touch, APT, memory |
| `platform/vita/src/ctru_ndsp.cpp` | The 3DS DSP: a software mixer with 24 voices, DSP-ADPCM/PCM, the IIR low-pass and a 48 kHz SceAudioOut stream |
| `platform/vita/src/c3d_gpu.cpp` | citro3d's GPU state, textures, render targets, draws and the final present |
| `platform/vita/src/c3d_shader.cpp` | GLSL ports of `src/mkw.v.pica` and `src/effect.v.pica`, fragment shaders generated from the texture combiner, the program cache |
| `platform/vita/src/zeroed_new.cpp` | `operator new` returning zeroed memory (see below) |

citro3d's matrix maths and `.t3x` loader, and libctru's LZ decompressor, are
compiled unchanged (`CMakeLists.txt`, target `ctrport`).

## Graphics

- **Texture combiner (TEV):**
  - Each distinct combination of the six combiner stages, alpha test and bound texture units becomes a generated fragment shader.
  - The shader follows Azahar's semantics: stage-0 "previous" reads source 3, there is a combiner buffer, every stage rounds to 8 bits, and the alpha test truncates.
  - Compiled programs are saved as binaries in `ux0:data/mkw/shaders/` and preloaded at start-up.
- **Vertex shaders:**
  - Hand-ported line by line from the PICA assembly.
  - The game writes the PICA float-uniform file; the shader reads it as `c[]` with `.wzyx`, because citro3d stores vectors w,z,y,x.
  - The bone palette is a separate uniform, uploaded only for skinned draws.
- **Depth:**
  - PICA clip z is in [-w, 0], with depth -z/w (1 near, 0 far); the game tests GEQUAL and clears to 0.
  - The shader writes z' = w + z, so GL depth is 1 − PICA depth. Compares are mirrored, and a clear to 0 becomes GL's usual clear to 1.
  - vitaGL's clear-to-0 quad sits on the clip boundary and left stale depth behind; that was the cause of the missing race scene.
- **Textures:**
  - PICA textures are 8×8 Morton-tiled, top row first.
  - They're converted on the thread that flushes them (usually the asset loader) and uploaded when first bound.
  - ETC1 stays compressed: blocks are reordered, byte-swapped and flipped vertically with bit operations.
  - Everything else becomes RGBA8 with the PICA's sampled values.
- **Render targets:**
  - Targets keep their portrait 3DS shapes (240×400) at twice the resolution.
  - The present pass rotates the top screen onto the display, undoing `Mtx_PerspTilt`.
  - Texture-backed targets (bloom) follow GL's window-to-texel mapping, as the PICA does.
- **LINEAR memory:**
  - LINEAR memory is GPU-mapped vitaGL pool memory, and draws read vertex and index data in place.
  - The game rewrites some of that data every frame (sprites, effects, CPU-skinned models). citro3d made this safe by waiting for the GPU in `FrameBegin`.
  - Here, ranges flushed in the last three frames are copied into vitaGL's scratch memory at the draw instead, so there's no per-frame stall.

## Memory the 3DS happened to zero

Kinoko's `Vector3f` is uninitialized by default. Some game state (for example,
the race camera) started from whatever memory held. On the 3DS that was zero;
on the Vita it was garbage that turned into NaN and hid every race model. The
build uses `-ftrivial-auto-var-init=zero`, and `operator new` returns zeroed
memory.

## Sound

The NW4R sound engine port (`src/snd_engine.cpp`, `src/sound_system.cpp`)
drives the DSP through libctru's NDSP API: wave buffers, ADPCM coefficients,
mix levels, rate and a filter per channel. `ctru_ndsp.cpp` implements that API:
- It decodes and resamples each voice, applies the filter, and mixes to stereo.
- It advances the DSP frame clock (160 samples at 32728 Hz) by the samples it outputs.
- It calls the game's frame callback.

## Single screen

The lower screen's pass isn't drawn. During races,
`RaceBottomScreen::drawMini` (`src/race_bottom_screen.cpp`) draws a Wii-style
course map on the right instead. The course outline comes from the KMP
checkpoints (`MapdataCheckPoint::left()/right()`, added in
`patches/kinoko-arm11.patch`) and is rasterized once per course into a
texture.

## Paths

Game files and saves are in `ux0:data/mkw/`, which replaces
`sdmc:/3ds/mkw-3ds/`. Logs are `vita.log` (this layer) and `runtime.log` (the
game, in non-release builds).
