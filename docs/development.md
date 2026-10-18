# Building and Running the Fixtures

The public dashboard works without building anything. A source checkout is not
a ready-to-run game bundle: scene inputs, SDKs and licensed runtime packages are
separate dependencies.

## Inputs

1. Install Python, Pillow and NumPy for the asset/build tooling. Install Node.js
   for the dashboard statistics tests. Playwright with Chrome is optional for
   headless dashboard checks.
2. Install Visual Studio 2022 C++ build tools and a Windows SDK. The scripts use
   `vswhere`; alternatively set `VS_BUILD_TOOLS` to the folder containing
   `vcvarsall.bat`.
3. Create your local `build-dependencies.json` from
   [the example](../build-dependencies.example.json). Point it to your gallery
   source/assets and Vulkan shader tooling. This local file is deliberately ignored.
4. Supply the scene snapshot and the declared third-party packages. The Windows
   pins are in [vendor/fullbench/dependencies.json](../vendor/fullbench/dependencies.json);
   the DOS toolchain/emulator pins are in
   [vendor/dos/dependencies.json](../vendor/dos/dependencies.json). These manifests
   are provenance, not a claim that every dependency is downloaded automatically.

Rebuilding the scene requires the external gallery input expected by
`tools/export_scene.py`. The source-only repository does not include that prepared
asset snapshot or redistribute vendor runtime DLLs. Keep their original licenses.

## Build Sets

```powershell
.\Rebuild-All.cmd
.\Rebuild-All.cmd --only dx11-x64 dos-vga
```

Builds update `games` and `clean/games` with matching fixture executables and
relative common-asset references. The working set preserves installed add-ons;
the clean set must remain uninjected. Factory wrappers are part of a wrapper
fixture's baseline. Builds do not launch tests unless `--validate` is explicit.

## Collect Native Results

```powershell
.\Run-All.cmd --suite .\clean --only dx11-x64 --fixed-time --seconds 25 --capture-at 25
```

For the measured neural-renderer protocol, use
[the execution sweep documentation](execution-sweep.md). It uses the actual
installer inspection/deployment CLI, verifies executable/package hashes and
observes where inference ran. Optional native x86 runtime deployment is currently
a documented runner supplement, not an installer feature claim.

## Browse or Publish Existing Results

`Dashboard.cmd` runs a read-only localhost indexer. It never launches games.
The checked-in [published dashboard](dashboard/index.html) is static and contains
only the selected public result snapshot.

```powershell
python tools/dashboard.py --export
python tools/export_public_dashboard.py --replace
python -m unittest discover -s tools -p "test_public_dashboard.py"
```

The public exporter removes private fields, rejects absolute host paths and
stores lossless images by decoded-pixel hash. It does not modify private raw
benchmark evidence. Republishing replaces its own manifest-owned snapshot;
unexpected files or links stop replacement.

## Fair Reruns

Use the same fixture/executable hashes, extent, camera, scene time, wrapper and
neural settings. Keep runs sequential, warmup/window lengths equal, and record
driver/hardware changes. Save initialization-affected scores as such. Never use
the parallel build-validator's FPS as a serial benchmark or turn failures into
zero-FPS measurements. Default runners replace only their own latest output.
