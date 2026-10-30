"""Large evidence stays compatible with unchanged source/checkpoint inventories."""
import io
import json
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loop.native_packet import source_delivery, verify_source_bundle, verify_source_materials, work_guide
from loop.native_qualification import load_materials
from loop.util import Rejected, digest, identity, tree


class SourceArchivePartsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        files = {}
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, 'w') as archive:
            for name in ('a.bin', 'b.bin'):
                raw = name.encode() * 900_000
                files[name] = dict(sha256=digest(raw), mode=0o644)
                info = zipfile.ZipInfo(name)
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, raw)
        cls.raw = memory.getvalue()
        cls.expected = identity(files)
        cls.manifest = json.dumps(dict(source=cls.expected, files=files)).encode()
        cls.selected = dict(manifest='current-source/manifest.json', archive=['current-source/part1', 'current-source/part2'])

    def setup_bundle(self, root):
        middle = len(self.raw)//2
        material = dict(zip([self.selected['manifest'], *self.selected['archive']], [self.manifest,self.raw[:middle],self.raw[middle:]]))
        for name, raw in material.items():
            path = root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        index = dict(binding=dict(controller_source_hash=self.expected,source_delivery=self.selected),
                     originals={name:dict(category='reference') for name in material})
        return material,index

    def test_ordered_parts_verify_exact_bytes_with_unchanged_input_tree(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); material,index=self.setup_bundle(root)
            self.assertGreater(len(self.raw),8_000_000)
            self.assertEqual(len(tree(root)),3)
            self.assertEqual(verify_source_materials(material,index),dict(verified_source=self.expected,files=2))
            self.assertEqual(verify_source_bundle(root/self.selected['manifest'],[root/n for n in self.selected['archive']],self.expected)['verified_source'],self.expected)

    def test_generated_model_command_executes_the_same_exact_verifier(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); _,index=self.setup_bundle(root)
            command=work_guide(index).split('Source-integrity command:\n')[1].splitlines()[0]
            argv=shlex.split(command)
            argv[2]=argv[2].replace('/inputs/',str(root)+'/').replace("'/controller'",repr(str(Path(__file__).resolve().parents[1])))
            result=subprocess.run([sys.executable,*argv[1:]],capture_output=True,text=True,check=True)
            self.assertEqual(json.loads(result.stdout)['verified_source'],self.expected)

    def test_wrong_order_tampered_or_missing_parts_do_not_verify(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); material,index=self.setup_bundle(root)
            wrong=json.loads(json.dumps(index));wrong['binding']['source_delivery']['archive'].reverse()
            with self.assertRaises(Rejected):verify_source_materials(material,wrong)
            material[self.selected['archive'][0]]=b'bad bytes'
            with self.assertRaises(Rejected):verify_source_materials(material,index)
            del material[self.selected['archive'][0]]
            with self.assertRaises(KeyError):verify_source_materials(material,index)

    def test_duplicate_unbound_history_and_oversized_part_lists_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            _,index=self.setup_bundle(Path(folder))
            for parts in ([],['current-source/part1']*2,['current-source/part1']*9,[42]):
                with self.assertRaises(Rejected):source_delivery(dict(source_delivery=dict(self.selected,archive=parts)),index['originals'])
            index['originals']['current-source/part1']['category']='history'
            with self.assertRaises(Rejected):source_delivery(index['binding'],index['originals'])

    def test_single_large_material_rejected_before_any_home_or_intent(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'source.zip';path.write_bytes(self.raw)
            with self.assertRaisesRegex(Rejected,'per-file snapshot limit'):
                load_materials(dict(materials=[dict(name='current-source/source.zip',path=str(path),sha256=digest(self.raw))]))
            self.assertEqual([p.name for p in root.iterdir()],['source.zip'])

    def test_ordinary_source_tree_still_rejects_the_unsplit_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'source.zip').write_bytes(self.raw)
            with self.assertRaisesRegex(Rejected,'Source file exceeds bounded snapshot limit'):tree(folder)


if __name__=='__main__':unittest.main()
