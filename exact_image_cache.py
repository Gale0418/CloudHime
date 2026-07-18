from __future__ import annotations

import copy
from collections import OrderedDict
from dataclasses import dataclass, fields, is_dataclass
import sys
import threading
from typing import Any, Hashable, Iterable
import zlib

import numpy as np


DEFAULT_MAX_ENTRIES = 4
DEFAULT_MAX_BYTES = 32 * 1024 * 1024


def _deep_size(value: Any, seen: set[int] | None = None) -> int:
    """Return a conservative deep size without counting an object twice."""
    if seen is None:
        seen = set()

    object_id = id(value)
    if object_id in seen:
        return 0
    seen.add(object_id)

    size = sys.getsizeof(value, 0)
    if isinstance(value, np.ndarray):
        buffer_bytes = int(value.nbytes)
        size = max(size, buffer_bytes) if value.flags.owndata else size + buffer_bytes
        if value.dtype.hasobject:
            size += sum(_deep_size(item, seen) for item in value.flat)
        return size
    if is_dataclass(value) and not isinstance(value, type):
        return size + sum(
            _deep_size(getattr(value, field.name), seen) for field in fields(value)
        )
    if isinstance(value, dict):
        return size + sum(
            _deep_size(key, seen) + _deep_size(item, seen)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return size + sum(_deep_size(item, seen) for item in value)
    if isinstance(value, (bytes, str)):
        return size

    attributes = getattr(value, "__dict__", None)
    if attributes is not None:
        size += _deep_size(attributes, seen)
    for owner in type(value).__mro__:
        slots = owner.__dict__.get("__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for slot in slots:
            if slot in {"__dict__", "__weakref__"}:
                continue
            try:
                slot_value = getattr(value, slot)
            except AttributeError:
                continue
            size += _deep_size(slot_value, seen)
    return size


@dataclass(frozen=True)
class ExactImageCachePayload:
    results: tuple[Any, ...]
    provider: Any
    state_token: Any


@dataclass(frozen=True)
class _CacheKey:
    shape: tuple[int, ...]
    dtype: str
    nbytes: int
    context: Hashable
    fingerprint: int


@dataclass(frozen=True)
class _Entry:
    image_snapshot: np.ndarray
    results: tuple[Any, ...]
    provider: Any
    state_token: Any
    nbytes: int
    retained_bytes: int


class ExactImageCache:
    def __init__(
        self,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")

        self._max_entries = int(max_entries)
        self._max_bytes = int(max_bytes)
        self._entries: OrderedDict[_CacheKey, _Entry] = OrderedDict()
        self._total_bytes = 0
        self._lock = threading.RLock()

    @staticmethod
    def _fingerprint(image: np.ndarray) -> int:
        """Return a fast content fingerprint for a C-contiguous array."""
        return zlib.crc32(memoryview(image).cast("B")) & 0xFFFFFFFF

    @staticmethod
    def _normalize_image(image: np.ndarray) -> np.ndarray:
        array = np.asarray(image)
        return np.ascontiguousarray(array)

    @classmethod
    def _freeze_context(cls, context: Any) -> Hashable:
        if context is None or isinstance(context, (bool, int, str, bytes)):
            return (type(context).__name__, context)
        if isinstance(context, float):
            return (type(context).__name__, repr(context))
        if isinstance(context, np.generic):
            return (
                "numpy-scalar",
                context.dtype.str,
                cls._freeze_context(context.item()),
            )
        if isinstance(context, np.ndarray):
            normalized = np.ascontiguousarray(context)
            if normalized.dtype.hasobject:
                raise TypeError("Object arrays are not supported as cache contexts")
            return (
                "numpy-array",
                normalized.shape,
                normalized.dtype.str,
                bytes(memoryview(normalized).cast("B")),
            )
        if isinstance(context, dict):
            items = [
                (cls._freeze_context(key), cls._freeze_context(value))
                for key, value in context.items()
            ]
            return ("dict", tuple(sorted(items, key=repr)))
        if isinstance(context, (list, tuple)):
            return (type(context).__name__, tuple(cls._freeze_context(item) for item in context))
        if isinstance(context, (set, frozenset)):
            values = tuple(sorted((cls._freeze_context(item) for item in context), key=repr))
            return (type(context).__name__, values)

        raise TypeError(
            "Unsupported cache context type: "
            f"{type(context).__module__}.{type(context).__qualname__}"
        )

    def _make_key(self, image: np.ndarray, context: Any) -> _CacheKey:
        return _CacheKey(
            shape=tuple(int(dimension) for dimension in image.shape),
            dtype=image.dtype.str,
            nbytes=int(image.nbytes),
            context=self._freeze_context(context),
            fingerprint=int(self._fingerprint(image)),
        )

    @staticmethod
    def _copy_results(results: Iterable[Any]) -> tuple[Any, ...]:
        return tuple(copy.deepcopy(result) for result in results)

    @staticmethod
    def _copy_payload(entry: _Entry) -> ExactImageCachePayload:
        return ExactImageCachePayload(
            results=ExactImageCache._copy_results(entry.results),
            provider=copy.deepcopy(entry.provider),
            state_token=copy.deepcopy(entry.state_token),
        )

    @staticmethod
    def _retained_size(
        key: _CacheKey,
        image: np.ndarray,
        results: tuple[Any, ...],
        provider: Any,
        state_token: Any,
    ) -> int:
        seen: set[int] = set()
        return sum(
            _deep_size(value, seen)
            for value in (key, image, results, provider, state_token)
        )

    def _evict_for_insert(self, retained_bytes: int) -> None:
        while self._entries and (
            len(self._entries) + 1 > self._max_entries
            or self._total_bytes + retained_bytes > self._max_bytes
        ):
            _, entry = self._entries.popitem(last=False)
            self._total_bytes -= entry.retained_bytes

    def get(self, image: np.ndarray, context: Any) -> ExactImageCachePayload | None:
        with self._lock:
            normalized = self._normalize_image(image)
            key = self._make_key(normalized, context)
            entry = self._entries.get(key)
            if entry is None or not np.array_equal(normalized, entry.image_snapshot):
                return None

            self._entries.move_to_end(key)
            return self._copy_payload(entry)

    def put(
        self,
        image: np.ndarray,
        context: Any,
        results: Iterable[Any],
        provider: Any,
        state_token: Any,
    ) -> bool:
        with self._lock:
            normalized = self._normalize_image(image)
            if _deep_size(normalized) > self._max_bytes:
                return False

            copied_results = self._copy_results(results)
            copied_provider = copy.deepcopy(provider)
            copied_state_token = copy.deepcopy(state_token)
            key = self._make_key(normalized, context)
            retained_bytes = self._retained_size(
                key,
                normalized,
                copied_results,
                copied_provider,
                copied_state_token,
            )
            if retained_bytes > self._max_bytes:
                return False

            previous = self._entries.pop(key, None)
            if previous is not None:
                self._total_bytes -= previous.retained_bytes
            self._evict_for_insert(retained_bytes)

            snapshot = np.array(normalized, copy=True, order="C")
            snapshot.setflags(write=False)
            entry = _Entry(
                image_snapshot=snapshot,
                results=copied_results,
                provider=copied_provider,
                state_token=copied_state_token,
                nbytes=int(normalized.nbytes),
                retained_bytes=retained_bytes,
            )
            self._entries[key] = entry
            self._total_bytes += entry.retained_bytes
            return True

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._total_bytes = 0

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    @property
    def total_bytes(self) -> int:
        with self._lock:
            return self._total_bytes
