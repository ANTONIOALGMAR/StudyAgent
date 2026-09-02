import functools
import glob
import logging
import os
import threading
from contextlib import contextmanager
from signal import SIGINT, SIGTERM, getsignal, signal

from .files import (
    _create_lock,
    create_file_racefree,
    create_lock,
    make_lock_path,
    remove_lock,
    wait_for_lock,
)
from .paths import mkabs

PID = os.getpid()
READ = f"read-{PID}"
READ_GLOB = "read-*"
WRITE = "write"
UNIVERSAL = "universal"
LOCK_PREFIX = "lock"

_LOGGER = logging.getLogger(__name__)


class ThreeLocker(object):
    """
    A class to lock files for reading and writing.

    It uses a three-lock system, with separate read-lock, write-lock, and
    universal-lock (or lock-lock). The universal lock is used to lock the locks,
    to prevent race conditions between read and write locks. It allows multiple
    simultaneous readers, as long as there is no writer.
    It creates lock files in the same directory as the file to be locked.

    Warning:
        These locks are NOT re-entrant. If a process already holds a lock on a
        file and tries to acquire the same lock again, it will deadlock (wait
        forever for itself to release the lock). Do not nest lock contexts on
        the same file.
    """

    def __init__(self, filepath: str, wait_max: int = 10, strict_ro_locks: bool = False):
        self.wait_max = wait_max
        self.strict_ro_locks = strict_ro_locks
        self.set_file_path(filepath)
        self.locked = {READ: False, WRITE: False}

    @property
    def filepath(self) -> str:
        return self._filepath

    def set_file_path(self, filepath: str) -> str:
        if filepath:
            self._filepath = mkabs(filepath)
            self.lock_paths = make_all_lock_paths(self.filepath)
        else:
            self._filepath = None
            self.lock_paths = None

        return self._filepath

    def read_lock(self) -> bool:
        if not self.filepath:
            _LOGGER.warning("No filepath, no need to lock.")
            return True
        lock_path = self.lock_paths[READ]
        if not ensure_write_access(lock_path, self.strict_ro_locks):
            return False

        self.create_read_lock(self.filepath, self.wait_max)
        self.locked[READ] = True
        return True

    def write_lock(self) -> bool:
        if not self.filepath:
            _LOGGER.warning("No filepath, no need to lock.")
            return True

        lock_path = self.lock_paths[WRITE]
        if not ensure_write_access(lock_path, self.strict_ro_locks):
            # for writing, just fail anyway
            raise OSError(f"No write access to '{lock_path}'; can't lock file.")
        self.create_write_lock(self.filepath, self.wait_max)
        self.locked[READ] = True
        self.locked[WRITE] = True
        return True

    def read_unlock(self) -> bool:
        if not self.filepath:
            _LOGGER.warning("No filepath, no need to unlock.")
            return True
        if self.locked[WRITE]:
            raise RuntimeError("Cannot read_unlock while write lock is held; use write_unlock()")
        _remove_lock(self.lock_paths[READ])
        self.locked[READ] = False
        return True

    def write_unlock(self) -> bool:
        if not self.filepath:
            _LOGGER.warning("No filepath, no need to unlock.")
            return True
        _remove_lock(self.lock_paths[WRITE])
        _remove_lock(self.lock_paths[READ])
        self.locked[WRITE] = False
        self.locked[READ] = False
        return True

    def create_read_lock(self, filepath: str = None, wait_max: int = None) -> None:
        """Securely create a read lock file.

        Args:
            filepath: path to a file to lock
            wait_max: max wait time if the file in question is already locked
        """
        filepath = self.filepath if filepath is None else filepath
        wait_max = self.wait_max if wait_max is None else wait_max
        wait_for_lock(self.lock_paths[UNIVERSAL], wait_max)
        _create_lock(self.lock_paths[UNIVERSAL], filepath, wait_max)
        wait_for_lock(self.lock_paths[WRITE], wait_max)
        _create_lock(self.lock_paths[READ], filepath, wait_max)
        _remove_lock(self.lock_paths[UNIVERSAL])

    def create_write_lock(self, filepath: str = None, wait_max: int = None) -> None:
        """Securely create a write lock file.

        Args:
            filepath: path to a file to lock
            wait_max: max wait time if the file in question is already locked
        """
        filepath = self.filepath if filepath is None else filepath
        wait_max = self.wait_max if wait_max is None else wait_max
        wait_for_lock(self.lock_paths[UNIVERSAL], wait_max)
        _create_lock(self.lock_paths[UNIVERSAL], filepath, wait_max)
        read_lock_paths = glob.glob(
            self.lock_paths[READ_GLOB]
        )  # must occur after universal lock is set
        all_lock_paths = read_lock_paths + [self.lock_paths[WRITE]]
        wait_for_locks(all_lock_paths, wait_max)
        _create_lock(self.lock_paths[READ], filepath, wait_max)
        _create_lock(self.lock_paths[WRITE], filepath, wait_max)
        _remove_lock(self.lock_paths[UNIVERSAL])

    def _interrupt_handler(self, signal_received, frame):
        if signal_received in (SIGINT, SIGTERM):
            _LOGGER.warning(f"Received {signal_received.name}, unlocking file and exiting...")
            self.write_unlock()
            raise SystemExit

    def __repr__(self) -> str:
        settings_dict = {
            "filepath": self.filepath,
            "wait_max": self.wait_max,
            "locked": self.locked,
            "strict_ro_locks": self.strict_ro_locks,
        }

        return f"{type(self).__name__}({settings_dict})"

    def __del__(self) -> None:
        if self.filepath:
            if self.locked[WRITE]:
                self.write_unlock()
            if self.locked[READ]:
                self.read_unlock()


def ensure_locked(lock_type: str = WRITE):  # decorator factory
    """Decorator to apply to functions to make sure they only happen when locked."""

    def decorator(func):
        @functools.wraps(func)
        def inner_func(self, *args, **kwargs):
            if not self.locker:
                raise OSError("File not lockable. File locker not provided.")
            if not self.locker.locked[lock_type]:
                raise OSError(
                    f"This function must use a context manager to {lock_type}-lock the file"
                )

            return func(self, *args, **kwargs)

        return inner_func

    return decorator


@contextmanager
def read_lock(obj: object) -> object:
    """Read-lock a filepath or object with locker attribute.

    Args:
        obj: filepath string or object with locker attribute

    Yields:
        object: the locked object

    Warning:
        Locks are NOT re-entrant. Do not nest lock contexts on the same file,
        or the process will deadlock waiting for itself::

            # WRONG - will deadlock:
            with read_lock(cfg):
                with read_lock(cfg):  # Deadlock!
                    ...

            # RIGHT - lock once at the top level:
            with read_lock(cfg):
                do_work(cfg)  # Pass already-locked object
    """
    if isinstance(obj, str):
        locker = ThreeLocker(obj)
    elif hasattr(obj, "locker"):
        locker = obj.locker
    else:
        raise AttributeError(f"Cannot lock: {obj}.")

    # handle a premature Ctrl+C exit from this context manager
    prev_sigterm = None
    prev_sigint = None
    if threading.current_thread() is threading.main_thread():
        prev_sigterm = getsignal(SIGTERM)
        prev_sigint = getsignal(SIGINT)
        signal(SIGTERM, locker._interrupt_handler)
        signal(SIGINT, locker._interrupt_handler)

    locker.read_lock()

    try:
        yield obj
    finally:
        locker.read_unlock()
        if prev_sigterm is not None:
            try:
                signal(SIGTERM, prev_sigterm)
                signal(SIGINT, prev_sigint)
            except ValueError:
                pass


@contextmanager
def write_lock(obj: object) -> object:
    """Write-lock file path or object with locker attribute.

    Args:
        obj: filepath string or object with locker attribute

    Yields:
        object: the locked object

    Warning:
        Locks are NOT re-entrant. Do not nest lock contexts on the same file,
        or the process will deadlock waiting for itself::

            # WRONG - will deadlock:
            with write_lock(cfg):
                with write_lock(cfg):  # Deadlock!
                    cfg.write()

            # RIGHT - lock once at the top level:
            with write_lock(cfg):
                do_work_and_write(cfg)  # Don't re-lock inside
    """
    if isinstance(obj, str):
        locker = ThreeLocker(obj)
    elif hasattr(obj, "locker"):
        locker = obj.locker
    else:
        raise AttributeError(f"Cannot lock: {obj}.")

    # handle a premature Ctrl+C exit from this context manager
    prev_sigterm = None
    prev_sigint = None
    if threading.current_thread() is threading.main_thread():
        prev_sigterm = getsignal(SIGTERM)
        prev_sigint = getsignal(SIGINT)
        signal(SIGTERM, locker._interrupt_handler)
        signal(SIGINT, locker._interrupt_handler)

    locker.write_lock()
    try:
        yield obj
    finally:
        locker.write_unlock()
        if prev_sigterm is not None:
            try:
                signal(SIGTERM, prev_sigterm)
                signal(SIGINT, prev_sigint)
            except ValueError:
                pass


def locked_read_file(filepath: str, create_file: bool = False) -> str:
    """Read a file contents into memory after locking the file.

    This will prevent other ThreeLocker-protected processes from writing to the
    file while it is being read.

    Args:
        filepath: path to the file that should be read
        create_file: whether to create the file if it doesn't exist

    Returns:
        str: file contents
    """
    if os.path.exists(filepath):
        with read_lock(filepath), open(filepath, "r") as file:
            file_contents = file.read()
    elif create_file:
        _LOGGER.info("File does not exist, but create_file is true. Creating...")
        file_contents = ""
        create_file_racefree(filepath)
    else:
        raise FileNotFoundError(f"No such file: {filepath}")
    return file_contents


def wait_for_locks(lock_paths: list | str, wait_max: int = 10):
    """Wait for lock files to be removed.

    Args:
        lock_paths: path to a file to lock
        wait_max: max wait time if the file in question is already locked
    """
    if not isinstance(lock_paths, list):
        lock_paths = [lock_paths]
    for lock_path in lock_paths:
        wait_for_lock(lock_path, wait_max)


def ensure_write_access(lock_path: str, strict_ro_locks: bool = False) -> bool:
    if os.access(os.path.dirname(lock_path), os.W_OK):  # write access
        return True
    else:
        if strict_ro_locks:  # fail; no write access, strict mode
            raise OSError(f"No write access to '{lock_path}'; can't lock file.")
        else:  # warn; no write access, non-strict mode
            _LOGGER.warning(f"No write access to '{lock_path}'; can't lock file.")
            return False


def _remove_lock(lock_path: str) -> bool:
    """Remove lock.

    Args:
        lock_path: path to the lock file to remove. Not the path to the actual file!

    Returns:
        bool: whether the lock was found and removed
    """
    _LOGGER.debug(f"Removing lock at {os.path.basename(lock_path)}")
    try:
        os.remove(lock_path)
        return True
    except FileNotFoundError:
        return False


def make_all_lock_paths(filepath: str) -> dict[str, str]:
    """
    Create a collection of paths to lock files with given name as base.
    """
    lock_paths = {}
    for type in [READ, WRITE, UNIVERSAL, READ_GLOB]:
        prefix = f"{LOCK_PREFIX}-{type}-" if type else LOCK_PREFIX
        base, name = os.path.split(filepath)
        lock_name = name if name.startswith(prefix) else prefix + name
        lock_paths[type] = lock_name if not base else os.path.join(base, lock_name)
    return lock_paths


class OneLocker:
    """A simple mutual-exclusion file locker.

    Uses a single lock file for exclusive access. Unlike ThreeLocker,
    this does not distinguish between read and write locks — any lock
    is exclusive. Simpler and sufficient when concurrent readers are
    not needed.
    """

    def __init__(self, filepath: str, wait_max: int = 10, strict_ro_locks: bool = False):
        self.wait_max = wait_max
        self.strict_ro_locks = strict_ro_locks
        self.set_file_path(filepath)
        self.locked = {READ: False, WRITE: False}

    @property
    def filepath(self) -> str:
        return self._filepath

    def set_file_path(self, filepath: str) -> str:
        if filepath:
            self._filepath = mkabs(filepath)
            self.lock_path = make_lock_path(self.filepath)
        else:
            self._filepath = None
            self.lock_path = None
        return self._filepath

    def read_lock(self) -> bool:
        return self._lock()

    def write_lock(self) -> bool:
        return self._lock()

    def read_unlock(self) -> bool:
        return self._unlock()

    def write_unlock(self) -> bool:
        return self._unlock()

    def _lock(self) -> bool:
        if not self.filepath:
            _LOGGER.warning("No filepath, no need to lock.")
            return True
        if not ensure_write_access(self.lock_path, self.strict_ro_locks):
            return False
        create_lock(self.filepath, self.wait_max)
        self.locked[READ] = True
        self.locked[WRITE] = True
        return True

    def _unlock(self) -> bool:
        if not self.filepath:
            _LOGGER.warning("No filepath, no need to unlock.")
            return True
        remove_lock(self.filepath)
        self.locked[READ] = False
        self.locked[WRITE] = False
        return True

    def _interrupt_handler(self, signal_received, frame):
        if signal_received in (SIGINT, SIGTERM):
            _LOGGER.warning(f"Received {signal_received.name}, unlocking file and exiting...")
            self._unlock()
            raise SystemExit

    def __enter__(self):
        self._lock()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.locked[READ] or self.locked[WRITE]:
            self._unlock()
        return False

    def __repr__(self) -> str:
        return f"{type(self).__name__}({{'filepath': {self.filepath!r}, 'wait_max': {self.wait_max}, 'locked': {self.locked}, 'strict_ro_locks': {self.strict_ro_locks}}})"

    def __del__(self) -> None:
        if self.filepath and (self.locked[READ] or self.locked[WRITE]):
            self._unlock()
