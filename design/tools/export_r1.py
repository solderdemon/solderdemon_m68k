"""Generate the SolderDemon m68k r1 first-order package from current KiCad sources.

Run with KiCad 10 Python. The DRC/ERC error gates run before any existing CAM files
are replaced. The factory ZIP contains copper, masks, silkscreen, outline and drills;
the schematic PDF, BOM, position file and reports remain alongside it for review.
"""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

import pcbnew as pcb
import wx

wx.Log.EnableLogging(False)
ROOT = Path(__file__).resolve().parents[2]
KICAD = ROOT / 'design' / 'kicad'
BOARD = KICAD / 'solderdemon_m68k.kicad_pcb'
SCH = KICAD / 'solderdemon_m68k.kicad_sch'
OUT = ROOT / 'design' / 'CAMOutputs'
CLI = Path('C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')
STEM = 'solderdemon_m68k-r1'
LAYERS = ','.join(('F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu',
                   'F.Mask', 'B.Mask', 'F.Silkscreen', 'B.Silkscreen', 'Edge.Cuts'))


def run(*args):
    result = subprocess.run([str(CLI), *map(str, args)], cwd=ROOT,
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{' '.join(map(str, args))}\n"
                           f'{result.stdout}\n{result.stderr}')
    return result.stdout


def gate(report, kind):
    body = report.read_text(encoding='utf-8')
    # KiCad reports warning-only ERC/DRC with a successful exit code; count only
    # actual errors here and retain the full report in the package.
    match = re.search(rf'\*\* {kind} messages: \d+\s+Errors (\d+)', body)
    if match:
        errors = int(match.group(1))
    else:
        errors = len(re.findall(r'^\s*; error$', body, re.M)) if kind == 'ERC' else \
                 len(re.findall(r'^\s*[^\n]*; error$', body, re.M))
    if errors:
        raise RuntimeError(f'{kind}: {errors} errors; see {report}')
    return body


def main():
    b = pcb.LoadBoard(str(BOARD))
    edge = [shape for shape in b.GetDrawings() if shape.GetLayer() == pcb.Edge_Cuts]
    points = [point for shape in edge for point in (shape.GetStart(), shape.GetEnd())]
    size = (pcb.ToMM(max(p.x for p in points) - min(p.x for p in points)),
            pcb.ToMM(max(p.y for p in points) - min(p.y for p in points)))
    if not (abs(size[0] - 165.0) < 0.01 and abs(size[1] - 100.0) < 0.01):
        raise RuntimeError(f'unexpected r1 outline {size[0]:.2f} x {size[1]:.2f} mm')
    if b.GetCopperLayerCount() != 4:
        raise RuntimeError('r1 must have four copper layers')

    with tempfile.TemporaryDirectory(prefix='r1-export-', dir=ROOT / 'design') as tmp:
        stage = Path(tmp)
        erc = stage / f'{STEM}-erc.rpt'
        drc = stage / f'{STEM}-drc.rpt'
        run('sch', 'erc', '--severity-error', '-o', erc, SCH)
        gate(erc, 'ERC')
        run('pcb', 'drc', '--schematic-parity', '--severity-error',
            '--severity-warning', '-o', drc, BOARD)
        drc_text = drc.read_text(encoding='utf-8')
        if re.search(r'; error\s*$', drc_text, re.M):
            raise RuntimeError(f'DRC errors; see {drc}')
        if not re.search(r'\*\* Found 0 unconnected pads \*\*', drc_text):
            raise RuntimeError(f'unconnected pads; see {drc}')

        run('pcb', 'export', 'gerbers', '--layers', LAYERS, '--check-zones',
            '-o', stage, BOARD)
        run('pcb', 'export', 'drill', '--excellon-separate-th',
            '--generate-report', '--report-path', stage / f'{STEM}-drill-report.txt',
            '-o', stage, BOARD)
        run('sch', 'export', 'pdf', '-o', stage / f'{STEM}-schematic.pdf', SCH)
        run('sch', 'export', 'bom', '--fields',
            'Reference,Value,Footprint,QUANTITY,DNP', '--labels',
            'Refs,Value,Footprint,Qty,DNP', '--group-by', 'Value,Footprint',
            '-o', stage / f'{STEM}-bom.csv', SCH)
        run('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm',
            '--side', 'both', '-o', stage / f'{STEM}-pos.csv', BOARD)

        fab = [p for p in stage.iterdir() if p.suffix.lower() in
               {'.gtl', '.gbl', '.g1', '.g2', '.gts', '.gbs', '.gto', '.gbo',
                '.gm1', '.drl', '.gbrjob'}]
        if not any(p.suffix == '.g1' for p in fab) or not any(p.suffix == '.g2' for p in fab):
            raise RuntimeError('inner-layer Gerbers missing')
        if len([p for p in fab if p.suffix == '.drl']) != 2:
            raise RuntimeError('PTH/NPTH drill files missing')
        archive = stage / f'{STEM}-factory.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
            for p in sorted(fab):
                z.write(p, p.name)

        OUT.mkdir(exist_ok=True)
        for old in OUT.iterdir():
            if old.is_file():
                old.unlink()
        for p in stage.iterdir():
            if p.is_file():
                shutil.copy2(p, OUT / p.name)
        shutil.copy2(stage / f'{STEM}-schematic.pdf', KICAD / 'solderdemon_m68k.pdf')
        shutil.copy2(stage / f'{STEM}-bom.csv', KICAD / 'solderdemon_m68k.csv')
        print(f'{STEM}: {size[0]:.1f} x {size[1]:.1f} mm, 4 layers, '
              f'{len(fab)} factory files; ERC/DRC errors 0, unconnected 0')
        print(f'Factory ZIP: {OUT / archive.name}')


if __name__ == '__main__':
    main()
