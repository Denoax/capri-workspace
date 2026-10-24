import importlib.util
from pathlib import Path
import tempfile
import unittest

BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('capri_installer',BASE/'tools/install_v2.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class SessionHookTests(unittest.TestCase):
    def test_owned_hook_removal_preserves_unrelated_user_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config=root/'hyprland.lua';bootstrap=root/'bootstrap';bootstrap.mkdir()
            original='-- Existing owner configuration\nlocal hl = {}\n';config.write_text(original)
            installer.install_session_hook(config,bootstrap,Path('/usr/bin/python3'))
            self.assertIn('hyprland.start',config.read_text());self.assertIn('hyprland.shutdown',config.read_text())
            config.write_text(config.read_text()+'-- Later owner change\n')
            installer.remove_session_hook(bootstrap,check=True);installer.remove_session_hook(bootstrap)
            self.assertEqual(config.read_text(),original+'-- Later owner change\n')
            self.assertFalse((bootstrap/'session-hook.json').exists())
    def test_changed_owned_fragment_and_symlink_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config=root/'hyprland.lua';bootstrap=root/'bootstrap';bootstrap.mkdir();config.write_text('-- Owner config\n')
            installer.install_session_hook(config,bootstrap,Path('/usr/bin/python3'))
            config.write_text(config.read_text().replace('hyprland.start','owner.changed'))
            before=config.read_bytes()
            with self.assertRaises(SystemExit):installer.remove_session_hook(bootstrap)
            self.assertEqual(config.read_bytes(),before)
            link=root/'link.lua';link.symlink_to(config)
            with self.assertRaises(SystemExit):installer.install_session_hook(link,bootstrap,Path('/usr/bin/python3'))
    def test_missing_or_stale_wayland_socket_denies_startup(self):
        from unittest.mock import patch
        spec=importlib.util.spec_from_file_location('capri_session_start',BASE/'tools/session_start.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder,patch.dict('os.environ',{'XDG_RUNTIME_DIR':folder,'WAYLAND_DISPLAY':'wayland-999'}):
            self.assertFalse(module.ready())
            (Path(folder)/'wayland-999').write_text('Not a socket')
            self.assertFalse(module.ready())
