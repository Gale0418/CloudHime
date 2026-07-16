from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

from exact_image_cache import ExactImageCache, ExactImageCachePayload, _deep_size


def image(value=0, shape=(2, 2, 3)):
    return np.full(shape, value, dtype=np.uint8)


def retained_size(source, context, results, provider, state_token):
    probe = ExactImageCache(max_bytes=10_000_000)
    assert probe.put(source, context, results, provider, state_token)
    return probe.total_bytes


def test_exact_hit_returns_payload():
    cache = ExactImageCache()
    source = image(1)

    assert cache.put(source, "ocr", ["text"], "provider-a", "state-1")
    payload = cache.get(source, "ocr")

    assert isinstance(payload, ExactImageCachePayload)
    assert payload.results == ("text",)
    assert payload.provider == "provider-a"
    assert payload.state_token == "state-1"


def test_one_pixel_difference_is_a_miss():
    cache = ExactImageCache()
    source = image(1)
    changed = source.copy()
    changed[0, 0, 0] = 2

    cache.put(source, "ocr", ["text"], "provider-a", "state-1")

    assert cache.get(changed, "ocr") is None


def test_forced_crc_collision_is_verified_by_array_equal(monkeypatch):
    cache = ExactImageCache()
    monkeypatch.setattr(cache, "_fingerprint", lambda candidate: 1234)
    first = image(1)
    second = image(2)

    cache.put(first, "ocr", ["first"], "provider-a", "state-1")

    assert cache.get(second, "ocr") is None
    assert cache.put(second, "ocr", ["second"], "provider-b", "state-2")
    assert cache.get(first, "ocr") is None
    assert cache.get(second, "ocr").results == ("second",)


def test_context_isolation():
    cache = ExactImageCache()
    source = image(1)

    cache.put(source, "context-a", ["a"], "provider-a", "state-a")

    assert cache.get(source, "context-b") is None
    assert cache.get(source, "context-a").results == ("a",)


def test_lru_entry_eviction():
    cache = ExactImageCache(max_entries=4, max_bytes=4096)
    sources = [image(value, shape=(1, 1, 1)) for value in range(5)]

    for value, source in enumerate(sources[:4]):
        assert cache.put(source, "ocr", [value], "provider", value)
    assert cache.get(sources[0], "ocr") is not None
    assert cache.put(sources[4], "ocr", [4], "provider", 4)

    assert len(cache) == 4
    assert cache.get(sources[1], "ocr") is None
    assert cache.get(sources[0], "ocr") is not None


def test_retained_bytes_include_metadata_and_respect_budget():
    source = image(1)
    budget = 1_000_000
    cache = ExactImageCache(max_bytes=budget)

    assert cache.put(
        source,
        {"mode": ["ocr", "metadata"]},
        [{"boxes": [1, 2, 3], "text": "payload"}],
        {"name": ["provider"]},
        {"version": [1]},
    )

    assert cache.total_bytes > source.nbytes
    assert cache.total_bytes <= budget
    assert cache._entries[next(iter(cache._entries))].retained_bytes == cache.total_bytes


def test_large_metadata_can_evict_or_skip_without_corrupting_bookkeeping():
    source = image(1, shape=(2, 2, 1))
    large_results = [{"text": "x" * 4096}]
    small_size = retained_size(source, "ocr", [1], "provider", 1)
    large_size = retained_size(source, "ocr-large", large_results, "provider", 1)
    assert large_size > small_size

    eviction_cache = ExactImageCache(max_entries=4, max_bytes=large_size)
    assert eviction_cache.put(source, "ocr", [1], "provider", 1)
    assert eviction_cache.put(source, "ocr-large", large_results, "provider", 1)
    assert len(eviction_cache) == 1
    assert eviction_cache.total_bytes == large_size
    assert eviction_cache.get(source, "ocr") is None
    assert eviction_cache.get(source, "ocr-large") is not None

    skip_cache = ExactImageCache(max_entries=4, max_bytes=small_size)
    assert skip_cache.put(source, "ocr", [1], "provider", 1)
    assert not skip_cache.put(source, "ocr-large", large_results, "provider", 1)
    assert len(skip_cache) == 1
    assert skip_cache.total_bytes == small_size
    assert skip_cache.get(source, "ocr") is not None


def test_replacement_updates_retained_bytes_once():
    source = image(1, shape=(2, 2, 1))
    old_results = ["old"]
    new_results = [{"text": "x" * 4096}]
    old_size = retained_size(source, "ocr", old_results, "provider", 1)
    new_size = retained_size(source, "ocr", new_results, "provider", 1)
    assert new_size > old_size

    cache = ExactImageCache(max_bytes=new_size)
    assert cache.put(source, "ocr", old_results, "provider", 1)
    assert cache.put(source, "ocr", new_results, "provider", 1)

    assert len(cache) == 1
    assert cache.total_bytes == new_size
    assert cache.get(source, "ocr").results == tuple(new_results)


def test_cyclic_payload_is_copied_and_sized_without_recursion_error():
    results = {"self": None}
    results["self"] = results
    provider = {"nested": []}
    provider["nested"].append(provider)
    state_token = ["state"]
    state_token.append(state_token)

    cache = ExactImageCache(max_bytes=1_000_000)
    source = image(1)
    assert cache.put(source, "ocr", [results], provider, state_token)

    payload = cache.get(source, "ocr")
    assert payload.results[0]["self"] is payload.results[0]
    assert payload.provider["nested"][0] is payload.provider
    assert payload.state_token[1] is payload.state_token
    assert cache.total_bytes > source.nbytes


@dataclass
class _MetadataBox:
    values: list[Any]


def test_deep_size_handles_dataclasses_and_shared_cycles():
    box = _MetadataBox(values=[])
    box.values.append(box)

    size = _deep_size(box)

    assert size >= len(box.values)


def test_byte_eviction_and_oversize_skip():
    first = image(1, shape=(2, 2, 1))
    second = image(2, shape=(2, 2, 1))
    single_size = retained_size(first, "ocr", [1], "provider", 1)
    cache = ExactImageCache(max_entries=4, max_bytes=(single_size * 2) - 1)

    assert cache.put(first, "ocr", [1], "provider", 1)
    assert cache.put(second, "ocr", [2], "provider", 2)
    assert cache.total_bytes == single_size
    assert cache.get(first, "ocr") is None
    assert cache.get(second, "ocr") is not None

    oversize = image(3, shape=(32, 32, 2))
    assert not cache.put(oversize, "ocr", [3], "provider", 3)
    assert len(cache) == 1
    assert cache.total_bytes == single_size


def test_non_contiguous_input_is_normalized():
    cache = ExactImageCache()
    source = image(1, shape=(4, 4, 3))
    non_contiguous = source[::2, :, :]

    cache.put(non_contiguous, "ocr", ["text"], "provider", "state")

    assert not non_contiguous.flags.c_contiguous
    assert cache.get(non_contiguous, "ocr").results == ("text",)


def test_result_provider_and_state_mutation_isolation():
    cache = ExactImageCache()
    source = image(1)
    results = [{"boxes": [1]}]
    provider = {"name": ["provider"]}
    state_token = {"version": [1]}

    cache.put(source, "ocr", results, provider, state_token)
    results[0]["boxes"].append(2)
    provider["name"].append("changed")
    state_token["version"].append(2)

    first = cache.get(source, "ocr")
    first.results[0]["boxes"].append(3)
    first.provider["name"].append("changed-again")
    first.state_token["version"].append(3)
    second = cache.get(source, "ocr")

    assert second.results == ({"boxes": [1]},)
    assert second.provider == {"name": ["provider"]}
    assert second.state_token == {"version": [1]}
    with pytest.raises(Exception):
        first.results = ()


def test_clear_resets_entries_and_bytes():
    cache = ExactImageCache()
    cache.put(image(1), "ocr", ["text"], "provider", "state")

    cache.clear()

    assert len(cache) == 0
    assert cache.total_bytes == 0
    assert cache.get(image(1), "ocr") is None
