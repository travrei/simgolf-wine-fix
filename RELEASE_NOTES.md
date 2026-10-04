# SimGolf Wine Fix v0.2.0

This release removes the fixed SHA-256 requirement for the user's original Terrain.dll.

The installer now validates the PE layout, required imports, pixel-format descriptor, OpenGL patch sites, and relocations. Compatible DLLs with different metadata or overlays can be patched while unrelated bytes are preserved. Automatic backups and exact restoration remain supported.

The injected renderer fix is unchanged. The reference DLL still produces the same bytes as the visually confirmed v0.1.0 result. All 21 automated tests passed, including five synthetic different-hash variants and incompatible-file refusal cases. Broader gameplay compatibility remains unverified.

## Install

Close the game. Extract the archive and run:

```bash
python3 patch.py check '/path/to/SimGolf'
python3 patch.py apply '/path/to/SimGolf'
```

Keep Terrain.dll.simgolf-wine-fix.backup. To restore:

```bash
python3 patch.py restore '/path/to/SimGolf'
```

Requires Python 3.9+, Wine, and an existing game installation. No game files are included.

**Pre-release:** supports structurally compatible DLLs, not arbitrary layouts. Only the original 800×600 renderer has been visually confirmed. Widescreen and executable startup problems such as SecDrv failures are outside this rendering fix.
