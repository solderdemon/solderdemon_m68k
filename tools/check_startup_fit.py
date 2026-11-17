"""Compare fitted CPLD equations with CUPL, including inverted buried registers.

Usage: python3 tools/check_startup_fit.py [directory containing .pld and bin/]
Checks the fitter report, not a JEDEC readback or electrical timing.
"""
from pathlib import Path
import random
import re
import sys

import cupl


def check(root, name, vectors=50000):
    dev = cupl.Device((root / f'{name}.pld').read_text())
    fit = (root / 'bin' / f'{name}.fit').read_text(encoding='latin-1')
    section = fit.split('programmed logic:')[1].split('Pin/Node Placement')[0]
    eq = {}
    for statement in section.split(';'):
        statement = re.sub(r'-{5,}', '', statement).strip()
        if '=' not in statement:
            continue
        lhs, rhs = map(str.strip, statement.split('=', 1))
        signal, _, ext = lhs.lstrip('!').partition('.')
        eq[signal, ext] = (lhs.startswith('!'), rhs)
    regs = {n for n, ext in eq if ext == 'D'}
    assert regs == set(dev.regs), (name, regs, dev.regs)
    # WinCUPL may complement a buried register and use AP instead of AR.
    inverted = {n for n in regs if (n, 'AP') in eq and (n, 'AR') not in eq}
    combs = {n for n, ext in eq if not ext}

    def compile_expr(negative, expression):
        tokens = re.findall(r'\w+(?:\.\w+)?|[!&#()]', expression)
        out = []
        for token in tokens:
            if token in ('0', '1', '(', ')'):
                out.append(token)
            elif token in ('!', '&', '#'):
                out.append({'!': ' not ', '&': ' and ', '#': ' or '}[token])
            else:
                n, _, ext = token.partition('.')
                source = 'q' if ext == 'Q' else 'p' if ext == 'PIN' else 'c' if n in combs else 'p'
                out.append(f'{source}[{n!r}]')
        code = ''.join(out).strip()
        return eval(f'lambda p,q,c: int({"not " if negative else ""}bool({code}))')

    fn = {key: compile_expr(*value) for key, value in eq.items() if key[1] != 'C'}

    def settle(p, q):
        c, todo = {}, set(combs)
        while todo:
            done = set()
            for n in todo:
                try:
                    c[n] = fn[n, ''](p, q, c)
                    done.add(n)
                except KeyError:
                    pass
            assert done, (name, 'unresolved fitted nodes', todo)
            todo -= done
        return c

    def async_state(p, q):
        c = settle(p, q)
        return {r: 0 if (r, 'AR') in fn and fn[r, 'AR'](p, q, c)
                else 1 if (r, 'AP') in fn and fn[r, 'AP'](p, q, c)
                else q[r] for r in regs}

    for r in regs:
        assert eq[r, 'C'][1].strip() == dev.clocks[r], (name, r, 'clock')
    wanted = {s: pin for pin, s in dev.pins.items()}
    actual = {s: int(pin) for s, pin in re.findall(r'^(\w+) (?:is placed at pin|assigned to pin)\s+(\d+)', fit, re.M)}
    assert all(actual.get(s) == pin for s, pin in wanted.items()), (name, 'pin placement')
    rng = random.Random(1)
    for i in range(vectors):
        p = {n: rng.getrandbits(1) for n in dev.pins.values()}
        logical = {r: rng.getrandbits(1) for r in dev.regs}
        physical = {r: logical[r] ^ (r in inverted) for r in regs}
        qa = async_state(p, physical)
        model_q = dict(logical)
        expected = dev.outputs(p, model_q)
        assert {r: qa[r] ^ (r in inverted) for r in regs} == model_q, (name, i, 'async reset')
        c = settle(p, qa)
        for n, value in expected.items():
            enabled = fn[n, 'OE'](p, qa, c) if (n, 'OE') in fn else 1
            got = (qa[n] if n in regs else c[n]) if enabled else None
            assert got == value, (name, i, n, got, value, p, logical)
        c = settle(p, physical)
        nxt = {r: fn[r, 'D'](p, physical, c) for r in regs}
        # Asynchronous controls override the sampled D value.
        for r in regs:
            if (r, 'AR') in fn and fn[r, 'AR'](p, physical, c):
                nxt[r] = 0
            elif (r, 'AP') in fn and fn[r, 'AP'](p, physical, c):
                nxt[r] = 1
        model_next = dev.clock_edge(p, logical, set(dev.clocks.values()))
        got_next = {r: nxt[r] ^ (r in inverted) for r in regs}
        assert got_next == model_next, (name, i, 'next state', got_next, model_next)
    print(f'{name}: {vectors} vectors; outputs, OE, next state, reset, clocks and pins agree; inverted={sorted(inverted)}')


if __name__ == '__main__':
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'code/firmware/pld/cpld'
    for name in ('ic2_decoder', 'ic3_glue'):
        check(root, name)
