MUSEUM DOS - a real 3D VGA gallery
=================================

Requires DOS, a 386 with an x87 coprocessor or later CPU, VGA and at least
32 MB RAM (64 MB recommended). A Pentium-class CPU is more practical.
Run MUSEUM.EXE from this directory. CWSDPMI.EXE must remain beside it.
The supplied DOSBox Staging launcher is recommended on modern Windows.

This is a CPU software renderer using VGA BIOS mode 13h, 320x200, 256 colours.
It draws actual 3D triangles from the common museum snapshot, reduced with
vertex clustering. All 24 scene textures are converted to 256x256 palettized
maps. It is not a still image or a Windows application disguised as DOS.
The skeletal pose is frozen, like the Windows fixtures. The camera can move.

Controls:
  F1: room view           F2: focused face
  WASD or arrows: move    IJKL: look
  A/D: strafe             Q/E: move down/up
  R: reset view/time      F / Space: freeze all automatic motion
  O: orbit/free camera    T: toggle lighting animation
  B: toggle camera motion (automatic sway or orbit)
  Orbit: A/D rotates, W/S zooms, Q/E changes elevation.
  Manual inspection is available while frozen; the pose is always static.
  F12: save capture       Escape: exit

Command examples:
  MUSEUM --room
  MUSEUM --seconds 30 --capture-at 15
  MUSEUM --seconds 40 --capture-at 5,15,30
  MUSEUM --seconds 20 --capture-every 5
  MUSEUM --seconds 20 --capture-at 1 --capture-at 3,7 --capture-every 5
  MUSEUM --mode matched --frames 30 --fixed-time
  MUSEUM --room --tour --frames 10
  MUSEUM --freeze
  MUSEUM --orbit --animations off --seconds 30 --capture-at 15
  MUSEUM --camera orbit --camera-motion off

--animations on/off controls the gentle showcase light pulse.
--camera-motion on/off controls automatic sway and orbit.
--no-animations aliases --animations off; --tour aliases --orbit.
Freeze and --fixed-time stop both clocks; capture/run timing remains real time.

Matched uses full-bright texture colours; showcase applies interpolated
baked lighting. Both use perspective-correct textures, depth testing,
alpha cutouts and near-plane clipping. DOS matched is a retro interpretation,
not a pixel-parity baseline for the Windows renderers.

Timed runs write CAP00001.BMP, CAP00002.BMP, etc. (read back from VGA memory),
FPS.CSV and RESULT.JSN (JSON with an 8.3-safe filename). CAPTURE.BMP retains
the first image. Requested/actual capture times and frame numbers are in JSON.
Lists and intervals combine into one sorted, deduplicated schedule. Zero and
end-of-run capture times are allowed. Several targets spanned by one slow frame
produce separate files from that frame, marked shared_frame. Up to 10000 shots
are supported; intervals require a finite positive run time. Pending shots are
reported if a frame limit or user exit ends the run first.
For long schedules use --capture-file SHOTS.TXT, one time in seconds per line.
The Windows launcher writes that file automatically to bypass DOS's short
command-tail limit. It also provides --capture-at/--capture-every directly.
Without a time/frame limit the
program stays interactive. The Windows launcher converts the capture to PNG
and provides a 4:3 preview; background launches default to 30 seconds and
capture at 15 seconds. FPS measured in DOSBox describes emulation, not the
speed of a physical 386/Pentium.

The portable ZIP contains independent ordinary files and original source.
The installed sets find the common dos/assets folder through relative paths.
The launcher mounts that folder as drive D: inside DOSBox. No links are needed.
Windows API smoke-test tools list 82 Windows fixtures; DOS is a separate bonus
fixture and uses tools/run_dos.py instead of tools/run_background.py.

Build: DJGPP GCC 12.2.0, build-djgpp v3.4.
https://github.com/andrewwutw/build-djgpp/releases/tag/v3.4
DJGPP library/runtime redistribution terms: DJGPP.TXT, LIBCOPY.TXT and
GPLCOPY.TXT. DJGPP source and complete distribution: https://www.delorie.com/djgpp/
Emulator: DOSBox Staging 0.83.0 (GPL); its LICENSE.txt is in the emulator folder.
https://github.com/dosbox-staging/dosbox-staging/releases/tag/v0.83.0

CWSDPMI release 7 is Copyright (C) 1995-2010 Charles W Sandmann.
Its unmodified binary is redistributed under the terms in CWSDPMI.TXT.
You have the right to obtain its source code and/or binary updates:
https://ftp.gwdg.de/pub/msdos/gcc/djgpp/v2misc/csdpmi7s.zip
https://ftp.gwdg.de/pub/msdos/gcc/djgpp/v2misc/csdpmi7b.zip

Gallery art credits and original licences: ASSETS/CREDITS.md and
ASSETS/licenses. Rocketbox characters are copyright Microsoft, MIT licence;
Poly Haven exhibits are CC0. See retained notices for authors and sources.
