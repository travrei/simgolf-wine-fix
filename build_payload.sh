#!/usr/bin/env bash
# Rebuild for inspection. The tested release payload is never overwritten.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$root/build"
gcc -m32 -Os -ffreestanding -fPIC -fno-stack-protector \
    -fno-asynchronous-unwind-tables -fno-unwind-tables -fno-builtin \
    -fcf-protection=none -c "$root/src/hook.c" -o "$root/build/hook.o"
gcc -m32 -c "$root/src/entry.S" -o "$root/build/entry.o"
ld -m elf_i386 -T "$root/src/link.ld" -o "$root/build/hook.elf" \
    "$root/build/entry.o" "$root/build/hook.o"
objcopy -O binary -j .payload "$root/build/hook.elf" "$root/build/hook.bin"
gcc -O2 -Wall -Wextra -I "$root/src" "$root/tests/test_convert.c" -o "$root/build/test_convert"
"$root/build/test_convert"
python3 - "$root" <<'PY'
from pathlib import Path
import subprocess
import sys
root = Path(sys.argv[1])
symbols = subprocess.check_output(['nm', '-n', str(root / 'build/hook.elf')], text=True)
parsed = [line.split() for line in symbols.splitlines() if len(line.split()) == 3]
entries = {row[2]: int(row[0], 16) for row in parsed}
if entries.get('entry') != 0 or entries.get('begin_entry') != 0x15:
    raise SystemExit('ERROR: entry offsets changed; this payload cannot use the release patcher.')
if subprocess.check_output(['nm', '-u', str(root / 'build/hook.elf')]).strip():
    raise SystemExit('ERROR: unresolved symbols in payload.')
# linker script checks code/data/BSS fit; linked image must need no relocation.
relocations = subprocess.check_output(['objdump', '-r', str(root / 'build/hook.elf')], text=True)
if 'RELOCATION RECORDS' in relocations:
    raise SystemExit('ERROR: unexpected payload relocation records.')
built = (root / 'build/hook.bin').read_bytes()
shipped = (root / 'payload/hook.bin').read_bytes()
if built == shipped:
    print('PASS: rebuilt payload exactly matches the tested release.')
else:
    print('NOTE: compiler output differs. Shipped payload preserved; release patcher accepts only its pinned hash.')
print('Build artifacts: build/')
PY
