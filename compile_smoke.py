"""Compile only with unmistakable test values; never upload or use real secrets."""
import subprocess
import time
from pathlib import Path
import setup_wifi

root = Path(__file__).resolve().parent
header = root / 'CameraWebServer/wifi_secrets.h'
# O_EXCL refuses to read or replace a user's existing header.
setup_wifi.write_header(header, 'COMPILE_ONLY_NO_NETWORK', '')
start = time.monotonic()
try:
    result = subprocess.run([
        str(root / '.camera-tools/bin/arduino-cli'),
        '--config-file', str(root / 'arduino-cli.yaml'),
        'compile', '--fqbn', 'esp32:esp32:esp32cam',
        '--build-path', str(root / 'build/compile-only'),
        str(root / 'CameraWebServer')], cwd=root)
finally:
    header.unlink()
    print(f'Compile-only header removed; duration {time.monotonic() - start:.2f}s', flush=True)
raise SystemExit(result.returncode)
