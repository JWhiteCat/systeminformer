"""Guard the fork against silently installing upstream binaries."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ForkUpdaterTests(unittest.TestCase):
    def test_entrypoint_is_inert_even_with_existing_update_settings(self):
        source = (ROOT / 'plugins/Updater/main.c').read_text()
        entrypoint = source[source.index('LOGICAL DllMain('):]
        self.assertIn('PhRegisterPlugin(PLUGIN_NAME, Instance, &info)', entrypoint)
        self.assertIn('disabled in bilingual fork', entrypoint)
        for forbidden in ('PhRegisterCallback(', 'PhAddSettings(', 'StartInitialCheck(',
                          'ShowUpdateDialog(', 'ShowStartupUpdateDialog(',
                          'PhGetIntegerSetting(', 'PhGetStringSetting('):
            self.assertNotIn(forbidden, entrypoint)
        self.assertIn('return TRUE;', entrypoint)  # no spurious load-error popup

if __name__ == '__main__':
    unittest.main()
