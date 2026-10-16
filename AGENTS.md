# Project instructions

These storage and testing rules were requested by the user. Follow them for all work in this folder.

- Maintain the two published sets only: `games` and `clean/games`. Update both when rebuilding. Preserve installed ReShade files and settings in the working set.
- Do not accumulate old builds, compiler outputs, test-game copies, baseline backups, screenshots or diagnostic history. Do not recreate `cases`, `baselines` or `evidence` unless the user explicitly requests retained artifacts.
- Use temporary directories for compilation, staging, release preparation and build validation. Remove them in a `finally` block or context manager on success AND failure. Put compiler objects inside that temporary staging tree.
- Keep only the current `pristine.zip` and checksum. Replace the archive atomically; never automatically copy the previous archive into a backup folder.
- Keep only compact current build metadata and the matched reference image in `state`. Keep `build/scene`: it is the source asset snapshot needed by rebuilds, not an old executable build.
- Default benchmark runs replace their own `runs/latest*` output. Keep multiple runs or a separately named `--output` only when explicitly requested. Never erase an explicitly named output directory automatically.
- Do not launch games, GPU tests, DOSBox, full validation or repeated smoke tests unless the user asks for testing. Normal rebuilds compile and publish without game launches. `--validate` is an explicit opt-in, not permission to test autonomously.
- Do not create extra portable installer cases unless the user requests them. Select only the requested fixtures; portable cases copy assets and can consume substantial space. Remove temporary cases when finished.
- Keep assets common and locate them through relative paths. Do not introduce filesystem symlinks/junctions or per-game asset copies for normal sets.
- Preserve `games`, `clean`, `shared-assets`, `build/scene`, `dos`, `vendor`, `src`, `tools`, the current baseline and their configuration. Restrict cleanup to verified paths inside this project; reject links and never follow them during recursive deletion.
