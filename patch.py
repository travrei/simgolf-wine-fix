#!/usr/bin/env python3
"""Install or restore the SimGolf Wine renderer fix using a verified local DLL.

No game files are included. Compatibility is checked by PE layout and patch sites,
not by requiring a particular original file hash.
"""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile

VERSION = '0.2.0'
ORIGINAL_SHA256 = '378e61d2f2061f85e517eade8b64e92ecde00d30ab866c091d55cb737adce0a4'
PATCHED_SHA256 = '96befb7be17227e33b9a0b1bef84b22777124f9dd80750dffe1a7cde87fd4d6b'
PAYLOAD_SHA256 = '5a7a71c9cb1b3b6db5f7d4f5d7a28882bd3792324f29a17baefd68c592d70ff3'
BACKUP_SUFFIX = '.simgolf-wine-fix.backup'
PAYLOAD = Path(__file__).resolve().parent / 'payload' / 'hook.bin'


class PatchError(Exception):
    """A validation failed; do not patch an unrecognized binary."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise PatchError(message)


def validate_layout(data):
    """Validate every fixed RVA used by the existing, tested injection payload."""
    def read(fmt, offset):
        require(0 <= offset <= len(data) - struct.calcsize(fmt), 'Truncated PE file.')
        return struct.unpack_from(fmt, data, offset)

    require(data[:2] == b'MZ', 'Not a Windows PE DLL.')
    pe = read('<I', 0x3c)[0]
    require(data[pe:pe + 4] == b'PE\0\0', 'Invalid PE signature.')
    machine, count = read('<HH', pe + 4)
    size, flags = read('<HH', pe + 20)
    optional = pe + 24
    require(machine == 0x14c and flags & 0x2000 and size >= 224,
            'This patch requires an x86 PE32 DLL.')
    require(read('<H', optional)[0] == 0x10b, 'Not a PE32 image.')
    require(read('<I', optional + 28)[0] == 0x10000000, 'Unsupported image base.')
    require(read('<II', optional + 32) == (4096, 4096), 'Unsupported section/file alignment.')
    require(read('<I', optional + 56)[0] == 0x119000,
            'Unsupported image layout, or DLL already modified by another patch.')
    require(read('<I', optional + 92)[0] >= 6, 'Missing PE data directories.')
    require(read('<II', optional + 128) == (0, 0), 'Signed DLL requires separate handling.')
    table = optional + size
    header_size = read('<I', optional + 60)[0]
    require(1 <= count <= 32 and table + (count + 1) * 40 <= header_size <= len(data),
            'Invalid or full section header table.')
    sections = []
    names = set()
    for index in range(count):
        name, virtual_size, va, raw_size, raw = read('<8sIIII', table + index * 40)
        name = name.rstrip(b'\0')
        require(name not in names and name != b'.sgfix', 'Duplicate or already patched section.')
        names.add(name)
        extent = max(virtual_size, raw_size)
        require(va >= header_size and va % 4096 == 0 and va + extent <= 0x119000,
                'Unsupported section mapping.')
        require(raw_size == 0 or (raw >= header_size and raw % 4096 == 0 and raw + raw_size <= len(data)),
                'Invalid section file range.')
        for _, other_va, other_extent, other_raw, other_size in sections:
            require(va + extent <= other_va or other_va + other_extent <= va,
                    'Overlapping virtual sections.')
            if raw_size and other_size:
                require(raw + raw_size <= other_raw or other_raw + other_size <= raw,
                        'Overlapping file sections.')
        sections.append((name, va, extent, raw, raw_size))
    require(b'.text' in names, 'Missing code section.')

    def at(rva, length=1):
        for _, va, _, raw, raw_size in sections:
            if va <= rva and rva + length <= va + raw_size:
                return raw + rva - va
        raise PatchError('Required RVA is outside a file-backed section.')

    def cstring(rva):
        result = bytearray()
        for i in range(256):
            value = data[at(rva + i)]
            if value == 0:
                return bytes(result).lower()
            result.append(value)
        raise PatchError('Invalid PE import name.')

    # The payload resolves its functions through these exact import slots.
    imports = {}
    import_rva, import_size = read('<II', optional + 104)
    require(20 <= import_size <= 65536, 'Invalid import directory.')
    terminated = False
    for relative in range(0, import_size - 19, 20):
        lookup, timestamp, forwarder, name, iat = read('<IIIII', at(import_rva + relative, 20))
        if not any((lookup, timestamp, forwarder, name, iat)):
            terminated = True
            break
        module = cstring(name)
        require(lookup != 0, 'Original import name table is required.')
        for index in range(4096):
            entry = read('<I', at(lookup + 4 * index, 4))[0]
            if entry == 0:
                break
            at(iat + 4 * index, 4)
            if not entry & 0x80000000:
                imports[iat + 4 * index] = (module, cstring(entry + 2))
        else:
            raise PatchError('Unterminated import table.')
    require(terminated, 'Unterminated import directory.')
    for rva, expected in {
        0x113534: (b'kernel32.dll', b'getprocaddress'),
        0x113554: (b'kernel32.dll', b'getmodulehandlea'),
        0x113660: (b'opengl32.dll', b'glbegin'),
        0x113670: (b'opengl32.dll', b'glflush'),
    }.items():
        require(imports.get(rva) == expected, f'Unsupported import slot at {rva:#x}.')
    require(at(0x63e10, 40) == 0x63e10, 'Unsupported pixel format descriptor mapping.')
    descriptor = bytearray(data[0x63e10:0x63e38])
    require(descriptor[9] in (0, 16), 'Unsupported requested color depth.')
    descriptor[9] = 16
    require(descriptor == bytes.fromhex('28000100280000000010000000000000000000000000000000000000000000000000000000000000'),
            'Unsupported pixel format descriptor.')
    reloc_rva, reloc_size = read('<II', optional + 136)
    require(reloc_size >= 8, 'Missing relocations.')
    at(reloc_rva, reloc_size)


def build_patch(original, payload):
    """Patch compatible layouts while preserving unrelated bytes and overlays."""
    validate_layout(original)
    require(sha256(payload) == PAYLOAD_SHA256, 'Payload checksum mismatch. Re-download the release.')
    require(len(payload) == 3684, 'Unexpected payload size.')
    data = bytearray(original)

    def u16(offset):
        return struct.unpack_from('<H', data, offset)[0]

    def u32(offset):
        return struct.unpack_from('<I', data, offset)[0]

    pe = u32(0x3c)
    optional = pe + 24
    table = optional + u16(pe + 20)
    count = u16(pe + 6)
    sections = []
    for index in range(count):
        offset = table + index * 40
        sections.append((bytes(data[offset:offset + 8]).rstrip(b'\0'),
                         u32(offset + 12), u32(offset + 8),
                         u32(offset + 20), u32(offset + 16)))
    code = next(section for section in sections if section[0] == b'.text')

    def file_offset(rva):
        for _, va, _, raw, size in sections:
            if va <= rva < va + size:
                return raw + rva - va
        raise PatchError('Relocation points outside a file-backed section.')

    require(u32(optional + 56) == 0x119000, 'Unexpected original SizeOfImage.')
    removed = set()
    for iat, target, expected in [(0x10113670, 0x119000, 10),
                                  (0x10113660, 0x119015, 22)]:
        found = 0
        for opcode in (b'\xff\x15', b'\xff\x25'):
            needle = opcode + struct.pack('<I', iat)
            position = code[3]
            while True:
                at = data.find(needle, position, code[3] + code[4])
                if at < 0:
                    break
                rva = code[1] + at - code[3]
                instruction = b'\xe8' if opcode == b'\xff\x15' else b'\xe9'
                data[at:at + 6] = instruction + struct.pack('<i', target - rva - 5) + b'\x90'
                removed.add(rva + 2)
                found += 1
                position = at + 6
        require(found == expected, 'Unexpected number of OpenGL redirect sites.')

    reloc_rva = u32(optional + 96 + 5 * 8)
    reloc_size = u32(optional + 96 + 5 * 8 + 4)
    position = file_offset(reloc_rva)
    end = position + reloc_size
    seen = set()
    while position < end:
        require(position + 8 <= end, 'Truncated relocation block header.')
        page, size = struct.unpack_from('<II', data, position)
        require(size >= 8 and size % 2 == 0 and position + size <= end,
                'Invalid relocation block.')
        for offset in range(position + 8, position + size, 2):
            value = u16(offset)
            rva = page + (value & 0xfff)
            if value >> 12 == 3 and rva in removed:
                struct.pack_into('<H', data, offset, 0)
                seen.add(rva)
        position += size
    require(seen == removed, 'Could not neutralize every replaced absolute relocation.')

    require(data[0x63e19] in (0, 16), 'Unexpected pixel format descriptor.')
    data[0x63e19] = 0
    raw = (len(data) + 0xfff) & ~0xfff
    data.extend(bytes(raw - len(data)))
    data.extend(payload + bytes(0x1000 - len(payload)))
    header = table + count * 40
    require(header + 40 <= u32(optional + 60) and not any(data[header:header + 40]),
            'No room for the additional section header.')
    struct.pack_into('<8sIIIIIIHHI', data, header, b'.sgfix\0\0',
                     0x1000, 0x119000, 0x1000, raw, 0, 0, 0, 0, 0xe0000060)
    struct.pack_into('<H', data, pe + 6, count + 1)
    struct.pack_into('<I', data, optional + 56, 0x11a000)
    struct.pack_into('<I', data, optional + 4, u32(optional + 4) + 0x1000)
    struct.pack_into('<I', data, optional + 64, 0)
    if sha256(original) == ORIGINAL_SHA256:
        require(sha256(data) == PATCHED_SHA256, 'Regression: reference DLL output changed.')
    return bytes(data)


def target_path(argument):
    target = Path(argument).expanduser()
    if target.is_dir():
        matches = [entry for entry in target.iterdir() if entry.name.lower() == 'terrain.dll']
        require(len(matches) == 1, 'The game directory must contain exactly one Terrain.dll.')
        target = matches[0]
    require(not target.is_symlink(), 'Symlink DLLs are not supported; use a regular file.')
    require(target.is_file(), f'DLL not found: {target}')
    return target.absolute()


def backup_data(backup):
    require(not backup.is_symlink(), 'Refusing a symlink backup.')
    require(backup.is_file(), f'Original backup not found: {backup}')
    data = backup.read_bytes()
    return data


def state(current, backup, payload):
    if sha256(current) == PATCHED_SHA256:
        return 'patched'
    try:
        build_patch(current, payload)
        return 'original'
    except PatchError as original_error:
        if backup.exists() or backup.is_symlink():
            original = backup_data(backup)
            if build_patch(original, payload) == current:
                return 'patched'
        raise original_error


def replace_checked(target, before, after, mode):
    """Write next to the destination, then atomically replace its verified contents."""
    descriptor, temporary = tempfile.mkstemp(prefix='.simgolf-fix-', dir=target.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(after)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        require(not target.is_symlink() and target.read_bytes() == before,
                'DLL changed during the operation; no replacement performed.')
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def change_file(action, target):
    # A per-directory lock prevents two instances of this patcher from racing.
    lock = target.parent / '.simgolf-wine-fix.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise PatchError(f'Patcher lock exists: {lock}. Check for another patcher process.') from None
    try:
        os.close(descriptor)
        require(not target.is_symlink(), 'DLL became a symlink; refusing to continue.')
        current = target.read_bytes()
        backup = target.with_name(target.name + BACKUP_SUFFIX)
        payload = PAYLOAD.read_bytes()
        current_state = state(current, backup, payload)
        mode = stat.S_IMODE(target.stat().st_mode)
        if action == 'apply':
            if current_state == 'patched':
                print('Already patched. No files changed.')
                return
            patched = build_patch(current, payload)
            if backup.exists() or backup.is_symlink():
                require(backup_data(backup) == current, 'Existing backup differs from this original DLL.')
            else:
                # Exclusive creation never overwrites an existing user backup.
                with backup.open('xb') as stream:
                    stream.write(current)
                    stream.flush()
                    os.fsync(stream.fileno())
                    os.fchmod(stream.fileno(), mode)
            require(backup_data(backup) == current, 'Backup verification failed.')
            replace_checked(target, current, patched, mode)
            print(f'Installed SimGolf Wine Fix v{VERSION}.')
            print(f'Original backup: {backup}')
        else:
            if current_state == 'original':
                print('Already original. No files changed.')
                return
            original = backup_data(backup)
            require(build_patch(original, payload) == current,
                    'Backup does not reproduce the current patched DLL; refusing to overwrite it.')
            replace_checked(target, current, original, mode)
            print('Original Terrain.dll restored. Backup kept.')
    finally:
        lock.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('action', choices=('check', 'apply', 'restore'))
    parser.add_argument('target', help='Game directory or path to Terrain.dll; close the game before applying/restoring')
    args = parser.parse_args(argv)
    try:
        target = target_path(args.target)
        if args.action == 'check':
            current = target.read_bytes()
            fingerprint = sha256(current)
            backup = target.with_name(target.name + BACKUP_SUFFIX)
            current_state = state(current, backup, PAYLOAD.read_bytes())
            if current_state == 'original':
                print('Compatible Terrain.dll layout. Ready to apply; no fixed original hash required.')
            else:
                print(f'SimGolf Wine Fix v{VERSION} is installed.')
            print(f'SHA-256: {fingerprint}')
        else:
            change_file(args.action, target)
        return 0
    except (PatchError, OSError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
