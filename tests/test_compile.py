"""Test Arduino firmware compilation without overwriting real credentials."""
import subprocess
import time
import unittest
from pathlib import Path

from scripts import setup_wifi

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HEADER = PROJECT_ROOT / 'CameraWebServer/wifi_secrets.h'
ARDUINO_CLI = PROJECT_ROOT / '.camera-tools/bin/arduino-cli'


class TestCompile(unittest.TestCase):
    def test_firmware_compile(self):
        if not ARDUINO_CLI.exists():
            self.skipTest('arduino-cli not installed in .camera-tools/bin')
        if HEADER.exists():
            self.skipTest('CameraWebServer/wifi_secrets.h exists; preserving private credentials')

        setup_wifi.write_header(HEADER, 'COMPILE_ONLY_NO_NETWORK', '')
        start = time.monotonic()
        try:
            result = subprocess.run([
                str(ARDUINO_CLI),
                '--config-file', str(PROJECT_ROOT / 'arduino-cli.yaml'),
                'compile', '--fqbn', 'esp32:esp32:esp32cam',
                '--build-path', str(PROJECT_ROOT / 'build/compile-only'),
                str(PROJECT_ROOT / 'CameraWebServer'),
            ], cwd=PROJECT_ROOT, capture_output=True)
            self.assertEqual(result.returncode, 0, f"Compilation failed: {result.stderr.decode()}")
        finally:
            if HEADER.exists():
                HEADER.unlink()


if __name__ == '__main__':
    unittest.main()
