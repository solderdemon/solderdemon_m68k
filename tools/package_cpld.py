"""Package production r1.1 CPLDs and verify the hardware-tested fuse identities.

Build and run verification gates before packaging. JEDEC timestamps are not
part of fuse identity; both image bytes and expanded fuse hashes are recorded.
"""
from pathlib import Path
import hashlib
import json
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1] / 'code/firmware/pld/cpld'
TESTED = {
    'IC2': '6e02d7434e96097cfba744513c6bac6b8871e40dde24d650d73a42fb2f8048bf',
    'IC3': 'f5cebb8ca90743a72f866adfde11901225adcf282b595e09f3cf0b093d0017df',
}


def fuse_bits(path):
    text = path.read_text()
    size = int(re.search(r'QF(\d+)\*', text).group(1))
    default = int(re.search(r'\bF([01])\*', text).group(1))
    fuses = bytearray([default]) * size
    for offset, bits in re.findall(r'(?:^|\*)\s*L(\d+)\s+([01\s]+)\*', text):
        offset = int(offset)
        values = bytes(int(bit) for bit in re.sub(r'\s', '', bits))
        assert offset + len(values) <= size
        fuses[offset:offset + len(values)] = values
    return bytes(fuses)


def main():
    manifest = {'firmware': 'SolderDemon m68k IC2 r1.1 + original IC3',
                'date': '2026-11-17', 'images': {},
                'hardware_evidence': 'Owner reported stable startup/reset with this exact fuse pair; '
                                     'physical AS waveform was not measured.'}
    files = {}
    for chip, name in [('IC2', 'ic2_decoder'), ('IC3', 'ic3_glue')]:
        image = ROOT / 'bin' / f'{name}.jed'
        bits = fuse_bits(image)
        digest = hashlib.sha256(bits).hexdigest()
        assert len(bits) == 16808 and digest == TESTED[chip], (chip, 'not the hardware-tested fuse map')
        manifest['images'][chip] = {
            'file': f'{name}.jed', 'fuse_count': len(bits),
            'sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
            'expanded_fuse_sha256': digest,
        }
        files[f'{name}.jed'] = image
        files[f'{name}.pld'] = ROOT / f'{name}.pld'
        files[f'{name}.fit'] = ROOT / 'bin' / f'{name}.fit'
    files['README.md'] = ROOT / 'README.md'
    out = ROOT / 'release'
    out.mkdir(exist_ok=True)
    content = json.dumps(manifest, indent=2) + '\n'
    (out / 'manifest.json').write_text(content)
    instructions = '''# SolderDemon m68k production CPLDs, IC2 firmware r1.1

Program ic2_decoder.jed into physical IC2; ic3_glue.jed into physical IC3.
The two chips are the same part type but have different functions. Label them.
IC2 uses address-based ROM handoff. IC3 uses the original production watchdog.
Use the existing ROM Flash contents; the reset PC must be in E00000-EFFFFF.
JTAG stays enabled. Always verify after programming.

The fuse maps match the pair reported working on the assembled board on
2026-11-17. A chip already programmed with that pair needs no further rewrite.
The included README.md describes the source-tree build and verification commands.
manifest.json and SHA256SUMS.txt identify the packaged files.
'''
    archive = out / 'solderdemon_m68k-cpld-r1.1.zip'
    checksums = []
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        payloads = {name: path.read_bytes() for name, path in files.items()}
        payloads['manifest.json'] = content.encode()
        payloads['PROGRAMMING.txt'] = instructions.encode()
        for name, payload in payloads.items():
            z.writestr(name, payload)
            checksums.append(f'{hashlib.sha256(payload).hexdigest()}  {name}')
        z.writestr('SHA256SUMS.txt', '\n'.join(checksums) + '\n')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
    print('PASS: both 16,808-fuse maps exactly match the successful hardware test.')
    print(archive)


if __name__ == '__main__':
    main()
