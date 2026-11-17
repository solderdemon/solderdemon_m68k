"""Remove redundant wide power copper after the final r1 routing pass.

Rosco r2 uses 0.85 mm for the main VCC/GND connections. The r1 board also
acquired 2 mm overlays around J5 and five 1.6 mm VCC segments near C3. Their
original connections remain after removal; refill the zones before saving.
"""
from collections import Counter
from pathlib import Path

import pcbnew as pcb
import wx

wx.Log.EnableLogging(False)

BOARD = Path(__file__).resolve().parents[1] / 'design' / 'solderdemon_m68k.kicad_pcb'
EXPECTED = Counter({('GND', 2.0): 13, ('VCC', 2.0): 7,
                    ('VCC', 1.6): 5})


def wide_tracks(board):
    return [track for track in board.GetTracks()
            if track.Type() == pcb.PCB_TRACE_T and track.GetWidth() > pcb.FromMM(0.85)]


def main():
    board = pcb.LoadBoard(str(BOARD))
    tracks = wide_tracks(board)
    counts = Counter((track.GetNetname(), round(pcb.ToMM(track.GetWidth()), 3))
                     for track in tracks)
    unexpected = {key: count for key, count in counts.items()
                  if count != EXPECTED.get(key)}
    if unexpected:
        raise RuntimeError(f'unexpected wide traces: {unexpected}')
    if not tracks:
        print('Trace widths already restored')
        return
    for track in tracks:
        board.Remove(track)
    pcb.ZONE_FILLER(board).Fill(board.Zones())
    pcb.SaveBoard(str(BOARD), board)
    print(f'Removed {len(tracks)} redundant wide power traces; zones refilled')


if __name__ == '__main__':
    main()
