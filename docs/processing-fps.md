# Processing Location and FPS

`execution_mode` is observed from the runtime, not inferred from whether the
fixture window is hidden. `helper` means a separate background graphics process;
`in_process` means the evaluator runs inside the fixture. A hidden native
baseline is not a background inference run.

For enhanced Windows runs, the primary output FPS is the increase of the
runtime's `delivered` counter per host-wall-clock second. Repeated presentation
of an older result does not increment this counter. The separate game-loop FPS
can be much higher and does not measure neural processing throughput.

The runner collects counters before and after the five-second warmup plus
twenty-second measurement window. Counter values at the exact measurement
boundaries use bounded linear interpolation between adjacent samples. There is
no extrapolation, inference-time reciprocal, or normalization over only the
last few ready seconds. Counter resets, missing window coverage and no output
progress invalidate the measurement. Failed runs keep neither images nor FPS.

`fps.json` stores fresh-output samples as its primary series, including the
nested `measurement` object. Raw fixture metrics use explicit `game_` names:
`game_fps`, `game_samples`, `game_measurement`, and the corresponding frame and
timing fields.

`--rerun-background` creates one current plan from observed helper-backed runs,
including failures, removes only their owned result files, and queues those
exact fixture/backend pairs. Clean baselines, in-process results and DOS remain
untouched. `--resume-background` resumes that plan through the normal detector
and installer. Addon identity comes from the installer's resolved payload path,
including content-addressed x86 companions, not a possibly stale loose filename.

`refresh_background_metrics.py` can rebuild selected metric metadata from saved
completion counters without relaunching a fixture. `verify_background_rerun.py`
checks the resulting rates, single screenshots, observed processing locations,
installation identities, and hashes of all preserved result files.

DOS rates retain their separate native-resolution and clock definitions in
`dos-fps.md`.
