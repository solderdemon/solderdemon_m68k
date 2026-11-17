"""Regression checks for production IC2's address-based reset ROM handoff.

These are zero-delay logic checks, not a measurement of AS signal integrity.
Run from anywhere: python3 tools/verify_boot_handoff.py
"""
from pathlib import Path

import cupl


SOURCE = Path(__file__).resolve().parents[1] / 'code/firmware/pld/cpld/ic2_decoder.pld'


def inputs(dev, address=0, **overrides):
    p = {n: 0 for n in dev.pins.values()}
    p.update(HALT=1, RESET=1, AS=0, RW=1, LGEXP=1, FC2=1, FC0=1)
    for bit in (19, 20, 21, 22, 23):
        p[f'A{bit}'] = address >> bit & 1
    p.update(overrides)
    return p


def expect_memory(dev, p, q, rom):
    o = dev.outputs(p, q)
    for strobe, suffix in [('UDS', 'EVEN'), ('LDS', 'ODD')]:
        selected = not p[strobe]
        assert o[suffix + 'ROMSEL'] == int(not (rom and selected)), (p, q, o)
        assert o[suffix + 'RAMSEL'] == int(not (not rom and selected)), (p, q, o)
    return o


def main():
    dev = cupl.Device(SOURCE.read_text())
    assert dev.regs == ['BOOT'], dev.regs
    cases = 0
    for initial in (0, 1):
        for extra in range(65):
            q = {'BOOT': initial}
            dev.outputs(inputs(dev, HALT=0, RESET=0, HWRST=1), q)
            assert q['BOOT'] == 0
            # Each 32-bit reset vector is two word transfers. Additional low-address
            # AS edges must never replace a vector word with uninitialized RAM.
            for address in (0, 2, 4, 6):
                p = inputs(dev, address)
                for _ in range(extra + 1):
                    expect_memory(dev, p, q, rom=True)
                    q = dev.clock_edge(p, q, {'AS'})
                    assert q['BOOT'] == 0
                    cases += 1
            # The first instruction is fetched at the reset PC in high ROM.
            for address in (0xE00000, 0xE00404, 0xEFFFFE):
                state = dict(q)
                p = inputs(dev, address)
                assert dev.outputs(p, state)['EVENROMSEL'] == 0
                state = dev.clock_edge(p, state, {'AS'})
                assert state['BOOT'] == 1
                for uds, lds in ((0, 0), (0, 1), (1, 0)):
                    p = inputs(dev, UDS=uds, LDS=lds)
                    expect_memory(dev, p, state, rom=False)
                    assert dev.clock_edge(p, state, {'AS'})['BOOT'] == 1
                # RESET alone (CPU RESET instruction) must not remap low RAM.
                dev.outputs(inputs(dev, RESET=0), state)
                assert state['BOOT'] == 1
                # External reset asserts both signals and re-arms the overlay.
                dev.outputs(inputs(dev, RESET=0, HALT=0), state)
                assert state['BOOT'] == 0
    for address in (0, 0x100000, 0xDFFFFE, 0xF00000):
        p = inputs(dev, address)
        assert dev.clock_edge(p, {'BOOT': 0}, {'AS'})['BOOT'] == 0
    for overrides in ({'RW': 0}, {'FC0': 1, 'FC1': 1, 'FC2': 1}):
        # E80000 sets A19, so FC=111 is an actual IACK in this decoder.
        p = inputs(dev, 0xE80000, **overrides)
        assert dev.clock_edge(p, {'BOOT': 0}, {'AS'})['BOOT'] == 0
    p = inputs(dev, 0xE00404)
    assert dev.clock_edge(p, {'BOOT': 0}, set())['BOOT'] == 0
    print(f'BOOT handoff PASS: {cases} low-vector cycles, reset from both states, '
          'high-ROM handoff, byte lanes, sticky BOOT, write/IACK exclusions.')


if __name__ == '__main__':
    main()
