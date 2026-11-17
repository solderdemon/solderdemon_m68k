"""Conservatively shorten selected r1 routes without rewriting footprint metadata.

Run with KiCad's Python after the board is fully routed. Each net is replanned by
KiCadRoutingTools on a copy, then only that net's copper is transplanted. A route
is accepted only if it is shorter, uses no more vias, and KiCad reports no new
DRC errors or unconnected pads. The original board is saved only at the end.
"""

from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

import pcbnew as pcb
import wx

wx.Log.EnableLogging(False)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cpld_board as cb
import cpld_route as cr
from check_board import check


NETS = ('D6', 'A18')
ROUTE_ARGS = ('--track-width', '0.1524', '--layers', 'F.Cu', 'B.Cu',
              '--clearance', '0.1524', '--via-size', '0.6', '--via-drill', '0.3',
              '--escalation', 'off', '--no-fix-drc-settings')


def measure(board, net):
    copper = [t for t in board.GetTracks() if t.GetNetname() == net]
    return (sum(pcb.ToMM(t.GetLength()) for t in copper if t.Type() == pcb.PCB_TRACE_T),
            sum(t.Type() == pcb.PCB_VIA_T for t in copper))


def copy_net(board, candidate, net, grave):
    old = [t for t in board.GetTracks() if t.GetNetname() == net]
    new = [t for t in candidate.GetTracks() if t.GetNetname() == net]
    if not new:
        raise RuntimeError(f'{net}: router returned no copper')
    for t in old:
        board.Remove(t)
    grave.extend(old)  # KiCad 10 SWIG must retain removed objects until exit.
    board_net = board.FindNet(net)
    for t in new:
        clone = t.Duplicate()
        clone.SetNet(board_net)
        board.Add(clone)


def clean(board_path, baseline_errors):
    report = check(board_path)
    errors = [v for v in report['violations'] if v['severity'] == 'error']
    if len(errors) > baseline_errors or report['unconnected_items']:
        raise RuntimeError(f'DRC: {len(errors)} errors, '
                           f"{len(report['unconnected_items'])} unconnected")
    return len(errors)


def main():
    original_pro = cb.BOARD.with_suffix('.kicad_pro').read_bytes()
    baseline = check(cb.BOARD)
    baseline_errors = sum(v['severity'] == 'error' for v in baseline['violations'])
    if baseline_errors or baseline['unconnected_items']:
        raise RuntimeError('start board must have 0 DRC errors and 0 unconnected pads')

    with tempfile.TemporaryDirectory(prefix='r1-route-opt-', dir=cb.KICAD) as tmp:
        work = Path(tmp)
        current = work / 'current.kicad_pcb'
        shutil.copy2(cb.BOARD, current)
        current.with_suffix('.kicad_pro').write_bytes(original_pro)
        grave = []
        accepted = []
        for net in NETS:
            out = work / f'{net}.kicad_pcb'
            cmd = [str(cr.KRT_PY), str(cr.KRT / 'py_router' / 'route.py'),
                   str(current.resolve()), str(out.resolve()), '--nets', net,
                   '--force-reroute', *ROUTE_ARGS]
            env = dict(os.environ, KICAD_RIP_PREEXISTING='0')
            result = subprocess.run(cmd, cwd=cr.KRT, env=env, capture_output=True, text=True)
            if result.returncode or not out.exists():
                raise RuntimeError(f'{net}: router failed ({result.returncode})\n'
                                   f'{result.stdout[-2500:]}\n{result.stderr[-1000:]}')
            board = pcb.LoadBoard(str(current))
            candidate = pcb.LoadBoard(str(out))
            before, after = measure(board, net), measure(candidate, net)
            print(f'{net}: {before[0]:.1f} mm/{before[1]} vias -> '
                  f'{after[0]:.1f} mm/{after[1]} vias', flush=True)
            if after[0] >= before[0] or after[1] > before[1]:
                print(f'{net}: rejected (length or vias)', flush=True)
                continue
            copy_net(board, candidate, net, grave)
            pcb.ZONE_FILLER(board).Fill(board.Zones())
            proposed = work / 'proposed.kicad_pcb'
            pcb.SaveBoard(str(proposed), board)
            proposed.with_suffix('.kicad_pro').write_bytes(original_pro)
            clean(proposed, baseline_errors)
            shutil.copy2(proposed, current)
            current.with_suffix('.kicad_pro').write_bytes(original_pro)
            accepted.append(net)
            print(f'{net}: accepted', flush=True)

        if accepted:
            shutil.copy2(current, cb.BOARD)
            cb.BOARD.with_suffix('.kicad_pro').write_bytes(original_pro)
        print(f"Accepted: {', '.join(accepted) or 'none'}", flush=True)


if __name__ == '__main__':
    main()
