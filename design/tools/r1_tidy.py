"""Tidy the r1 silkscreen and the small parts around the LEDs and the jumper block.

Run after ceramic_decouplers.py; reconnect the displaced copper with cpld_route.py afterwards.

  1. C6 and C32 stand upright (VCC pad up) on the LED centre line, each 6.85 mm from the
     nearest LED: C32 halfway between LED1 and LED2, C6 the same distance left of LED1.
  2. C17, the "Jumper Settings" frame and C8 share one centre line, halfway between the
     bottom of the CPU's pin row and the top of the ROM frames, with equal gaps between
     the three; the frame is widened so its caption clears the jumpers.
  3. Every 0207 resistor carries its reference centred inside the body outline.
  4. The revision is a copper mark, as on SolderDemon 6502: "r1" in 2.5 mm copper under the
     mask in the top left corner, between the mounting hole and C30. The silkscreen
     "Revision r1" goes, and the copyright line takes its place, centred above the CPU.
"""
from pathlib import Path
import sys

import pcbnew as pcb
import wx

wx.Log.EnableLogging(False)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cpld_board as cb

mm, at = pcb.ToMM, cb.at_mm
FRAME_W, FRAME_H, GAP = 18.9, 7.17, 1.45          # jumper frame, gap to C17 / C8 (mm)


def bbox(fp):
    """Body and pads, no text."""
    return fp.GetBoundingBox(False, False)


def silk_top(fp):
    """Top edge of the footprint's own silkscreen (the ROM/RAM frames)."""
    return min(mm(g.GetBoundingBox().GetY()) for g in fp.GraphicalItems() if g.GetLayer() == pcb.F_SilkS)


def move(fp, x, y, rot=None):
    if rot is not None:
        fp.SetOrientationDegrees(rot)
    fp.SetPosition(at(x, y))


def leds(b):
    led1, led2 = cb.find(b, 'LED1'), cb.find(b, 'LED2')
    y = (mm(led1.GetPosition().y) + mm(led2.GetPosition().y)) / 2
    assert abs(mm(led1.GetPosition().y) - mm(led2.GetPosition().y)) < 0.01, 'LED1 and LED2 are not on one line'
    x1, x2 = mm(led1.GetPosition().x), mm(led2.GetPosition().x)
    half = (x2 - x1) / 2
    for ref, x in (('C32', x1 + half), ('C6', x1 - half)):
        fp = cb.find(b, ref)
        move(fp, x, y, -90)                       # pad 1 (VCC) up, like a radial cap in a row
        assert next(p for p in fp.Pads() if p.GetNumber() == '1').GetPosition().y < fp.GetPosition().y
        center_reference(fp, 0.85, 0.12)
        print(f'{ref}: ({x:.3f}, {y:.3f}) upright')
    return [cb.find(b, 'C6'), cb.find(b, 'C32')]


def jumper_block(b):
    ic1, u1, u2 = cb.find(b, 'IC1'), cb.find(b, 'U1'), cb.find(b, 'U2')
    top = mm(bbox(ic1).GetBottom())
    bottom = min(silk_top(u) for u in (u1, u2))
    cy = (top + bottom) / 2
    c17, c8, jp3, jp4 = (cb.find(b, r) for r in ('C17', 'C8', 'JP3', 'JP4'))
    frame = [d for d in b.GetDrawings() if d.GetLayer() == pcb.F_SilkS and d.GetClass() == 'PCB_SHAPE'
             and d.GetShapeStr() == 'Line' and 90 < mm(d.GetStart().x) < 113 and 86 < mm(d.GetStart().y) < 104]
    assert len(frame) == 4, f'expected the 4 lines of the jumper frame, found {len(frame)}'
    heading = [d for d in b.GetDrawings() if isinstance(d, pcb.PCB_TEXT) and d.GetText().strip() == 'Jumper Settings']
    caption = [d for d in b.GetDrawings() if isinstance(d, pcb.PCB_TEXT) and d.GetText().strip() == 'See\nDocumentation']
    assert len(heading) == 1 and len(caption) == 1
    heading, caption = heading[0], caption[0]

    # C17 keeps its column; the frame and C8 follow with equal gaps
    x17 = mm(c17.GetPosition().x)
    move(c17, x17, cy)
    left = mm(bbox(c17).GetRight()) + GAP
    right = left + FRAME_W
    fy0, fy1 = cy - FRAME_H / 2, cy + FRAME_H / 2
    for line, (p, q) in zip(frame, (((left, fy0), (left, fy1)), ((left, fy1), (right, fy1)),
                                    ((right, fy1), (right, fy0)), ((right, fy0), (left, fy0)))):
        line.SetStart(at(*p))
        line.SetEnd(at(*q))
    # jumpers at the right of the frame, their references above the pins as before
    jy = cy + 0.89
    w4 = mm(bbox(jp4).GetWidth()) / 2
    x4 = right - 0.6 - w4
    x3 = x4 - 4.318
    move(jp4, x4, jy)
    move(jp3, x3, jy)
    tx = (left + mm(bbox(jp3).GetX())) / 2
    heading.SetPosition(at(tx, cy - 1.32))
    caption.SetPosition(at(tx, cy + 1.27))
    c8.SetOrientationDegrees(-90)
    c8.SetPosition(at(0, 0))
    x8 = right + GAP + (mm(c8.GetPosition().x) - mm(bbox(c8).GetX()))
    move(c8, x8, cy)
    center_reference(c8, 0.85, 0.12)
    print(f'jumper block: centre line y={cy:.3f} (CPU pins {top:.2f} .. ROM frames {bottom:.2f}), '
          f'C17 x={x17:.2f}, frame x={left:.2f}..{right:.2f}, C8 x={x8:.2f}')
    return [c17, c8, jp3, jp4]


def center_reference(fp, height, thickness):
    r = fp.Reference()
    r.SetPosition(fp.GetPosition())
    rot = fp.GetOrientationDegrees() % 180
    r.SetTextAngleDegrees(90 if 45 < rot < 135 else 0)
    r.SetTextSize(pcb.VECTOR2I(pcb.FromMM(height), pcb.FromMM(height)))
    r.SetTextThickness(pcb.FromMM(thickness))
    r.SetHorizJustify(pcb.GR_TEXT_H_ALIGN_CENTER)
    r.SetVertJustify(pcb.GR_TEXT_V_ALIGN_CENTER)
    r.SetVisible(True)


def resistors(b):
    n = 0
    for fp in b.GetFootprints():
        if '0207' in fp.GetFPIDAsString():
            center_reference(fp, 1.2, 0.15)
            n += 1
    print(f'{n} resistor references centred')


REVISION = 'r1'
REVISION_AT = (80.0, 57.8)                        # top left corner, clear of H2, C30 and the FC0 track


def revision_mark(b):
    gone = [d for d in b.GetDrawings() if isinstance(d, pcb.PCB_TEXT)
            and d.GetText().strip() == f'Revision {REVISION}']
    for d in gone:
        cb.remove(b, d)
    ic1 = cb.find(b, 'IC1')
    for d in b.GetDrawings():
        if isinstance(d, pcb.PCB_TEXT) and d.GetText().startswith('Copyright'):
            d.SetHorizJustify(pcb.GR_TEXT_H_ALIGN_CENTER)
            d.SetPosition(pcb.VECTOR2I(ic1.GetPosition().x, d.GetPosition().y))
    if not any(isinstance(d, pcb.PCB_TEXT) and d.IsOnCopperLayer() and d.GetText() == REVISION
               for d in b.GetDrawings()):
        t = pcb.PCB_TEXT(b)
        t.SetText(REVISION)
        t.SetLayer(pcb.F_Cu)
        t.SetTextSize(pcb.VECTOR2I(pcb.FromMM(2.5), pcb.FromMM(2.5)))
        t.SetTextThickness(pcb.FromMM(0.6))
        t.SetHorizJustify(pcb.GR_TEXT_H_ALIGN_CENTER)
        t.SetVertJustify(pcb.GR_TEXT_V_ALIGN_CENTER)
        t.SetPosition(at(*REVISION_AT))
        b.Add(t)
    print(f'revision mark: copper "{REVISION}" at {REVISION_AT}; {len(gone)} silkscreen revision texts removed')


def main():
    b = pcb.LoadBoard(str(cb.BOARD))
    before = {fp.GetReference(): (fp.GetPosition(), fp.GetOrientationDegrees()) for fp in b.GetFootprints()}
    touched = leds(b) + jumper_block(b)
    resistors(b)
    revision_mark(b)
    # Only a part that actually moved may tear copper up: rip_collisions asks 0.2 mm around a
    # pad, the router lays tracks at 0.1524, so a second run would otherwise rip routed tracks.
    moved = [fp for fp in touched if before[fp.GetReference()] != (fp.GetPosition(), fp.GetOrientationDegrees())]
    nets, count = cb.rip_collisions(b, moved)
    pcb.ZONE_FILLER(b).Fill(b.Zones())
    cb.save(b)
    b.BuildConnectivity()
    print(f'removed {count} colliding tracks/vias on {len(nets)} nets; '
          f'unconnected before rerouting: {b.GetConnectivity().GetUnconnectedCount(True)}')


if __name__ == '__main__':
    main()
