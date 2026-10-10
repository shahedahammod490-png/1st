"""Apply the verified Capture fix to an existing separate Research Lab.

Standard library only. Stop the Lab first. Datasets are never inspected/copied.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(lab, package):
    lab = lab.resolve()
    if not (lab / 'ocurisk_lab/server.py').is_file() or not (lab / 'requirements.txt').is_file():
        raise ValueError('Select the separate Stage 2 Research Lab folder containing ocurisk_lab and requirements.txt; never the original OcuRisk/EYE project.')
    entries = json.loads((package / 'manifest.json').read_text(encoding='utf-8'))
    permitted = {
        'ocurisk_lab/server.py', 'ocurisk_lab/web/ui.js',
        'ocurisk_lab/web/app.js', 'ocurisk_lab/web/live-capture.js',
        'tests/browser/capture-regression.cjs', 'tests/test_service_logging.py',
        'research/verification/CAPTURE_STUDIO_FIX.md',
    }
    if set(entries) != permitted:
        raise ValueError('Unexpected patch paths; no files changed.')
    plan = []
    for name, info in entries.items():
        source = package / name
        data = source.read_bytes()
        if digest(data) != info['sha256']:
            raise ValueError(f'Patch integrity failure: {name}; no files changed.')
        destination = lab / name
        if not destination.resolve().is_relative_to(lab) or destination.is_symlink():
            raise ValueError(f'Unsafe destination: {name}; no files changed.')
        prior = destination.read_bytes() if destination.exists() else None
        if prior is not None and digest(prior) == info['sha256']:
            continue
        if prior is not None and digest(prior) != info['baseline_sha256']:
            raise ValueError(f'Local edits or different version detected: {name}. Preserve them and reconcile manually; no files changed.')
        if prior is None and info['baseline_sha256'] is not None:
            raise ValueError(f'Expected baseline file missing: {name}; no files changed.')
        plan.append((name, destination, data, prior))
    if not plan:
        print('Capture Studio fix already installed; nothing changed.')
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    backup = lab / '.capture-fix-backups' / stamp
    if not backup.resolve().is_relative_to(lab):
        raise ValueError('Unsafe backup directory; no files changed.')
    backup.mkdir(parents=True, exist_ok=False)
    # Complete backups before replacing any application files.
    for name, _, _, prior in plan:
        if prior is not None:
            target = backup / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(prior)
    (backup / 'backup-manifest.json').write_text(json.dumps({
        name: digest(prior) if prior is not None else None
        for name, _, _, prior in plan
    }, indent=2), encoding='utf-8')
    written = []
    try:
        for name, destination, data, prior in plan:
            destination.parent.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(prefix='.capture-fix-', dir=destination.parent)
            try:
                with os.fdopen(handle, 'wb') as stream:
                    stream.write(data)
                os.replace(temporary, destination)
                written.append((destination, prior))
            finally:
                Path(temporary).unlink(missing_ok=True)
    except BaseException:
        for destination, prior in reversed(written):
            if prior is None:
                destination.unlink(missing_ok=True)
            else:
                destination.write_bytes(prior)
        raise
    print(f'Updated {len(plan)} source/test/report files. Backup: {backup}')
    print('Datasets, .venv, CameraX and the original OcuRisk were not changed. Restart the separate Lab now.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        apply(args.lab_dir, Path(__file__).resolve().parent)
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
