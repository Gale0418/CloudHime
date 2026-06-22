import pytest

from cloudhime_workers import OCRWorker


def make_worker_stub():
    worker = OCRWorker.__new__(OCRWorker)
    worker.refresh_count = 0

    def refresh_registry():
        worker.refresh_count += 1

    worker._refresh_translation_registry = refresh_registry
    return worker


def test_set_local_gemma_params_rejects_non_numeric_values():
    worker = make_worker_stub()

    with pytest.raises((TypeError, ValueError)):
        OCRWorker.set_local_gemma_params(worker, None, 1.15)


@pytest.mark.parametrize(
    ("temperature", "repeat_penalty"),
    [
        (-0.1, 1.15),
        (1.1, 1.15),
        (0.2, 0.9),
        (0.2, 2.1),
    ],
)
def test_set_local_gemma_params_rejects_out_of_range_values(temperature, repeat_penalty):
    worker = make_worker_stub()

    with pytest.raises(ValueError):
        OCRWorker.set_local_gemma_params(worker, temperature, repeat_penalty)


def test_set_local_gemma_params_accepts_valid_values_and_refreshes_registry():
    worker = make_worker_stub()

    OCRWorker.set_local_gemma_params(worker, 0.2, 1.15)

    assert worker.local_gemma_temperature == 0.2
    assert worker.local_gemma_repeat_penalty == 1.15
    assert worker.refresh_count == 1
