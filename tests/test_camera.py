"""Isolated stdlib tests for camera wifi configuration."""
import stat
import tempfile
import unittest
from pathlib import Path

from scripts import setup_wifi


class TestWifiSetup(unittest.TestCase):
    def test_private_header(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'wifi_secrets.h'
            setup_wifi.write_header(p, 'test-only', 'not-a-network-password')
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
            self.assertIn('WIFI_SSID', p.read_text())

    def test_escape_and_refuse_overwrite(self):
        self.assertEqual(setup_wifi.c_string('"\\\n?é'), '"\\042\\134\\012\\077\\303\\251"')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'wifi_secrets.h'
            setup_wifi.write_header(p, 'test-only', '')
            with self.assertRaises(FileExistsError):
                setup_wifi.write_header(p, 'other', '')


if __name__ == '__main__':
    unittest.main()
