# 0.81 Execution Comparison

`tools/run_execution_sweep.py` updates all selected Windows fixtures through the
application's real offline inspection/installation CLI. It verifies both clean
and working executable hashes. The clean set is never modified or injected.
The runner adds the separately hash-verified optional native x86 runtime after
installation; that extra copy is explicitly recorded, not attributed to the
installer's normal deployment capabilities.

The sweep runs clean baselines first, automatic x64 NVIDIA DLSS5/Phoenix DLSS5 cases next,
then three x86 execution choices. Each launched case uses five seconds warmup
and twenty measured seconds, without VSync, at 1920x1080 except native Glide
856x480. The source scene and camera remain frozen. DOS is a separate VGA test
through DOSBox Enhanced, not an x86 ReShade transport benchmark.

The five/twenty-second values are targets. Fixture timing starts and ends on
rendered-frame boundaries; very slow software renderers can overrun by a frame.
The recorded actual duration is used for FPS, not a fabricated twenty-second
denominator. These workloads are retained as compatibility cases.
Readiness gets a bounded grace period of three measured clean frame times
after nominal warmup (minimum twenty, maximum forty-five seconds). This does
not lengthen the requested measurement or permit a missing ReShade endpoint.

| x86 choice | Phoenix DLSS5 | NVIDIA DLSS5 | Required observed execution |
| --- | --- | --- | --- |
| External x64 helper | Run | Run | `helper`, inference PID is helper PID |
| x64 library inside x86 | Run | Run | `in_process_x64_library`, inference PID is fixture PID |
| x86 Phoenix DLSS5 + native driver | Run | Not applicable | `in_process_x86_driver`, inference PID is fixture PID |

Fallback is disabled for explicit native x86 choices. A different observed
route fails the case instead of reporting the helper's performance under an
in-process label. All three routes retain the full eight-block network, one
pass, 1:1 resolution and the same appearance controls/model source.

Each passing case retains **one** screenshot after measurement and separate
game-loop and fresh processed-output rates. Failed cases retain neither image
nor FPS. Unsupported NVIDIA DLSS5 x86 graph-host cases are tagged **Not applicable**
without launching a redundant helper test. Staged diagnostics are discarded;
only compact errors and relevant ReShade warnings survive a failure.

The separate DOS rows are included in the CSV with architecture `dos` and an
explicit `fps_scope`, but excluded from Windows totals and x86 route rankings.
The DOS guest clock and DOSBox host clock are different measurements; their
rates must not be interpreted as an enhancement speedup.

Results replace this runner's own `runs/latest-x64-backends` output. A compact
copy of the preceding scores remains in `state/previous-execution-scores.json`
for the native/x64 comparison; it contains no old screenshot archive. `--resume`
preserves successful cases and retries incomplete/failed ones. Use `--stage`
to restrict a resumed run to `baseline`, `x64` or `x86`.

```powershell
python tools/run_execution_sweep.py --installer <application.exe> --payload <payload-folder> --candidate <verified-addon-package>
python tools/summarize_execution_sweep.py
```

The summary produces `execution-scores.csv`, `execution-comparison.json` and
`execution-comparison.md` in the current output. All route labels are also in
the capture filenames/manifests, raw results, dashboard badges and CSV exports.
Dashboard comparisons reuse each fixture's one clean baseline in memory rather
than saving duplicate baseline images. Each requested route remains a separate
comparison case; it never overwrites another route for the same renderer.

The x86 route ranking uses the **same passing fixture set across all required
routes within each renderer**. Phoenix DLSS5 needs three successful routes; NVIDIA DLSS5
needs two. It uses fresh output throughput, not repeated game presentations or
helper swapchain FPS. Output interval (`1000 / processed FPS`) is not isolated
GPU inference latency. Failure counts and per-fixture scores remain visible even
when a fixture cannot enter that matched ranking.

The five-second warmup starts with the fixture, not renderer readiness. Cases
whose first enhanced output arrives after that warmup are marked **Startup in
measurement** in the dashboard and exports. Their retained throughput includes
initialization; it must not be presented as steady-state inference performance.
The route ranking reports how many matched cases have this flag.

Changes against previous scores are single-run observations. Clean baselines
contain no add-on, so a changed native score cannot be an add-on optimization.
Hidden-window, frozen-scene fixtures establish delivery and route compatibility,
not visible-game performance, temporal quality or blanket retail-game support.
