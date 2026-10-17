# Installer-driven x86/x64 backend sweep

`tools/run_backends.py` runs every entry of `matrix.json` through the real
DLSS5 Everything inspection and offline installation commands. It never
installs into `clean/games` or overrides an antivirus block. Use `--architecture`
to restrict a run to x86 or x64; the default covers both.

Windows launches render at 1920x1080 in the frozen showcase scene, except the
Glide fixtures' native 856x480 API mode. Their metadata, capture filenames and
resume profiles retain that actual extent; they are not 1080p benchmarks. VSync
is disabled: DXGI sync interval zero, D3D9 immediate presentation, GL/EGL interval
zero, Glide swap interval zero, and Vulkan immediate (or mailbox when immediate
is unavailable). Bundled wrappers also disable forced synchronization. Driver or
compositor restrictions are not overridden; unavailable uncapped presentation is
reported as a benchmark warning, not a compatibility failure or uncapped FPS.

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

Game FPS comes from the fixture render loop. Enhanced output FPS counts fresh
delivered frames over the full measured window, using bounded interpolation at
the window boundaries. It never shortens the interval to the first and last ready
observations. Game-loop metrics are kept separately. See `processing-fps.md`;
the full timing samples, readiness and GPU interval rows stay in local output.

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

All runtime images and FPS are staged in local output. Only successful
modes publish them. Failed modes publish a failure tag/reason only. A missing
ReShade/Phoenix endpoint or failed processing can close a test early.

The current output is `runs/latest-x64-backends`. `--clear-history` explicitly
clears generated result/image history (not scene assets or the matched reference).
Use `--resume` to retain passing
cases from the same build and benchmark profile, and retry failures. Capped or
720p results cannot be resumed as current 1080p measurements.
Without it, only this runner's own default output is
replaced. Runtime evidence is local; do not publish logs or machine paths.

The summary records whether enhancement ran in process or in the private
background helper. Unsupported routes retain failure records only.

ReShade 6.8 upgrades requested OpenGL versions below 4.3 to a 4.3 compatibility
context. The GL 3.3 fixture records this adjustment and permits it only when the
loaded OpenGL proxy exports ReShade's addon API. Its clean baseline still requires
core profile; GL 4.6 still requires core profile even when injected. This is not
proof that applications insisting on an exact 3.3 core profile accept ReShade.

## DOS

`tools/run_dos_backends.py` covers the DOS VGA fixture separately through the
application's `--prepare-dos` command and the current DOSBox Enhanced package.
Its clean baseline uses DOSBox Staging; enhanced runs use DOSBox Enhanced's
built-in, in-process D3D12 Phoenix/NVIDIA renderer, not ReShade injection.
Source resolution remains 320x200. Each successful mode retains one screenshot;
the enhanced renderer must advance its provider-specific inference counter and
presentation count and produce changed pixels. DOS guest/emulator FPS is not
published as comparable Windows game FPS. Failed modes retain failure records only.
