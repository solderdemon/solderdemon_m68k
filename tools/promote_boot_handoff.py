"""Promote the hardware-tested boot handoff; preserve the old counter for rollback.

Generated documentation is updated here, not by hand. Build and run the gates
after this script; it does not program hardware or claim fresh test results.
"""
from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[1]
CPLD = ROOT / 'code/firmware/pld/cpld'


def replace(path, before, after):
    text = path.read_text()
    if after in text:
        return
    assert before in text, (path, before)
    path.write_text(text.replace(before, after, 1))


def main():
    legacy = CPLD / 'diagnostics/legacy_as_counter'
    if not legacy.exists():
        legacy.mkdir()
        for name in ('ic2_decoder.pld', 'ic3_glue.pld'):
            shutil.copyfile(CPLD / name, legacy / name)
        (legacy / 'bin').mkdir()
        for name in ('ic2_decoder.jed', 'ic2_decoder.fit', 'ic3_glue.jed', 'ic3_glue.fit'):
            shutil.copyfile(CPLD / 'bin' / name, legacy / 'bin' / name)
    (legacy / 'README.md').write_text('''# Legacy AS-counter CPLD firmware

Archived before promoting the address-based ROM handoff on 2026-11-17.
IC2 removes the reset-vector ROM after four AS rising edges. The assembled
board showed intermittent cold-start and reset failures with this image.
Retained for rollback and reproducing the diagnostic comparison, not the
recommended production firmware. IC3 is the unchanged production glue image.
''')
    candidate = (CPLD / 'diagnostics/boot_handoff/ic2_decoder.pld').read_text()
    candidate = candidate.replace('Date     2026-09-27;', 'Date     2026-11-17;')
    candidate = candidate.replace('Revision r2.14;', 'Revision r1.1;')
    header = '''/*
 * SolderDemon m68k r1, IC2 production firmware r1.1.
 * Address decoder, DTACK, WR, interrupt-acknowledge decode and reset ROM overlay.
 *
 * At external RESET+HALT, BOOT clears and ROM supplies the vectors at address 0.
 * The first normal read in $E00000-$EFFFFF sets BOOT at the rising edge of AS.
 * Subsequent low-memory accesses select RAM. BOOT remains set until the next
 * external RESET+HALT; a CPU RESET instruction alone does not change the map.
 * The reset PC must point into high ROM, as the existing rosco ROM linker does.
 * No AS-edge counter is used during vector reads.
 *
 * Normal map: RAM $000000-$0FFFFF; expansion $100000-$DFFFFF;
 * ROM $E00000-$EFFFFF; IO $F00000-$FFFFFF. Levels and physical pins are unchanged.
 * DTACK is open drain. RESET and HALT are inputs here, driven by IC3 and CPU.
 * PIN declarations are the source of truth for PCB and schematic generators.
 * JTAG remains enabled, chained TDI -> IC2 -> IC3 -> TDO on header J9.
 */'''
    candidate = re.sub(r'/\*.*?\*/', lambda _: header, candidate, count=1, flags=re.S)
    candidate = candidate.replace('/* GCLK1: the boot counter counts bus cycles */',
                                  '/* GCLK1: latch high-ROM handoff at cycle end */')
    candidate = candidate.replace('/* Diagnostic experiment: keep the ROM overlay throughout reset-vector',
                                  '/* Keep the ROM overlay throughout reset-vector')
    (CPLD / 'ic2_decoder.pld').write_text(candidate)
    replace(CPLD / 'README.md', '# rosco_m68k classic THT r2.14 glue logic: two ATF1502AS',
            '# SolderDemon m68k CPLD firmware: two ATF1502AS')
    replace(CPLD / 'README.md',
            'The equations are those of the r2.13 GALs, unchanged, and every board net keeps its name and\n'
            'level. BOOT and ANYIACK, which ran between the GALs, are internal to IC2 now (ANYIACK is decoded\n'
            'in IC3 as well, for the watchdog and DUART IACK), so no wire runs between IC2 and IC3. IC2 uses\n'
            '24 pins and 16 macrocells, IC3 31 pins and 21 macrocells.',
            '''IC2 production firmware **r1.1 (2026-11-17)** keeps the reset-vector ROM overlay until
the first normal read in **0xE00000-0xEFFFFF**, then selects RAM at low addresses.
It replaces the previous four-AS-edge boot counter. The reset PC must point into
high ROM, as the existing rosco firmware does. Both RESET and HALT clear BOOT;
a CPU RESET instruction alone does not remap RAM.

The assembled board's owner reported stable startup and reset with this handoff
after intermittent failures with the counter. Extra AS edges can reproduce early
RAM selection in the model; their physical presence has not been measured.
The unsuccessful reset_guard watchdog experiment is not part of production IC3.

The normal memory map, signal levels and physical pin assignments are unchanged.
BOOT and ANYIACK are internal to IC2; ANYIACK is also decoded in IC3. IC2 uses
24 pins and 14 macrocells, IC3 31 pins and 21 macrocells.
Use **bin/ic2_decoder.jed -> IC2** and **bin/ic3_glue.jed -> IC3** for production.
Historical counter images remain under diagnostics/legacy_as_counter/ for rollback.''')
    replace(CPLD / 'README.md',
            'python tools/verify_cpld.py [steps] [seed]',
            'python3 tools/verify_boot_handoff.py\npython3 tools/verify_cpld.py [steps] [seed]\npython3 tools/check_startup_fit.py')
    replace(CPLD / 'README.md',
            'runs the r2.13 GALs from their real JEDEC fuse maps (`../address_decoder`, `../duartsel`,\n'
            '`../glue`, `../watchdog`) and the r2.14 CPLDs from these sources side by side on random bus\n'
            'traffic and fails on the first net that differs -- all 14 driven nets, the open-drain ones\n'
            'resolved as wired-AND with the CPU pulling RESET/HALT as well. The stimulus makes the boot latch\n'
            'set and the watchdog fire, and the run fails if either never happens.',
            '''Run these commands from the mainboard directory. The first checks vector reads with
extra AS edges, high-ROM handoff, reset, byte lanes and write/IACK exclusions.
The second compares all 14 driven nets against real r2.13 GAL fuse maps, with
only their old BOOT counter output replaced by an independent Python reference
for the new handoff. It requires BOOT and BERR activity and exercises wired-AND
RESET/HALT/DTACK/BERR. This intentionally is not full legacy-counter equivalence.
The third checks the actual fitter equations, enables, next states, asynchronous
controls, clock assignments and pin placement against the CUPL sources.
The build script gates on the handoff and fitter checks after compiling.
These are zero-delay logic checks; they do not measure physical timing.''')
    replace(ROOT / 'docs/MEMORY-MAP.md',
            'After the startup cycles, RAM occupies `0x000000`–`0x0FFFFF`.',
            'IC2 firmware r1.1 ends this overlay after the first normal read in `0xE00000`–`0xEFFFFF`; '
            'RAM then occupies `0x000000`–`0x0FFFFF`. The reset PC must point into that high-ROM region. '
            'Simultaneous RESET and HALT re-arm the overlay; RESET alone does not.')
    replace(ROOT / 'code/firmware/pld/README.md',
            'boards and as the reference `tools/verify_cpld.py` checks the CPLDs against:',
            'boards and as the decode/glue reference for `tools/verify_cpld.py`. '
            'The reference replaces the historical BOOT counter output with the current address-based handoff:')
    replace(ROOT / 'design/README.md',
            'python tools/verify_cpld.py        # 2. CPLDs against the r2.13 GAL fuse maps',
            'python3 tools/verify_cpld.py       # 2. GAL decode/glue + address-based BOOT reference')
    replace(ROOT / 'README.md',
            'r1 is the next release and is not made yet. KiCad renders of it, top and bottom:',
            'r1 is the current through-hole prototype. KiCad renders of it, top and bottom:')
    replace(ROOT / 'README.md',
            'What changed from rosco r2.42 is in the [design notes](design/README.md).',
            'What changed from rosco r2.42 is in the [design notes](design/README.md).\n\n'
            'Production [CPLD firmware](code/firmware/pld/cpld/README.md) uses the r1.1 address-based ROM handoff '
            'for reliable startup. Use `code/firmware/pld/cpld/bin/ic2_decoder.jed` for IC2 and '
            '`code/firmware/pld/cpld/bin/ic3_glue.jed` for IC3; the ROM Flash image is unchanged.')
    replace(CPLD / 'README.md',
            'These are zero-delay logic checks; they do not measure physical timing.',
            'These are zero-delay logic checks; they do not measure physical timing.\n\n'
            'After validation, run `python3 tools/package_cpld.py` from the mainboard '
            'directory. It checks both fuse maps against the hardware-tested identities and '
            'writes [the production ZIP](release/solderdemon_m68k-cpld-r1.1.zip), '
            'with programming images, sources, fitter reports and SHA-256 checksums.')
    print('Promoted IC2 source and regenerated CPLD/startup documentation; legacy images preserved.')


if __name__ == '__main__':
    main()
