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

- **native:** executable from `clean/games`, fixture GPU readback, no ReShade or Phoenix DLSS5 processing.
- **nvidia:** backend 1, NVIDIA DLSS5 NR feature creation/evaluation and current-selection
  presentation must be observed. Images use Phoenix DLSS5's presented-output capture.
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
runs once with NVIDIA DLSS5 and once with Phoenix DLSS5. Baseline files are not installed into
or restored. Captures are named with fixture, backend and resolution, and their
manifest records include source set and build hash.

All runtime images and FPS are staged outside the dashboard. Only successful
modes publish them. Failed modes publish a failure tag/reason only. A missing
ReShade/Phoenix DLSS5 endpoint or failed processing can close a test early.

The current output is `runs/latest-x64-backends`. `--clear-history` explicitly
clears generated result/image history (not scene assets or the matched reference).
Use `--resume` to retain passing
cases from the same build and benchmark profile, and retry failures. Capped or
720p results cannot be resumed as current 1080p measurements.
Without it, only this runner's own default output is
replaced. Runtime evidence is local; do not publish logs or machine paths.

The dashboard indexes these files on refresh, filters by native/nvidia/phoenix,
and exposes separate game/neurally delivered FPS columns and chart metrics.
The Execution column and summary record whether enhancement ran in process or
in the private background helper. Unsupported routes retain failure records only.

ReShade 6.8 upgrades requested OpenGL versions below 4.3 to a 4.3 compatibility
context. The GL 3.3 fixture records this adjustment and permits it only when the
loaded OpenGL proxy exports ReShade's addon API. Its clean baseline still requires
core profile; GL 4.6 still requires core profile even when injected. This is not
proof that applications insisting on an exact 3.3 core profile accept ReShade.

## DOS

`tools/run_dos_backends.py` covers the DOS VGA fixture separately through the
application's `--prepare-dos` command and the current DOSBox Enhanced package.
Its clean baseline uses DOSBox Staging; enhanced runs use DOSBox Enhanced's
built-in, in-process D3D12 Phoenix DLSS5/NVIDIA DLSS5 renderer, not ReShade injection.
Source resolution remains 320x200. Each successful mode retains one screenshot;
the enhanced renderer must advance its provider-specific inference counter and
presentation count and produce changed pixels. DOS guest/emulator FPS is not
published as comparable Windows game FPS. Failed modes retain failure records only.

## Verified sweep: 2026-10-17

The current run attempted all 82 Windows fixtures and the DOS fixture in native,
NVIDIA DLSS5 and Phoenix DLSS5 modes: 249 cases, 221 passed, 28 failed, none pending. All 83
clean baselines passed. Both enhanced modes passed on 68 Windows fixtures and DOS.
The runtime evidence and per-fixture route table are in
`runs/latest-x64-backends/compatibility.md`; the dashboard contains 249 result
sets and exactly 221 images. Successful enhancement used the background helper
in 128 cases and in-process execution in 10 cases (including both DOS modes).

Failures are retained explicitly:

- Eight installation rejections: four native x64 DirectDraw fixtures, both backends.
- Twelve stock ReShade exclusions: WARP DX10, DX10.1 and DX11, both architectures/backends.
- Eight readiness timeouts: software DX12 and D3D11-on-12, both architectures/backends.
  These timeouts do not establish that a longer-startup implementation is impossible.

The installer used its real inspection/deployment CLI with the fresh local payload;
internet downloads and the graphical installation workflow were not revalidated.
Component hashes matched the payload for every passing Windows enhancement.
The 45 CPU-side runner/dashboard regression tests passed. These frozen-scene,
hidden-window checks establish changed output delivery, not real-game temporal
quality or playable performance; some bridge paths remain very slow.

## Dashboard performance comparisons

The Performance view compares Native, NVIDIA DLSS5 and Phoenix DLSS5 with grouped bars
for all fixtures, or averages grouped by API, technology, architecture, transport
and observed execution route. Run-type checkboxes, processing-route and existing
catalogue filters also apply to the per-fixture comparison CSV export.

Game-loop FPS and delivered processed-frame FPS remain separate metrics. Relative
views show game FPS loss/retention against native, or either kind of FPS against
NVIDIA DLSS5 at 100%. Hidden reference series remain available for these calculations.
Failed runs stay visible without FPS; DOS contributes route evidence, not timing.

Matched averages require current successful results with the same executable,
profile, batch, resolution, requested timing, synchronization and scene/camera
state. Recorded NVIDIA DLSS5/Phoenix DLSS5 addon hashes must agree. Grouped means use the same
matched fixture set for every displayed backend. The latest failure never revives
an older passing run.

Mean FPS loss averages per-fixture percentages equally. Drop in mean FPS is
`100 * (1 - mean(enhanced FPS) / mean(native FPS))`, which weights fast baselines
more strongly. Normalized retention and the overall Phoenix DLSS5/NVIDIA DLSS5 ratio use
geometric means of positive per-fixture ratios. These are descriptive statistics
of the selected workloads, not quality scores or visible-gameplay guarantees.

`python tools/check_performance_ui.py --screenshots` checks the local, read-only
page headlessly using installed Chrome; it never launches benchmark fixtures.
The current desktop/mobile previews replace `dashboard/preview-performance-*.png`.
