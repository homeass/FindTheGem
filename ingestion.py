"""
ProteusP Data Ingestion Module
Obsidian Vault 파일 변경 감지 (Watchdog) 및 Git 동기화
"""

import os
import subprocess
import time
from pathlib import Path
from threading import Event, Thread
from typing import Callable, List, Optional

from proteusp.config import ProteusPConfig, get_config


class VaultWatcher:
    """
    Watchdog 기반 Obsidian Vault 파일 변경 감지.
    파일 생성/수정/삭제 이벤트를 감지하여 파이프라인 트리거.
    """

    def __init__(
        self,
        vault_path: str,
        on_change: Optional[Callable] = None,
        debounce_seconds: int = 5,
        recursive: bool = True,
    ):
        self.vault_path = Path(vault_path)
        self.on_change = on_change
        self.debounce_seconds = debounce_seconds
        self.recursive = recursive
        self._observer = None
        self._running = Event()
        self._last_trigger: float = 0
        self._change_queue: set = set()

    def start(self) -> None:
        """Start watching the vault for changes."""
        if not self.vault_path.exists():
            print(f"Warning: Vault path does not exist: {self.vault_path}")
            return

        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class ObsidianHandler(FileSystemEventHandler):
                def __init__(self, watcher):
                    self.watcher = watcher

                def on_modified(self, event):
                    if event.is_directory:
                        return
                    if event.src_path.endswith(".md"):
                        self.watcher._queue_change(event.src_path)

                def on_created(self, event):
                    if event.is_directory:
                        return
                    if event.src_path.endswith(".md"):
                        self.watcher._queue_change(event.src_path)

                def on_deleted(self, event):
                    if event.is_directory:
                        return
                    if event.src_path.endswith(".md"):
                        self.watcher._queue_change(event.src_path)

            self._handler = ObsidianHandler(self)
            self._observer = Observer()
            self._observer.schedule(
                self._handler,
                str(self.vault_path),
                recursive=self.recursive,
            )
            self._running.set()
            self._observer.start()

            # Start debounce thread
            self._debounce_thread = Thread(target=self._debounce_loop, daemon=True)
            self._debounce_thread.start()

            print(f"🔍 Watching Obsidian vault: {self.vault_path}")
            print(f"   Debounce: {self.debounce_seconds}s | Recursive: {self.recursive}")

        except ImportError:
            print("Warning: watchdog not installed. File watching disabled.")
            print("Install: pip install watchdog")
        except Exception as e:
            print(f"Warning: Failed to start file watcher: {e}")

    def _queue_change(self, file_path: str) -> None:
        """Queue a file change event."""
        self._change_queue.add(file_path)
        self._last_trigger = time.time()

    def _debounce_loop(self) -> None:
        """Debounce thread: wait for quiet period then trigger callback."""
        while self._running.is_set():
            time.sleep(0.5)
            if not self._change_queue:
                continue
            quiet_period = time.time() - self._last_trigger
            if quiet_period >= self.debounce_seconds:
                changes = list(self._change_queue)
                self._change_queue.clear()
                if self.on_change:
                    try:
                        self.on_change(changes)
                    except Exception as e:
                        print(f"Error in change callback: {e}")

    def stop(self) -> None:
        """Stop watching."""
        self._running.clear()
        if self._observer:
            self._observer.stop()
            self._observer.join()
            print("File watcher stopped.")


class GitSyncer:
    """
    Git 기반 Obsidian Vault 동기화.
    주기적으로 git pull을 수행하여 원격 변경사항 반영.
    """

    def __init__(
        self,
        local_path: str,
        remote_url: str = "",
        branch: str = "main",
        poll_interval_minutes: int = 5,
    ):
        self.local_path = Path(local_path)
        self.remote_url = remote_url
        self.branch = branch
        self.poll_interval = poll_interval_minutes
        self._running = Event()
        self._thread: Optional[Thread] = None

    def init_git_repo(self) -> bool:
        """Initialize git repo in vault path if not already."""
        git_dir = self.local_path / ".git"
        if git_dir.exists():
            return True

        try:
            subprocess.run(
                ["git", "init"],
                cwd=str(self.local_path),
                capture_output=True,
                timeout=30,
            )
            if self.remote_url:
                subprocess.run(
                    ["git", "remote", "add", "origin", self.remote_url],
                    cwd=str(self.local_path),
                    capture_output=True,
                    timeout=30,
                )
            print(f"Git repo initialized at {self.local_path}")
            return True
        except Exception as e:
            print(f"Warning: Git init failed: {e}")
            return False

    def pull(self) -> List[str]:
        """Pull latest changes from remote. Returns list of changed files."""
        if not self.remote_url:
            return []

        try:
            # Stash local changes first
            subprocess.run(
                ["git", "stash"],
                cwd=str(self.local_path),
                capture_output=True,
                timeout=30,
            )

            # Pull
            result = subprocess.run(
                ["git", "pull", "origin", self.branch],
                cwd=str(self.local_path),
                capture_output=True,
                timeout=60,
            )

            # Get list of changed files
            diff_result = subprocess.run(
                ["git", "diff", "--name-only", "@{1}..@{0}"],
                cwd=str(self.local_path),
                capture_output=True,
                text=True,
                timeout=30,
            )

            changed = [f.strip() for f in diff_result.stdout.split("\n") if f.strip()]
            if changed:
                print(f"Git pull: {len(changed)} files changed")
            return changed

        except Exception as e:
            print(f"Warning: Git pull failed: {e}")
            return []

    def watch(self, on_sync: Optional[Callable] = None) -> None:
        """
        Start periodic git sync loop.
        Calls on_sync(changed_files) when new changes are pulled.
        """
        if not self.remote_url:
            print("Git sync disabled: no remote URL configured")
            return

        self.init_git_repo()
        self._running.set()

        def _loop():
            while self._running.is_set():
                changed = self.pull()
                if changed and on_sync:
                    try:
                        on_sync(changed)
                    except Exception as e:
                        print(f"Error in sync callback: {e}")
                time.sleep(self.poll_interval * 60)

        self._thread = Thread(target=_loop, daemon=True)
        self._thread.start()
        print(f"Git sync enabled: every {self.poll_interval}min from {self.remote_url}")

    def stop(self) -> None:
        """Stop git sync loop."""
        self._running.clear()


def discover_vault_path(config: Optional[ProteusPConfig] = None) -> Optional[str]:
    """
    Auto-discover Obsidian vault location.
    Checks common paths for Termux and desktop environments.
    """
    cfg = config or get_config()
    vault_path = cfg.vault_path

    # Check if configured path exists
    if Path(vault_path).exists():
        return vault_path

    # Common Termux paths
    termux_paths = [
        Path.home() / "storage" / "shared" / "Obsidian",
        Path.home() / "storage" / "shared" / "obsidian",
        Path.home() / "Obsidian",
        Path.home() / "obsidian",
        "/sdcard/Obsidian",
        "/sdcard/obsidian",
        "/storage/emulated/0/Obsidian",
        "/storage/emulated/0/obsidian",
    ]

    for p in termux_paths:
        if p.exists():
            # Could be vault root or parent of vaults
            if list(p.glob("*.md")):
                return str(p)
            # Check subdirectories
            subdirs = [d for d in p.iterdir() if d.is_dir()]
            for sd in subdirs:
                if list(sd.glob("*.md")):
                    return str(sd)

    # Desktop Linux paths
    desktop_paths = [
        Path.home() / "Documents" / "Obsidian",
        Path.home() / "Documents" / "obsidian",
        Path.home() / "Obsidian Vault",
    ]
    for p in desktop_paths:
        if p.exists() and list(p.glob("*.md")):
            return str(p)

    return None
