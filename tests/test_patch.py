"""CLI safety tests; optional integration tests use a user's own Terrain.dll."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import struct
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patch.py"
ORIGINAL_SHA256 = "378e61d2f2061f85e517eade8b64e92ecde00d30ab866c091d55cb737adce0a4"
PATCHED_SHA256 = "96befb7be17227e33b9a0b1bef84b22777124f9dd80750dffe1a7cde87fd4d6b"
ORIGINAL_DLL = os.environ.get("SIMGOLF_ORIGINAL_DLL")
BACKUP_NAME = "Terrain.dll.simgolf-wine-fix.backup"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(directory, include_directory_times=False):
    """Capture files and symlinks; optionally detect temporary directory writes.

    Apply/restore may briefly create a lock, changing directory timestamps even
    when no game file changes. Read-only checks include those timestamps too.
    """
    result = {}
    for path in sorted(directory.rglob("*")):
        stat = path.lstat()
        if path.is_symlink():
            content = ("symlink", os.readlink(path))
        elif path.is_file():
            content = ("file", path.read_bytes())
        else:
            content = ("directory",)
        modified = stat.st_mtime_ns
        if content[0] == "directory" and not include_directory_times:
            modified = None
        result[str(path.relative_to(directory))] = (
            stat.st_mode, modified, content
        )
    return result


class CommandTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="simgolf-patch-test-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.game = self.directory / "game with spaces"
        self.game.mkdir()
        self.dll = self.game / "Terrain.dll"
        self.backup = self.game / BACKUP_NAME
        (self.game / "unrelated.txt").write_text("Keep this file unchanged.\n")

    def command(self, action, target=None, expected=0, script=PATCH):
        completed = subprocess.run(
            [sys.executable, str(script), action,
             str(self.game if target is None else target)],
            cwd=self.directory,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )
        self.assertEqual(
            completed.returncode, expected,
            f"{action} returned {completed.returncode}:\n"
            f"{completed.stdout}{completed.stderr}",
        )
        return completed


class StandaloneTests(CommandTestCase):
    """These tests require no proprietary game files."""

    def test_help(self):
        completed = subprocess.run(
            [sys.executable, str(PATCH), "--help"],
            text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        for action in ("check", "apply", "restore"):
            self.assertIn(action, completed.stdout)

    def test_missing_dll_does_not_create_files(self):
        before = snapshot(self.directory)
        for action in ("check", "apply", "restore"):
            with self.subTest(action=action):
                self.command(action, expected=2)
                self.assertEqual(snapshot(self.directory), before)

    def test_missing_directory_is_not_created(self):
        missing = self.directory / "does not exist"
        before = snapshot(self.directory)
        for action in ("check", "apply", "restore"):
            with self.subTest(action=action):
                self.command(action, target=missing, expected=2)
                self.assertFalse(missing.exists())
                self.assertEqual(snapshot(self.directory), before)

    def test_unknown_dll_is_never_changed(self):
        self.dll.write_bytes(b"Not a supported Terrain.dll.\x00\x01")
        before = snapshot(self.directory)
        for action in ("check", "apply", "restore"):
            for target in (self.game, self.dll):
                with self.subTest(action=action, target=target.name):
                    self.command(action, target=target, expected=2)
                    self.assertEqual(snapshot(self.directory), before)

    def test_symlink_dll_is_rejected_without_modification(self):
        external = self.directory / "external.dll"
        external.write_bytes(b"Symlink destination must stay unchanged.")
        self.dll.symlink_to(external)
        before = snapshot(self.directory)
        for action in ("check", "apply", "restore"):
            with self.subTest(action=action):
                self.command(action, expected=2)
                self.assertEqual(snapshot(self.directory), before)


@unittest.skipUnless(ORIGINAL_DLL, "Set SIMGOLF_ORIGINAL_DLL to test your own game DLL")
class IntegrationTests(CommandTestCase):
    def setUp(self):
        super().setUp()
        source = Path(ORIGINAL_DLL).expanduser()
        self.assertTrue(source.is_file(), f"Original DLL not found: {source}")
        self.assertEqual(sha256(source), ORIGINAL_SHA256,
                         "SIMGOLF_ORIGINAL_DLL must contain the supported original DLL")
        shutil.copy2(source, self.dll)

    def test_complete_lifecycle_and_idempotence(self):
        before = snapshot(self.game)
        read_only_before = snapshot(self.directory, include_directory_times=True)
        self.command("check")
        self.assertEqual(snapshot(self.game), before)
        self.assertEqual(snapshot(self.directory, include_directory_times=True), read_only_before)

        self.command("apply", target=self.dll)
        self.assertEqual(sha256(self.dll), PATCHED_SHA256)
        self.assertEqual(sha256(self.backup), ORIGINAL_SHA256)
        self.assertEqual(snapshot(self.game)["unrelated.txt"], before["unrelated.txt"])
        self.assertEqual(set(snapshot(self.game)), set(before) | {BACKUP_NAME})

        patched = snapshot(self.game)
        read_only_before = snapshot(self.directory, include_directory_times=True)
        self.command("check", target=self.dll)
        self.assertEqual(snapshot(self.directory, include_directory_times=True), read_only_before)
        self.command("apply")
        self.assertEqual(snapshot(self.game), patched)

        self.command("restore")
        self.assertEqual(sha256(self.dll), ORIGINAL_SHA256)
        self.assertEqual(sha256(self.backup), ORIGINAL_SHA256)
        self.assertEqual(snapshot(self.game)["unrelated.txt"], before["unrelated.txt"])
        restored = snapshot(self.game)
        self.command("restore", target=self.dll)
        self.command("check")
        self.assertEqual(snapshot(self.game), restored)

    def test_restore_original_without_backup_is_idempotent(self):
        before = snapshot(self.game)
        self.command("restore")
        self.assertEqual(snapshot(self.game), before)

    def test_corrupted_backup_blocks_restore(self):
        self.command("apply")
        self.backup.write_bytes(b"Corrupted backup")
        before = snapshot(self.game)
        self.command("restore", expected=2)
        self.assertEqual(snapshot(self.game), before)

    def test_missing_backup_blocks_restore(self):
        self.command("apply")
        self.backup.unlink()
        before = snapshot(self.game)
        self.command("restore", expected=2)
        self.assertEqual(snapshot(self.game), before)

    def test_modified_patched_dll_blocks_apply_and_restore(self):
        self.command("apply")
        modified = bytearray(self.dll.read_bytes())
        modified[-1] ^= 1
        self.dll.write_bytes(modified)
        before = snapshot(self.game)
        for action in ("check", "apply", "restore"):
            with self.subTest(action=action):
                self.command(action, expected=2)
                self.assertEqual(snapshot(self.game), before)

    def test_wrong_existing_backup_blocks_apply(self):
        self.backup.write_bytes(b"Another user's backup must not be overwritten.")
        before = snapshot(self.game)
        self.command("apply", expected=2)
        self.assertEqual(snapshot(self.game), before)

    def test_valid_existing_backup_allows_apply(self):
        shutil.copy2(self.dll, self.backup)
        backup_before = snapshot(self.game)[BACKUP_NAME]
        self.command("apply")
        self.assertEqual(sha256(self.dll), PATCHED_SHA256)
        self.assertEqual(snapshot(self.game)[BACKUP_NAME], backup_before)

    def test_supported_dll_symlink_is_rejected(self):
        external = self.directory / "external.dll"
        self.dll.rename(external)
        self.dll.symlink_to(external)
        before = snapshot(self.directory)
        for action in ("check", "apply", "restore"):
            with self.subTest(action=action):
                self.command(action, expected=2)
                self.assertEqual(snapshot(self.directory), before)

    def test_symlink_backup_blocks_apply(self):
        external = self.directory / "external-backup.dll"
        shutil.copy2(self.dll, external)
        self.backup.symlink_to(external)
        before = snapshot(self.directory)
        self.command("apply", expected=2)
        self.assertEqual(snapshot(self.directory), before)

    def test_corrupted_payload_blocks_apply_without_backup(self):
        package = self.directory / "damaged-package"
        (package / "payload").mkdir(parents=True)
        shutil.copy2(PATCH, package / "patch.py")
        payload = bytearray((ROOT / "payload" / "hook.bin").read_bytes())
        self.assertTrue(payload)
        packaged_payload = package / "payload" / "hook.bin"
        packaged_payload.write_bytes(payload)
        # First prove that the copied package runs; otherwise a missing runtime
        # dependency could masquerade as successful corruption detection.
        self.command("apply", script=package / "patch.py")
        self.assertEqual(sha256(self.dll), PATCHED_SHA256)
        self.command("restore", script=package / "patch.py")
        self.backup.unlink()
        payload[len(payload) // 2] ^= 1
        packaged_payload.write_bytes(payload)
        before = snapshot(self.game)
        self.command("apply", expected=2, script=package / "patch.py")
        self.assertEqual(snapshot(self.game), before)

    def test_different_hash_variants_roundtrip_without_losing_changes(self):
        reference = self.dll.read_bytes()
        pe = struct.unpack_from('<I', reference, 0x3c)[0]
        variants = {}
        for label, offset in [('timestamp', pe + 8), ('checksum', pe + 24 + 64),
                              ('dos_message', 0x80)]:
            data = bytearray(reference)
            data[offset] ^= 1
            variants[label] = bytes(data)
        variants['overlay'] = reference + b'Local distribution metadata\0'
        data = bytearray(reference)
        data[0x63e19] = 0
        variants['pixel_format_only_fix'] = bytes(data)
        for label, original in variants.items():
            with self.subTest(variant=label):
                if self.backup.exists():
                    self.backup.unlink()
                self.dll.write_bytes(original)
                self.assertNotEqual(sha256(self.dll), ORIGINAL_SHA256)
                self.command('check')
                self.command('apply')
                self.assertEqual(self.backup.read_bytes(), original)
                installed = self.dll.read_bytes()
                self.assertNotEqual(installed, original)
                if label == 'overlay':
                    self.assertEqual(installed[len(reference):len(original)], original[len(reference):])
                self.command('check')
                self.command('apply')
                self.assertEqual(self.dll.read_bytes(), installed)
                self.command('restore')
                self.assertEqual(self.dll.read_bytes(), original)
                self.command('restore')

    def test_incompatible_structures_are_refused_without_backup(self):
        reference = self.dll.read_bytes()
        pe = struct.unpack_from('<I', reference, 0x3c)[0]
        optional = pe + 24
        mutations = {
            'machine': (pe + 4, b'\x64\x86'),
            'image_base': (optional + 28, struct.pack('<I', 0x20000000)),
            'layout': (optional + 56, struct.pack('<I', 0x120000)),
            'pfd': (0x63e10, b'\x01'),
            'gl_flush_site': (0x4b5e, b'\x90'),
            'relocations': (0x6b004, struct.pack('<I', 3)),
            'missing_import': (optional + 104, struct.pack('<I', 0)),
            'huge_sections': (pe + 6, b'\xff\xff'),
        }
        for label, (offset, replacement) in mutations.items():
            with self.subTest(mutation=label):
                data = bytearray(reference)
                data[offset:offset + len(replacement)] = replacement
                self.dll.write_bytes(data)
                before = snapshot(self.game)
                for action in ('check', 'apply', 'restore'):
                    result = self.command(action, expected=2)
                    self.assertNotIn('Traceback', result.stderr)
                    self.assertEqual(snapshot(self.game), before)

    def test_wrong_function_in_required_import_slot_is_refused(self):
        data = bytearray(self.dll.read_bytes())
        location = data.index(b'GetModuleHandleA\0')
        data[location:location + 15] = b'GetModuleHandleW'
        self.dll.write_bytes(data)
        before = snapshot(self.game)
        self.command('apply', expected=2)
        self.assertEqual(snapshot(self.game), before)

    def test_backup_of_another_compatible_variant_is_not_used(self):
        reference = self.dll.read_bytes()
        pe = struct.unpack_from('<I', reference, 0x3c)[0]
        other = bytearray(reference)
        other[pe + 8] ^= 1
        self.backup.write_bytes(other)
        before = snapshot(self.game)
        self.command('apply', expected=2)
        self.assertEqual(snapshot(self.game), before)
        self.backup.unlink()
        self.command('apply')
        self.backup.write_bytes(other)
        before = snapshot(self.game)
        self.command('restore', expected=2)
        self.assertEqual(snapshot(self.game), before)

    def test_modified_variant_patch_is_not_overwritten(self):
        data = bytearray(self.dll.read_bytes())
        pe = struct.unpack_from('<I', data, 0x3c)[0]
        data[pe + 8] ^= 1
        self.dll.write_bytes(data)
        self.command('apply')
        data = bytearray(self.dll.read_bytes())
        data[-1] ^= 1
        self.dll.write_bytes(data)
        before = snapshot(self.game)
        for action in ('check', 'apply', 'restore'):
            self.command(action, expected=2)
            self.assertEqual(snapshot(self.game), before)

    def test_truncated_pe_is_refused(self):
        reference = self.dll.read_bytes()
        for length in (64, 250, 512, 8192, len(reference) // 2):
            with self.subTest(length=length):
                self.dll.write_bytes(reference[:length])
                before = snapshot(self.game)
                result = self.command('apply', expected=2)
                self.assertNotIn('Traceback', result.stderr)
                self.assertEqual(snapshot(self.game), before)


if __name__ == "__main__":
    unittest.main()
