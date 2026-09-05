"""Small Windows DPAPI-backed secret store for user-scoped CloudHime secrets."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import os
import tempfile
from pathlib import Path


class SecretStoreError(RuntimeError):
    """Raised when a secret cannot be protected, restored, or persisted."""


DEFAULT_SECRET_DESCRIPTION = "CloudHime secret"


if os.name == "nt":
    class _DataBlob(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
        ]


def _blob_from_bytes(value: bytes):
    if not value:
        buffer = ctypes.create_string_buffer(1)
        return _DataBlob(0, ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer
    buffer = ctypes.create_string_buffer(value)
    return _DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer


def _blob_bytes(blob) -> bytes:
    if not blob.cbData or not blob.pbData:
        return b""
    return ctypes.string_at(blob.pbData, blob.cbData)

def _atomic_write(path: Path, payload: bytes, prefix: str) -> None:
    temp_path = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=str(path.parent), prefix=prefix, suffix=".tmp")
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception as exc:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        # Do not expose arbitrary filesystem exception text: callers may use
        # secret-derived paths or mocked exceptions containing secret values.
        raise SecretStoreError("could not write secret store") from None


def _protect(value: bytes, description: str = DEFAULT_SECRET_DESCRIPTION) -> bytes:
    if os.name != "nt":
        raise SecretStoreError("Windows DPAPI is unavailable on this platform")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    protect = crypt32.CryptProtectData
    protect.argtypes = [
        ctypes.POINTER(_DataBlob), wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(_DataBlob),
    ]
    protect.restype = wintypes.BOOL
    local_free = kernel32.LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p
    source, source_buffer = _blob_from_bytes(value)
    result = _DataBlob()
    description = str(description or DEFAULT_SECRET_DESCRIPTION).strip() or DEFAULT_SECRET_DESCRIPTION
    if not protect(ctypes.byref(source), description, None, None, None, 0, ctypes.byref(result)):
        raise SecretStoreError(f"CryptProtectData failed: {ctypes.get_last_error()}")
    try:
        return _blob_bytes(result)
    finally:
        local_free(result.pbData)


def _unprotect(value: bytes) -> bytes:
    if os.name != "nt":
        raise SecretStoreError("Windows DPAPI is unavailable on this platform")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    unprotect = crypt32.CryptUnprotectData
    unprotect.argtypes = [
        ctypes.POINTER(_DataBlob), ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(_DataBlob),
    ]
    unprotect.restype = wintypes.BOOL
    local_free = kernel32.LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p
    source, source_buffer = _blob_from_bytes(value)
    result = _DataBlob()
    description = wintypes.LPWSTR()
    if not unprotect(ctypes.byref(source), ctypes.byref(description), None, None, None, 0, ctypes.byref(result)):
        raise SecretStoreError(f"CryptUnprotectData failed: {ctypes.get_last_error()}")
    try:
        return _blob_bytes(result)
    finally:
        local_free(result.pbData)
        if description:
            local_free(description)


class SecretStore:
    """Persist one user-scoped secret as DPAPI ciphertext, never plaintext."""

    _MIGRATION_MARKER = b"legacy-sources-disabled-v1\n"

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        description: str = DEFAULT_SECRET_DESCRIPTION,
    ):
        self.path = Path(path)
        self.description = str(description or DEFAULT_SECRET_DESCRIPTION).strip() or DEFAULT_SECRET_DESCRIPTION

    @property
    def migration_marker_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".state")

    def legacy_sources_disabled(self) -> bool:
        try:
            return self.migration_marker_path.read_bytes() == self._MIGRATION_MARKER
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise SecretStoreError("could not read secret migration state") from None

    def mark_legacy_sources_disabled(self) -> None:
        _atomic_write(
            self.migration_marker_path,
            self._MIGRATION_MARKER,
            ".cloudhime-secret-state-",
        )

    def get(self) -> str:
        try:
            encrypted = self.path.read_bytes()
        except FileNotFoundError:
            return ""
        except OSError:
            raise SecretStoreError("could not read secret store") from None
        try:
            return _unprotect(encrypted).decode("utf-8")
        except (OSError, UnicodeError, SecretStoreError):
            raise SecretStoreError("could not read secret store") from None

    def set(self, value: str) -> None:
        normalized = str(value or "").strip()
        if not normalized:
            self.delete()
            return
        try:
            encrypted = _protect(normalized.encode("utf-8"), description=self.description)
        except SecretStoreError as exc:
            # Preserve the established platform/DPAPI error category without
            # forwarding arbitrary exception text that could contain a key.
            detail = str(exc)
            if detail.startswith(("Windows DPAPI is unavailable", "CryptProtectData failed:")):
                raise SecretStoreError(detail) from None
            raise SecretStoreError("could not protect secret") from None
        except Exception:
            raise SecretStoreError("could not protect secret") from None
        _atomic_write(self.path, encrypted, ".cloudhime-secret-")

    def delete(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            return
        except OSError:
            raise SecretStoreError("could not remove secret store") from None
