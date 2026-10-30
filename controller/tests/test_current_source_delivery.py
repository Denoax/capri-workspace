import io
import json
import shlex
import stat
import sys
from pathlib import Path
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from loop.native_packet import verify_source_bytes,source_delivery,work_guide
from loop.util import digest,identity,Rejected


class CurrentSourceTests(unittest.TestCase):
    def bundle(self,mode=0o644,archive_mode=None):
        raw=b'exact current implementation';files={'code.py':dict(sha256=digest(raw),mode=mode)};expected=identity(files)
        memory=io.BytesIO()
        with zipfile.ZipFile(memory,'w') as z:
            info=zipfile.ZipInfo('code.py');info.external_attr=(stat.S_IFREG|(mode if archive_mode is None else archive_mode))<<16
            z.writestr(info,raw)
        return json.dumps(dict(source=expected,files=files)).encode(),memory.getvalue(),expected

    def test_current_bundle_verifies_content_mode_and_exact_identity(self):
        manifest,archive,expected=self.bundle()
        self.assertEqual(verify_source_bytes(manifest,archive,expected),dict(verified_source=expected,files=1))

    def test_historical_source_cannot_masquerade_as_current(self):
        manifest,archive,expected=self.bundle()
        with self.assertRaises(Rejected):verify_source_bytes(manifest,archive,'0'*64)

    def test_rebound_inventory_wrong_mode_or_missing_entry_is_rejected(self):
        manifest,archive,expected=self.bundle(archive_mode=0o755)
        with self.assertRaises(Rejected):verify_source_bytes(manifest,archive,expected)
        m=json.loads(manifest);m['files']['extra.py']=m['files']['code.py'];m['source']=identity(m['files'])
        with self.assertRaises(Rejected):verify_source_bytes(json.dumps(m).encode(),archive,m['source'])

    def test_work_command_selects_bound_current_paths_preserving_legacy_guide(self):
        selected=dict(manifest='current-source/SOURCE_MANIFEST.json',archive='current-source/source.zip')
        index=dict(binding=dict(controller_source_hash='e'*64,source_delivery=selected),originals={n:dict(category='reference') for n in selected.values()})
        guide=work_guide(index);command=guide.split('Source-integrity command:\n')[1].splitlines()[0]
        argv=shlex.split(command)
        self.assertEqual(argv[:2],['python3','-c']);self.assertIn('/inputs/current-source/SOURCE_MANIFEST.json',argv[2])
        self.assertNotIn('/inputs/authority/SOURCE_MANIFEST.json',argv[2])
        self.assertIn('/inputs/authority/SOURCE_MANIFEST.json',work_guide(dict(binding={'controller_source_hash':'e'*64})))

    def test_current_delivery_rejects_history_unbound_and_traversal_paths(self):
        selected=dict(manifest='current-source/m.json',archive='current-source/s.zip')
        for records in ({},{n:dict(category='history') for n in selected.values()}):
            with self.assertRaises(Rejected):source_delivery(dict(source_delivery=selected),records)
        with self.assertRaises(Rejected):source_delivery(dict(source_delivery=dict(manifest='../escape',archive=selected['archive'])),{})


if __name__=='__main__':unittest.main()
