import os
import shutil
import stat
import subprocess
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from project.services.telegram_bot import TelegramControlBot


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPDATE_SCRIPT = PROJECT_ROOT / "update_uvjerenja_terminal.sh"
INSTALL_SCRIPT = PROJECT_ROOT / "install_uvjerenja_terminal.sh"


def _git_executable() -> str:
    executable = shutil.which("git")
    if not executable:
        raise unittest.SkipTest("git is not available")
    return executable


def _bash_executable() -> str:
    if os.name == "nt":
        for candidate in (
            Path(r"C:\Program Files\Git\bin\bash.exe"),
            Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
        ):
            if candidate.is_file():
                return str(candidate)
    executable = shutil.which("bash")
    if not executable:
        raise unittest.SkipTest("bash is not available")
    return executable


def _bash_path(path: Path) -> str:
    resolved = path.resolve()
    if os.name != "nt":
        return str(resolved)
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.as_posix().split(":", 1)[1]
    return f"/{drive}{tail}"


@contextmanager
def _update_test_directory():
    """Retry Windows cleanup while short-lived Git/Bash handles are released."""
    def clear_readonly_and_retry(function, item, _error_info):
        os.chmod(item, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        function(item)

    path = Path(tempfile.mkdtemp(prefix=".update-safety-", dir=PROJECT_ROOT))
    try:
        yield path
    finally:
        for attempt in range(10):
            try:
                shutil.rmtree(path, onerror=clear_readonly_and_retry)
                break
            except FileNotFoundError:
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.25)


class UpdateScriptEnvSafetyTests(unittest.TestCase):
    def _prepare_remote(self, root: Path) -> Path:
        git = _git_executable()
        seed = root / "seed"
        origin = root / "origin.git"
        seed.mkdir()
        subprocess.run([git, "init", "-b", "main"], cwd=seed, check=True, capture_output=True)
        subprocess.run([git, "config", "user.email", "tests@example.invalid"], cwd=seed, check=True)
        subprocess.run([git, "config", "user.name", "Update Safety Tests"], cwd=seed, check=True)
        (seed / "install_uvjerenja_terminal.sh").write_text(
            """#!/usr/bin/env bash
set -euo pipefail
if [[ "${MUTATE_ENV:-0}" == "1" ]]; then
  sed -i 's/^SECRET=.*/SECRET="replaced"/' "$POTVRDE_ENV_FILE"
else
  printf '%s\\n' 'NEW_SETTING="added"' >> "$POTVRDE_ENV_FILE"
fi
""",
            encoding="utf-8",
        )
        (seed / "update_uvjerenja_terminal.sh").write_bytes(UPDATE_SCRIPT.read_bytes())
        for script in seed.glob("*.sh"):
            script.chmod(0o755)
        subprocess.run([git, "add", "."], cwd=seed, check=True)
        subprocess.run([git, "commit", "-m", "test release"], cwd=seed, check=True, capture_output=True)
        subprocess.run([git, "clone", "--bare", str(seed), str(origin)], check=True, capture_output=True)
        return origin

    def _run_update(
        self, root: Path, *, mutate_env: bool
    ) -> tuple[subprocess.CompletedProcess, Path, Path, bytes, Path, bytes]:
        origin = self._prepare_remote(root)
        source = root / "source"
        subprocess.run([_git_executable(), "clone", str(origin), str(source)], check=True, capture_output=True)
        source_env_original = b'SOURCE_SECRET="keep source env"\n'
        (source / ".env").write_bytes(source_env_original)
        env_file = root / "installed.env"
        backup_dir = root / "env-backups"
        original = b'SECRET="keep me"\nPOTVRDE_PRINTER_NAME="USB_Printer"\n'
        env_file.write_bytes(original)

        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        fake_sudo = fake_bin / "sudo"
        fake_sudo.write_text('#!/usr/bin/env bash\nexec "$@"\n', encoding="utf-8")
        fake_sudo.chmod(0o755)

        env = os.environ.copy()
        env.update(
            {
                "APP_ID": "uvjerenja-test",
                "POTVRDE_UPDATE_REPO_URL": _bash_path(origin),
                "POTVRDE_UPDATE_SOURCE_DIR": _bash_path(source),
                "POTVRDE_UPDATE_BRANCH": "main",
                "POTVRDE_ENV_FILE": _bash_path(env_file),
                "POTVRDE_ENV_BACKUP_DIR": _bash_path(backup_dir),
                "MUTATE_ENV": "1" if mutate_env else "0",
                "TMPDIR": _bash_path(root),
                "TMP": _bash_path(root),
                "TEMP": _bash_path(root),
                "PATH": str(fake_bin) + os.pathsep + env.get("PATH", ""),
            }
        )
        result = subprocess.run(
            [_bash_executable(), _bash_path(UPDATE_SCRIPT)],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
        )
        return result, env_file, backup_dir, original, source / ".env", source_env_original

    def test_update_keeps_existing_values_and_allows_only_new_keys(self):
        with _update_test_directory() as temp_dir:
            result, env_file, backup_dir, original, source_env, source_env_original = self._run_update(
                temp_dir, mutate_env=False
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            updated = env_file.read_bytes()
            self.assertTrue(updated.startswith(original))
            self.assertIn(b'NEW_SETTING="added"', updated)
            backups = list(backup_dir.glob("*.backup"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)
            self.assertEqual(source_env.read_bytes(), source_env_original)

    def test_update_rejects_changed_secret_and_restores_full_env(self):
        with _update_test_directory() as temp_dir:
            result, env_file, backup_dir, original, source_env, source_env_original = self._run_update(
                temp_dir, mutate_env=True
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Refusing env change", result.stderr)
            self.assertEqual(env_file.read_bytes(), original)
            self.assertEqual(len(list(backup_dir.glob("*.backup"))), 1)
            self.assertEqual(source_env.read_bytes(), source_env_original)

    def test_installer_never_rewrites_existing_env_assignments(self):
        installer = INSTALL_SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("replace_env_setting", installer)
        self.assertIn("Existing env values are configuration owned", installer)
        self.assertIn("--exclude '.env'", installer)


class TelegramRollbackSafetyTests(unittest.TestCase):
    def test_git_root_falls_back_to_configured_update_source(self):
        bot = object.__new__(TelegramControlBot)
        source_root = Path("/safe/source")
        bot._find_git_root = Mock(side_effect=[None, source_root])
        with (
            patch("project.services.telegram_bot.config.APP_ROOT", Path("/deployed/no-git")),
            patch("project.services.telegram_bot.config.UPDATE_SOURCE_DIR", source_root),
        ):
            self.assertEqual(bot._git_repository_root(), source_root)

    def test_rollback_deploys_verified_commit_through_hardened_updater(self):
        current = "a" * 40
        target = "b" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            updater = repo / "update_uvjerenja_terminal.sh"
            updater.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

            bot = object.__new__(TelegramControlBot)
            bot._run_git = Mock(
                side_effect=[
                    (True, "true"),
                    (True, "fetched"),
                    (True, target),
                    (True, target),
                ]
            )
            bot._run_process = Mock(return_value=(True, "safe update complete"))

            ok, output, resolved = bot._run_rollback(repo, "HEAD~1", current)

        self.assertTrue(ok, output)
        self.assertEqual(resolved, target)
        command = bot._run_process.call_args.args[0]
        self.assertEqual(command[:3], ["env", f"POTVRDE_UPDATE_TARGET={target}", "bash"])
        self.assertEqual(Path(command[3]), updater)


if __name__ == "__main__":
    unittest.main()
