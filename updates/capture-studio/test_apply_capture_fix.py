"""Updater regression: preserve data/local changes and repeat safely."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from apply_capture_fix import apply


PACKAGE = Path(__file__).resolve().parent
ARCHIVE = PACKAGE.parents[1] / 'OcuRisk-Checkpoint-20261009T224737Z.zip'


class UpdateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lab = Path(self.temp.name) / 'lab'
        self.lab.mkdir()
        self.entries = json.loads((PACKAGE / 'manifest.json').read_text())
        with zipfile.ZipFile(ARCHIVE) as archive:
            for name, info in self.entries.items():
                if info['baseline_sha256']:
                    target = self.lab / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read('working-trees/main/' + name))
        (self.lab / 'requirements.txt').write_text('fixture marker')
        (self.lab / 'data').mkdir()
        (self.lab / 'data' / 'retain.db').write_bytes(b'RETAIN SYNTHETIC DATA SENTINEL')

    def snapshot(self):
        return {str(p.relative_to(self.lab)): p.read_bytes() for p in self.lab.rglob('*') if p.is_file()}

    def test_apply_backup_data_preservation_and_repeat(self):
        before = self.snapshot()
        apply(self.lab, PACKAGE)
        for name, info in self.entries.items():
            self.assertEqual(hashlib.sha256((self.lab / name).read_bytes()).hexdigest(), info['sha256'])
        self.assertEqual((self.lab / 'data/retain.db').read_bytes(), before['data/retain.db'])
        backups = list((self.lab / '.capture-fix-backups').iterdir())
        self.assertEqual(len(backups), 1)
        for name in self.entries:
            if name in before:
                self.assertEqual((backups[0] / name).read_bytes(), before[name])
        after = self.snapshot()
        apply(self.lab, PACKAGE)
        self.assertEqual(self.snapshot(), after)

    def test_local_changes_rejected_before_any_write(self):
        (self.lab / 'ocurisk_lab/web/ui.js').write_text('preserve newer local code')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Local edits'):
            apply(self.lab, PACKAGE)
        self.assertEqual(self.snapshot(), before)

    def test_original_project_rejected(self):
        original = self.lab.parent / 'original-eye'
        original.mkdir()
        (original / 'package.json').write_text('original fixture')
        with self.assertRaisesRegex(ValueError, 'separate Stage 2'):
            apply(original, PACKAGE)
        self.assertEqual(list(original.iterdir()), [original / 'package.json'])

    def test_symlink_escape_rejected_before_any_write(self):
        target = self.lab / 'ocurisk_lab/web/ui.js'
        external = self.lab.parent / 'preserve-external.js'
        external.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(external)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Unsafe destination'):
            apply(self.lab, PACKAGE)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(external.read_bytes(), before['ocurisk_lab/web/ui.js'])


if __name__ == '__main__':
    unittest.main()
