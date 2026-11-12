"""Exercise privacy checks in isolated repositories with synthetic data only."""
from pathlib import Path
import subprocess
import tempfile
import unittest

CHECKER = Path(__file__).resolve().parents[1] / 'scripts/check-privacy.py'


class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Synthetic Tester')
        self.git('config', 'user.email', 'tester@example.com')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.DEVNULL)

    def stage(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode() if isinstance(content, str) else content)
        self.git('add', '-f', name)

    def check(self, mode='staged'):
        return subprocess.run(['python3', str(CHECKER), mode], cwd=self.root,
                              input='', text=True, capture_output=True)

    def test_clean_synthetic_example(self):
        self.stage('example.txt', 'tester@example.com\nSynthetic data only\n')
        self.assertEqual(self.check().returncode, 0)

    def test_private_paths(self):
        for name in ('.env.production', 'forecasting/data/report.json', 'backup.vault.json', 'statement.csv'):
            with self.subTest(name=name):
                self.stage(name, 'synthetic')
                self.assertNotEqual(self.check().returncode, 0)
                self.git('rm', '--cached', name)

    def test_personal_email_and_iban(self):
        for value in ('alice' + '@' + 'private-mail.test', 'DE89' + '370400440532013000'):
            self.stage('notes.txt', value)
            result = self.check()
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(value, result.stderr)

    def test_secret_and_staged_content(self):
        token = 'ghp_' + 'aB3dE5fG7hJ9kL1mN2pQ4rS6tU8vW0xYzABC'
        self.stage('settings.txt', token)
        (self.root / 'settings.txt').write_text('clean working copy')
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Gitleaks', result.stderr)
        self.assertNotIn(token, result.stderr + result.stdout)

    def test_deleted_personal_data_still_blocks_push(self):
        self.stage('notes.txt', 'alice' + '@' + 'private-mail.test')
        self.git('commit', '-qm', 'Synthetic fixture')
        self.git('rm', 'notes.txt')
        self.git('commit', '-qm', 'Remove synthetic fixture')
        self.assertNotEqual(self.check('push').returncode, 0)

    def test_binary_and_symlink(self):
        self.stage('screenshot.png', b'\x89PNG\0synthetic')
        self.assertNotEqual(self.check().returncode, 0)
        self.git('rm', '--cached', 'screenshot.png')
        (self.root / 'link').symlink_to('screenshot.png')
        self.git('add', 'link')
        self.assertNotEqual(self.check().returncode, 0)


if __name__ == '__main__':
    unittest.main()
