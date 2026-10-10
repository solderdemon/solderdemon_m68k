"""Replace the 23 r1 100 nF decouplers with 5.08 mm radial ceramic footprints.

Run after the existing r1 layout/routing pipeline. The VCC pad starts at its old
position; placement may shift it to leave visible space around neighbouring parts.
The existing board is then routed again with cpld_route.py. C13 is a
100 nF capacitor on the 555 control-voltage pin, not a supply decoupler.
"""
from pathlib import Path
import sys

import pcbnew as pcb
import wx

wx.Log.EnableLogging(False)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cpld_board as cb

OLD = 'rosco_m68k:C2.5-3'
NEW = 'rosco_m68k:C_Radial_5.08mm'
BODY_GAP = pcb.FromMM(0.5)
# Keep the two crowded end capacitors on the same centre lines as their rows.
ALIGN = {'C28': (207.44, 102.60, 0), 'C31': (175.30, 82.81, 90)}


def replace(b, old):
    ref = old.GetReference()
    old_pads = {p.GetNumber(): p for p in old.Pads()}
    assert set(old_pads) == {'1', '2'}, ref
    assert {p.GetNetname() for p in old_pads.values()} & {'VCC'}, ref

    new = cb.footprint(ref, NEW, old.GetValue())
    new.SetPath(old.GetPath())
    new.SetOrientationDegrees(old.GetOrientationDegrees())
    new.SetPosition(old.GetPosition())
    anchor = next(n for n, p in old_pads.items() if p.GetNetname() == 'VCC')
    new.SetPosition(new.GetPosition() + old_pads[anchor].GetPosition() -
                    next(p for p in new.Pads() if p.GetNumber() == anchor).GetPosition())
    for pad in new.Pads():
        source = old_pads[pad.GetNumber()]
        pad.SetNet(source.GetNet())
        pad.SetPinFunction(source.GetPinFunction())
        pad.SetPinType(source.GetPinType())
        pad.SetLocalZoneConnection(source.GetLocalZoneConnection())
    for source, target in ((old.Reference(), new.Reference()), (old.Value(), new.Value())):
        target.SetPosition(source.GetPosition())
        target.SetTextAngleDegrees(source.GetTextAngleDegrees())
        target.SetTextSize(source.GetTextSize())
        target.SetTextThickness(source.GetTextThickness())
        target.SetLayer(source.GetLayer())
        target.SetVisible(source.IsVisible())
    b.Add(new)
    cb.remove(b, old)
    return new


def place_without_overlaps(b, caps):
    """Search around each old VCC pad, keeping visible space around each body."""
    movable = {f.GetReference() for f in caps}
    fixed = [f for f in b.GetFootprints() if f.GetReference() not in movable]
    boxes = []
    for f in fixed:
        box = f.GetCourtyard(pcb.F_CrtYd).BBox()
        # Imported rosco footprints such as the 68010 have no courtyard. Their
        # own geometry still occupies board space and must constrain placement.
        if box.GetWidth() == 0:
            box = f.GetBoundingBox(False, False)
        boxes.append((box, f.GetPosition()))
    pads = [(p, p.GetPosition()) for f in fixed for p in f.Pads()]
    edge = b.GetBoardEdgesBoundingBox()
    offsets = [0] + [v for n in range(1, 11) for v in (-n * 0.5, n * 0.5)]
    # Crowded groups are solved first; the remaining parts have more freedom.
    priority = ['C20', 'C12', 'C29', 'C31', 'C3', 'C9', 'C7', 'C32', 'C13',
                'C4', 'C5', 'C28']
    caps.sort(key=lambda f: (priority.index(f.GetReference()) if f.GetReference() in priority
                             else len(priority), f.GetReference()))
    for fp in caps:
        vcc = next(p for p in fp.Pads() if p.GetNetname() == 'VCC')
        anchor = vcc.GetPosition()
        original_angle = fp.GetOrientationDegrees()
        near_boxes = [box for box, _ in boxes if box.GetWidth() > 0
                      and box.GetX() <= anchor.x + pcb.FromMM(15)
                      and box.GetX() + box.GetWidth() >= anchor.x - pcb.FromMM(15)
                      and box.GetY() <= anchor.y + pcb.FromMM(15)
                      and box.GetY() + box.GetHeight() >= anchor.y - pcb.FromMM(15)]
        near_pads = [p for p, pos in pads
                     if abs(pos.x - anchor.x) < pcb.FromMM(12)
                     and abs(pos.y - anchor.y) < pcb.FromMM(12)]
        candidates = []
        for dx in offsets:
            for dy in offsets:
                dist2 = dx * dx + dy * dy
                if dist2 > 25:
                    continue
                for turn in (0, 180, 90, 270):
                    angle = (original_angle + turn) % 360
                    candidates.append((dist2 * 10 + (turn != 0) * 3 + (turn in (90, 270)) * 3,
                                       dx, dy, angle))
        chosen = None
        for _, dx, dy, angle in sorted(candidates):
            fp.SetOrientationDegrees(angle)
            fp.SetPosition(fp.GetPosition() + anchor + pcb.VECTOR2I(pcb.FromMM(dx), pcb.FromMM(dy))
                           - vcc.GetPosition())
            box = fp.GetCourtyard(pcb.F_CrtYd).BBox()
            if (box.GetX() < edge.GetX() + BODY_GAP or
                box.GetY() < edge.GetY() + BODY_GAP or
                box.GetX() + box.GetWidth() > edge.GetX() + edge.GetWidth() - BODY_GAP or
                box.GetY() + box.GetHeight() > edge.GetY() + edge.GetHeight() - BODY_GAP):
                continue
            if any(box.GetX() < other.GetX() + other.GetWidth() + BODY_GAP and
                   other.GetX() < box.GetX() + box.GetWidth() + BODY_GAP and
                   box.GetY() < other.GetY() + other.GetHeight() + BODY_GAP and
                   other.GetY() < box.GetY() + box.GetHeight() + BODY_GAP
                   for other in near_boxes):
                continue
            # Leave room for the 0.25 mm solder-mask web as well as copper clearance.
            if any(p.GetEffectiveShape(pcb.F_Cu).Collide(q.GetEffectiveShape(pcb.F_Cu), pcb.FromMM(0.6))
                   for p in fp.Pads() for q in near_pads if p.GetNetname() != q.GetNetname()
                   and abs(p.GetPosition().x - q.GetPosition().x) < pcb.FromMM(3)
                   and abs(p.GetPosition().y - q.GetPosition().y) < pcb.FromMM(3)):
                continue
            chosen = (dx, dy, angle)
            break
        if chosen is None:
            raise RuntimeError(f'no clear position within 5 mm for {fp.GetReference()}')
        dx, dy, angle = chosen
        boxes.append((fp.GetCourtyard(pcb.F_CrtYd).BBox(), fp.GetPosition()))
        pads.extend((p, p.GetPosition()) for p in fp.Pads())
        if dx or dy or angle != original_angle:
            print(f'{fp.GetReference()}: VCC pad offset ({dx:+.1f}, {dy:+.1f}) mm, rotation {angle:g} deg')


def center_reference(fp):
    ref = fp.Reference()
    ref.SetPosition(fp.GetPosition())
    ref.SetTextAngleDegrees(fp.GetOrientationDegrees())
    ref.SetTextSize(pcb.VECTOR2I(pcb.FromMM(0.85), pcb.FromMM(0.85)))
    ref.SetTextThickness(pcb.FromMM(0.12))
    ref.SetHorizJustify(pcb.GR_TEXT_H_ALIGN_CENTER)
    ref.SetVertJustify(pcb.GR_TEXT_V_ALIGN_CENTER)
    ref.SetLayer(pcb.F_SilkS)
    ref.SetVisible(True)


def main():
    # Most sheets originated in the hand-drawn r2.13 project. Apply the footprint
    # selection as a repeatable source transformation rather than editing them by hand.
    for sheet in cb.KICAD.glob('*.kicad_sch'):
        data = sheet.read_text(encoding='utf-8')
        revised = data.replace(f'(property "Footprint" "{OLD}"',
                               f'(property "Footprint" "{NEW}"')
        if sheet.name == 'CPLDs.kicad_sch':
            # cpld_sch.py creates the intermediate r2.42 sheet. The r1 layout
            # step normally updates its title block before this final conversion.
            revised = revised.replace('(date "2026-09-28")', '(date "2026-09-30")', 1)
            revised = revised.replace('(rev "2.42")', '(rev "r1")', 1)
        if revised != data:
            sheet.write_text(revised, encoding='utf-8')
    b = pcb.LoadBoard(str(cb.BOARD))
    caps = [f for f in b.GetFootprints() if f.GetValue() == '100nF' and f.GetReference().startswith('C')]
    assert len(caps) == 23, f'expected 23 100 nF capacitors, found {len(caps)}'
    old = [f for f in caps if f.GetFPIDAsString() == OLD]
    # Reapply the library footprint on subsequent runs so edits to the
    # silkscreen propagate to all placed capacitors.
    refresh = [f for f in caps if f.GetFPIDAsString() == NEW]
    other = [f.GetReference() for f in caps if f.GetFPIDAsString() not in (OLD, NEW)]
    assert not other, f'unexpected 100 nF footprints: {other}'
    if old:
        new = [replace(b, f) for f in old]
        place_without_overlaps(b, new)
        nets, count = cb.rip_collisions(b, new)
    else:
        new, nets, count = [], set(), 0
    for fp in refresh:
        replace(b, fp)
    aligned = []
    for ref, (x, y, angle) in ALIGN.items():
        fp = cb.find(b, ref)
        target = pcb.VECTOR2I(pcb.FromMM(x), pcb.FromMM(y))
        if fp.GetPosition() != target or fp.GetOrientationDegrees() != angle:
            fp.SetOrientationDegrees(angle)
            fp.SetPosition(target)
            aligned.append(fp)
    c11 = cb.find(b, 'C11')
    c13 = cb.find(b, 'C13')
    if c13.GetPosition().x != c11.GetPosition().x:
        c13.SetPosition(pcb.VECTOR2I(c11.GetPosition().x, c13.GetPosition().y))
        aligned.append(c13)
    c17 = cb.find(b, 'C17')
    c8 = cb.find(b, 'C8')
    if c8.GetPosition().y != c17.GetPosition().y:
        c8.SetPosition(pcb.VECTOR2I(c8.GetPosition().x, c17.GetPosition().y))
        aligned.append(c8)
    headings = [d for d in b.GetDrawings() if isinstance(d, pcb.PCB_TEXT)
                and d.GetText().strip() == 'Jumper Settings']
    assert len(headings) == 1, 'expected one Jumper Settings heading'
    heading = headings[0]
    jp3 = cb.find(b, 'JP3')
    c17_box = c17.GetCourtyard(pcb.F_CrtYd).BBox()
    jp3_box = jp3.GetCourtyard(pcb.F_CrtYd).BBox()
    if not c17_box.GetWidth():
        c17_box = c17.GetBoundingBox(False, False)
    if not jp3_box.GetWidth():
        jp3_box = jp3.GetBoundingBox(False, False)
    label_x = (c17_box.GetRight() + jp3_box.GetLeft()) // 2
    heading.SetPosition(pcb.VECTOR2I(label_x, c17.GetPosition().y))
    documentation = [d for d in b.GetDrawings() if isinstance(d, pcb.PCB_TEXT)
                     and d.GetText().strip() == 'See\nDocumentation']
    assert len(documentation) == 1, 'expected one See Documentation caption'
    documentation[0].SetPosition(pcb.VECTOR2I(label_x, documentation[0].GetPosition().y))
    aligned_nets, aligned_count = cb.rip_collisions(b, aligned)
    nets |= aligned_nets
    count += aligned_count
    for fp in b.GetFootprints():
        if fp.GetReference() in {c.GetReference() for c in caps}:
            center_reference(fp)
    pcb.ZONE_FILLER(b).Fill(b.Zones())
    cb.save(b)
    b.BuildConnectivity()
    print(f'converted {len(new)} capacitors; removed {count} colliding tracks/vias on {len(nets)} nets')
    print('unconnected before rerouting:', b.GetConnectivity().GetUnconnectedCount(True))


if __name__ == '__main__':
    main()
