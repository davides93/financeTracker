#!/usr/bin/env python3
"""Fail closed on private files, common personal identifiers and Gitleaks findings."""
import fnmatch
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile


def git(*args):
    return subprocess.check_output(['git', *args])


def blocked_path(name):
    parts = PurePosixPath(name).parts
    private_dirs = {'data', 'outputs', 'backups', 'exports', 'imports', 'private',
                    'secrets', '.agents', '.codex', 'node_modules', '.venv', '__pycache__'}
    if set(parts) & private_dirs or name.startswith(('forecasting/models/', 'design/')):
        return True
    base = parts[-1].lower()
    if base.startswith('.env') or base.startswith(('credentials', 'service-account')):
        return True
    if name == 'forecasting/portfolio.example.csv':
        return False
    return any(fnmatch.fnmatch(base, pattern) for pattern in (
        '*.csv', '*.pdf', '*.ofx', '*.qfx', '*.qif', '*.sqlite*', '*.db', '*.db-*',
        '*.vault*', '*.pem', '*.key', '*.p12', '*.pfx', '*.keystore', '*.jks',
        '*.zip', '*.tar', '*.gz', '*.7z', '*.xlsx', '*.docx'))


def personal_text(text):
    # Public documentation examples and GitHub's masked author address are permitted.
    for match in re.finditer(r'[\w.+%-]+@([\w.-]+\.[A-Za-z]{2,})', text):
        if match.group(0) == '128x128@2x.png':  # Standard retina icon filename.
            continue
        domain = match.group(1).lower()
        if domain not in {'example.com', 'example.org', 'example.net', 'users.noreply.github.com'}:
            return True
    if re.search(r'/(?:Users|home)/[A-Za-z0-9_.-]+/', text):
        return True
    # Italian tax codes and IBANs (including display spaces).
    if re.search(r'\b[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]\b', text):
        return True
    for match in re.finditer(r'\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b', text):
        iban = match.group().replace(' ', '')
        if not 15 <= len(iban) <= 34:
            continue
        digits = ''.join(str(ord(c) - 55) if c.isalpha() else c for c in iban[4:] + iban[:4])
        if int(digits) % 97 == 1:
            return True
    return False


def scan(mode):
    if not shutil.which('gitleaks'):
        raise ValueError('Install Gitleaks before committing or pushing (macOS: brew install gitleaks).')
    if mode == 'staged':
        trees = [None]
    elif mode == 'push':
        # Scan every ancestor, including intermediate commits that later delete data.
        tips = []
        if not sys.stdin.isatty():
            for line in sys.stdin:
                fields = line.split()
                if len(fields) == 4 and set(fields[1]) != {'0'}:
                    tips.append(fields[1])
        if not tips:
            tips = ['--all']
        trees = git('rev-list', *tips).decode().splitlines()
    else:
        raise ValueError('Expected staged or push.')
    seen = set()
    with tempfile.TemporaryDirectory(prefix='orizzonte-privacy-') as temporary:
        root = Path(temporary)
        # Owner-only directory; no personal data or secret values are printed.
        for tree in trees:
            rows = git('ls-files', '--stage', '-z') if tree is None else git('ls-tree', '-r', '-z', tree)
            for row in rows.split(b'\0'):
                if not row:
                    continue
                header, raw_name = row.split(b'\t', 1)
                fields = header.decode().split()
                mode_bits, blob = fields[:2] if tree is None else (fields[0], fields[2])
                name = os.fsdecode(raw_name)
                if blocked_path(name):
                    raise ValueError('Private or generated file detected. Remove it from the index/history.')
                if mode_bits not in {'100644', '100755'}:
                    raise ValueError('Symlink, submodule or unresolved entry requires manual privacy review.')
                if blob in seen:
                    continue
                seen.add(blob)
                data = git('cat-file', 'blob', blob)
                if len(data) > 5_000_000:
                    raise ValueError('File over 5 MB requires manual privacy review.')
                if b'\0' in data:
                    if not name.startswith('src-tauri/icons/'):
                        raise ValueError('Binary file outside application icons requires manual privacy review.')
                else:
                    try:
                        text = data.decode('utf-8')
                    except UnicodeDecodeError:
                        raise ValueError('Non-UTF-8 file requires manual privacy review.') from None
                    if personal_text(text):
                        raise ValueError('Possible personal identifier detected. Use synthetic examples instead.')
                # Flatten paths and preserve every unique blob, including deleted historical files.
                (root / blob).write_bytes(data)
        result = subprocess.run(['gitleaks', 'dir', str(root), '--redact', '--no-banner',
                                 '--timeout', '120'], capture_output=True)
        if result.returncode:
            raise ValueError('Gitleaks detected a secret or could not complete. Review locally with redacted output.')
    print('Privacy check passed: private paths, common personal identifiers and secrets.')


if __name__ == '__main__':
    try:
        scan(sys.argv[1] if len(sys.argv) > 1 else 'staged')
    except (ValueError, subprocess.CalledProcessError, OSError) as error:
        print(f'Privacy check BLOCKED: {error}', file=sys.stderr)
        sys.exit(1)
