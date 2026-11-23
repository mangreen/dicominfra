"""推論契約 v0.1 草案的 schema 測試：範例必須通過，常見的錯誤輸入必須被拒絕。"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

CONTRACT_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "inference-v0"


def _load(relative: str) -> Any:
    return json.loads((CONTRACT_DIR / relative).read_text(encoding="utf-8"))


def _validator(schema_file: str) -> Draft202012Validator:
    schema = _load(schema_file)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


REQUEST = _validator("request.schema.json")
RESULT = _validator("result.schema.json")


def test_examples_are_valid() -> None:
    assert not list(REQUEST.iter_errors(_load("examples/request.json")))
    assert not list(RESULT.iter_errors(_load("examples/result.succeeded.json")))
    assert not list(RESULT.iter_errors(_load("examples/result.failed.json")))


def _mutate_request(**changes: Any) -> dict[str, Any]:
    doc = copy.deepcopy(_load("examples/request.json"))
    doc.update(changes)
    return doc  # type: ignore[no-any-return]


@pytest.mark.parametrize(
    "changes",
    [
        {"request_id": "not-a-uuid"},
        {"modality": "ct"},
        {"inputs": []},
        {"submitted_at": "yesterday"},
        {"unexpected": 1},
        {"contract_version": "0.2"},
    ],
)
def test_invalid_requests_are_rejected(changes: dict[str, Any]) -> None:
    assert list(REQUEST.iter_errors(_mutate_request(**changes)))


def _mutate_result(base: str, **changes: Any) -> dict[str, Any]:
    doc = copy.deepcopy(_load(base))
    doc.update(changes)
    return doc  # type: ignore[no-any-return]


def test_measurement_value_must_be_decimal_string_not_float() -> None:
    doc = _mutate_result(
        "examples/result.succeeded.json",
        measurements=[{"name": "lesion_diameter", "value": 12.5, "unit": "mm"}],
    )
    assert list(RESULT.iter_errors(doc))


def test_succeeded_result_requires_measurements_and_forbids_error() -> None:
    missing = _load("examples/result.succeeded.json")
    del missing["measurements"]
    assert list(RESULT.iter_errors(missing))

    with_error = _mutate_result(
        "examples/result.succeeded.json",
        error={"code": "X", "message": "m", "retryable": False},
    )
    assert list(RESULT.iter_errors(with_error))


def test_failed_result_requires_error_and_forbids_measurements() -> None:
    missing = _load("examples/result.failed.json")
    del missing["error"]
    assert list(RESULT.iter_errors(missing))

    with_measurements = _mutate_result(
        "examples/result.failed.json",
        measurements=[{"name": "n", "value": "1", "unit": "mm"}],
    )
    assert list(RESULT.iter_errors(with_measurements))
