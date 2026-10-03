"""
Cross-process file lock — prevents duplicate concurrent pipeline or digest executions.
"""
from __future__ import annotations

import os
import sys
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ProcessFileLock:
    """
    Cross-process non-blocking file lock.
    Uses msvcrt on Windows and fcntl on Unix/Linux/macOS.
    """

    def __init__(self, lock_filename: str):
        self.lock_path = os.path.abspath(lock_filename)
        self._file_obj: Any = None
        self._is_locked: bool = False

    def acquire(self) -> bool:
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
        try:
            self._file_obj = open(self.lock_path, "a+")
            if sys.platform == "win32":
                import msvcrt
                # Lock 1 byte at position 0 without blocking (LK_NBLCK)
                self._file_obj.seek(0)
                msvcrt.locking(self._file_obj.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._file_obj.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            self._is_locked = True
            logger.debug("process_lock_acquired path=%s", self.lock_path)
            return True
        except (IOError, OSError) as exc:
            logger.warning("process_lock_busy path=%s err=%s", self.lock_path, exc)
            if self._file_obj:
                try:
                    self._file_obj.close()
                except Exception:
                    pass
                self._file_obj = None
            self._is_locked = False
            return False

    def release(self) -> None:
        if not self._is_locked or not self._file_obj:
            return
        try:
            if sys.platform == "win32":
                import msvcrt
                self._file_obj.seek(0)
                msvcrt.locking(self._file_obj.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._file_obj.fileno(), fcntl.LOCK_UN)
            self._file_obj.close()
        except Exception as exc:
            logger.debug("process_lock_release_error err=%s", exc)
        finally:
            self._file_obj = None
            self._is_locked = False
            logger.debug("process_lock_released path=%s", self.lock_path)

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
