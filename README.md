# SimGolf Wine Fix

[Leia em português](README.pt-BR.md)

Community rendering fix for Sid Meier's SimGolf on Linux with Wine.

**v0.2.0 removes the fixed original-DLL SHA-256 requirement.** The patcher checks the DLL structure, required imports, pixel-format descriptor, OpenGL call sites, and relocations instead. Compatible files with different metadata, overlays, or checksums can be patched while preserving unrelated bytes.

The injected rendering fix is unchanged from v0.1.0. Its visual result was confirmed at 800×600 on Fedora 44, Wine 11.0 Staging, Radeon RX 6750 XT, and Mesa 26.2.3. This remains a preliminary release; structurally different game builds are not automatically supported.

## Project history and AI assistance

I started reverse engineering SimGolf in 2024. As AI coding tools improved, I continued the project through "vibe coding", using AI assistance to develop and test this patch.

— Andrei Esteves dos Reis Bonfante (@travrei)

## Install

Requires Linux, Python 3.9+, Wine with working OpenGL, and an existing game installation. No compiler or Python packages are needed to apply the patch.

Close the game. Extract this package and open a terminal in its directory:

```bash
python3 patch.py check '/path/to/SimGolf'
python3 patch.py apply '/path/to/SimGolf'
```

You can also pass the full path to Terrain.dll. The patcher creates `Terrain.dll.simgolf-wine-fix.backup` beside that file, then installs the correction. An existing backup must match the current original exactly. Repeated application is recognized without patching twice.

Launch from the game directory:

```bash
cd '/path/to/SimGolf'
wine ./golf.exe
```

## Restore

From the extracted patch directory:

```bash
python3 patch.py restore '/path/to/SimGolf'
```

**Keep the backup.** For variants with different hashes, it is also needed to recognize a previously patched file. Restoration checks that rebuilding from that exact backup reproduces the current DLL, then restores the backup byte for byte. Later edits to the patched DLL are refused rather than overwritten. The backup remains after restoration.

## Compatibility checks

The v3 injection payload has fixed internal addresses. Version 0.2.0 checks the necessary x86 PE32 layout, image base, section ranges, named imports at the required slots, pixel-format structure, 10 glFlush sites, 22 glBegin sites, and their relocations. It rejects truncated files, incompatible layouts, and conflicting earlier modifications.

There is no fixed hash gate on the user's original DLL. The included payload still has an integrity checksum. The original and patched hashes below are regression references, not an installation allowlist:

- Original reference: `378e61d2f2061f85e517eade8b64e92ecde00d30ab866c091d55cb737adce0a4`
- Patched reference: `96befb7be17227e33b9a0b1bef84b22777124f9dd80750dffe1a7cde87fd4d6b`

Matching the structure does not prove compatibility with every modified binary. Five synthetic compatible variations were tested automatically, alongside the reference game DLL. Other builds still need gameplay testing.

## Scope

This patch synchronizes the game's GDI bitmap and OpenGL framebuffer, including RGB555/RGB565 conversion. It modifies Terrain.dll only and retains the original resolution. Widescreen is not included.

A full-ISO installation may fail before rendering, for example with a SecDrv driver error. This rendering patch does not change golf.exe or address that separate startup failure. The original ISO Terrain.dll examined during development was already supported by v0.1.0.

Game executables, game DLLs, and assets are not included. The project contains only original patch code, its compiled injection payload, documentation, and tests.

## Build and test

Rebuilding requires GCC with freestanding `-m32` support, GNU binutils with elf_i386 support, Bash, and Python 3. No Windows headers or MinGW are required.

```bash
bash build_payload.sh
python3 -m unittest discover -s tests
SIMGOLF_ORIGINAL_DLL='/path/to/unpatched/Terrain.dll' python3 -m unittest discover -s tests
```

Integration tests use the reference original hash above and create temporary copies; game binaries are never distributed as fixtures. Without that environment variable, those tests are skipped. Build output goes to `build/`; the packaged payload is preserved. GCC 16.2.1 reproduced that payload exactly. Different compiler output is not silently accepted by the installer. The injected section contains code and mutable state, so the linker emits an expected RWX warning.

See [VALIDATION.md](VALIDATION.md) for release checks. Report problems with patch version, Wine version, GPU/driver, resolution, `check` output, and reproduction steps.

## License

Original project code is [MIT-licensed](LICENSE). SimGolf and its assets remain the property of their respective owners. This is an unofficial community project.
