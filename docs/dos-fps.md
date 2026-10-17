# DOS FPS

The DOS fixture remains at native 320x200. A successful run retains one image
per mode and now writes `fps.json` alongside the compatibility evidence.

- Native: guest render-frame deltas from `FPS.CSV`, using the emulated DOS
  `uclock` timestamps. These are guest render FPS, not physical DOS hardware FPS.
- Enhanced presentation: `graphics.presented` deltas over host monotonic time.
- Fresh enhanced output: `graphics.frames` deltas over the same host interval.
  This counter advances after a complete processing/composition/presentation
  operation. Model evaluation counters are not used as output FPS because
  multiple refinement passes may evaluate a model more than once per image.

All rates exclude the first five seconds and cover the subsequent twenty-second
window, with actual endpoint times retained. No rate is inferred from the
reciprocal of a single inference duration. Counter/time resets, incomplete
windows, wrong backends or input extents, and active frame generation invalidate
the enhanced measurement. Failed modes retain neither images nor FPS.

Native DOSBox Staging and DOSBox Enhanced use different emulator paths and
clocks. Their benchmark profiles are deliberately separate: raw rates can be
shown, but they cannot produce a matched native-loss percentage. NVIDIA and
Phoenix enhanced runs can be paired with each other when their other metadata
matches. These 320x200 results are not equivalent to 1920x1080 Windows results.

The current DOSBox Enhanced renderer requests synchronized presentation. Its
results record this rather than claiming VSync was disabled. Presentation FPS
can therefore be limited by refresh or by emulation/transfer overhead even when
the model itself finishes much faster.
