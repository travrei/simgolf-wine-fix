# Validation — v0.2.0

- All 21 Python tests passed with the user's reference original DLL supplied locally.
- Five synthetic different-hash variations completed check/apply/check/reapply/restore successfully: PE timestamp, PE checksum, DOS message, appended overlay, and the earlier pixel-format-only fix.
- Each variant restored its own original bytes exactly. Appended overlay bytes remained intact after patching.
- Incompatible architecture, image base, image size, pixel format, missing call sites, invalid relocations, missing imports, excessive section counts, and truncated files were refused.
- Required import names were checked: replacing GetModuleHandleA with GetModuleHandleW was refused.
- A backup belonging to a different compatible variant was refused for installation and restoration.
- Modified patched files, missing or corrupt backups, symlinks, and corrupted payloads remained protected by the original tests.
- The reference DLL still produced SHA-256 96befb7be17227e33b9a0b1bef84b22777124f9dd80750dffe1a7cde87fd4d6b.
- The injection source and binary payload are unchanged from v0.1.0. The prior native color-conversion and exact payload-build results still apply.

Different-hash variants above are generated test cases, not independently acquired or gameplay-tested releases. Visual validation is inherited from the exact v3 renderer bytes previously confirmed at800×600. No claim is made that all files named Terrain.dll are compatible.

Proprietary game files are not included as fixtures or release assets.
