"""Tests for cross-process ProcessFileLock."""
import os
import pytest
from app.locks import ProcessFileLock


def test_process_file_lock_acquisition_and_concurrency(tmp_path):
    lock_file = str(tmp_path / "test.lock")

    lock1 = ProcessFileLock(lock_file)
    lock2 = ProcessFileLock(lock_file)

    # First lock acquires successfully
    assert lock1.acquire() is True

    # Second lock fails to acquire because lock1 holds it
    assert lock2.acquire() is False

    # Releasing lock1 allows lock2 to acquire
    lock1.release()
    assert lock2.acquire() is True
    lock2.release()
