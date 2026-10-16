# Installer-driven x64 backend sweep

`tools/run_backends.py` runs the x64 entries of `matrix.json` through the real
DLSS5 Everything inspection and offline installation commands. It never
installs into `clean/games`, selects x86 fixtures, or overrides an antivirus block.

Each successful launch renders at 1920x1080 in the frozen showcase scene. VSync
is disabled: DXGI sync interval zero, D3D9 immediate presentation, GL/EGL interval
zero, Glide swap interval zero, and Vulkan immediate (or mailbox when immediate
is unavailable). Bundled wrappers also disable forced synchronization. Driver or
compositor restrictions are not overridden; unavailable uncapped presentation is
reported as a failed benchmark, not silently treated as uncapped FPS.

The fixture waits five render seconds, then measures the next twenty seconds at
frame boundaries. Warmup, initialization and screenshot work are excluded from
the published FPS. Exact start/end times and actual duration are retained, since
the final frame can cross the twenty-second boundary on slow renderers.
After measurement, one screenshot is taken. Enhanced modes do not perform an
additional unprocessed fixture readback. A failed mode publishes no image or FPS.
Hidden-window presentation is not equivalent to visible-game FPS or latency.

- **native:** executable from `clean/games`, fixture GPU readback, no ReShade or Phoenix processing.
- **nvidia:** backend 1, NVIDIA NR feature creation/evaluation and current-selection
  presentation must be observed. Images use Phoenix's presented-output capture.
- **phoenix:** backend 3, current-selection enhanced presentation must be observed.
  Images use the same presented-output capture API.

Game FPS comes from the fixture render loop. Neural FPS is the change in delivered
frames divided by elapsed render time between first/last ready observations inside
the measured window. It is not the same as game-loop FPS. The full timing samples, readiness and
GPU interval rows are saved locally in each case's `processing.json`.

A central pixel comparison against the frozen original must show a measurable
change. This checks delivery, not subjective quality or temporal gameplay.
Missing enhanced screenshots never fall back to unprocessed fixture captures.
Unsupported installation routes and runtime errors remain failures, not zero-FPS
measurements or successful unchanged screenshots.

The clean and working executables must both match the same matrix SHA256 before
any run. Native baselines run once from the clean set; each working fixture then
runs once with NVIDIA and once with Phoenix. Baseline files are not installed into
or restored. Captures are named with fixture, backend and resolution, and their
manifest records include source set and build hash.

All runtime images and FPS are staged outside the dashboard. Only successful
modes publish them. Failed modes publish a failure tag/reason only. A missing
ReShade/Phoenix endpoint or failed processing can close a test early.

The current output is `runs/latest-x64-backends`. `--clear-history` explicitly
clears generated result/image history (not scene assets or the matched reference).
Use `--resume` to retain passing
cases from the same build and benchmark profile, and retry failures. Capped or
720p results cannot be resumed as current 1080p measurements.
Without it, only this runner's own default output is
replaced. Runtime evidence is local; do not publish logs or machine paths.

The dashboard indexes these files on refresh, filters by native/nvidia/phoenix,
and exposes separate game/neurally delivered FPS columns and chart metrics.
