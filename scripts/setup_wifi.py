"""Run locally in a private terminal; never pass credentials as arguments."""
import getpass
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def c_string(value):
    # Fixed-width octal escapes prevent quote injection, trigraphs and hex bleed.
    return '"' + ''.join(f'\\{b:03o}' for b in value.encode('utf-8')) + '"'


def write_header(path, ssid, password):
    if not 1 <= len(ssid.encode('utf-8')) <= 32:
        raise ValueError('SSID must contain 1–32 UTF-8 bytes')
    if '\0' in ssid or '\0' in password:
        raise ValueError('NUL is not supported')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='ascii') as f:
        f.write('#pragma once\n#define WIFI_SSID ' + c_string(ssid)
                + '\n#define WIFI_PASSWORD ' + c_string(password) + '\n')


if __name__ == '__main__':
    if not os.isatty(0):
        raise SystemExit('Run interactively in your own terminal.')
    ssid = getpass.getpass('SSID (hidden): ')
    password = getpass.getpass('Wi-Fi password (hidden; empty for open network): ')
    try:
        write_header(PROJECT_ROOT / 'CameraWebServer/wifi_secrets.h', ssid, password)
    except (ValueError, FileExistsError):
        raise SystemExit('Invalid input or header already exists; remove it locally to reconfigure.')
    print('Private header created. No credentials printed.')
