"""Field-parity checks between backend/api.py Pydantic request models and the
plain dataclasses agent/ exposes as their "mirror" (SearchParams, RagAskParams,
IngestRequest). These dataclasses exist specifically so agent/ stays
FastAPI-free; nothing enforces that the two sides stay in sync when someone
adds a field to one but forgets the other. This test is that enforcement.

Run with:
    pytest tests/test_contract_parity.py -v
"""
from __future__ import annotations

import dataclasses

import pytest

# Pydantic request models live in backend.api
from backend.api import (
    IngestRequest as PydanticIngestRequest,
    PaperSearchRequest,
    RagAskRequest,
)

from agent.search.state import SearchParams
from agent.rag.agent import RagAskParams
from agent.rag.ingest import IngestRequest as DataclassIngestRequest


def _dataclass_field_names(dc: type) -> set[str]:
    return {f.name for f in dataclasses.fields(dc)}


def _pydantic_field_names(model: type) -> set[str]:
    return set(model.model_fields.keys())


@pytest.mark.parametrize(
    "pydantic_model, dataclass_model, pydantic_only, dataclass_only",
    [
        # `config_path` selects which agent.config.Config to build (resolved
        # before run_search is called, never passed through SearchParams).
        # `record_memory_events` is an internal server-side switch, not a
        # public request field.
        (PaperSearchRequest, SearchParams, {"config_path"}, {"record_memory_events"}),
        # `config_path` follows the same "resolved before the dataclass is
        # built" pattern as above. `history` is present on both sides but
        # gets converted from list[ChatMessageModel] to list[dict] in transit.
        (RagAskRequest, RagAskParams, {"config_path"}, set()),
        # `config_path` again resolves Config before IngestRequest is built.
        (PydanticIngestRequest, DataclassIngestRequest, {"config_path"}, set()),
    ],
)
def test_request_dataclass_field_parity(pydantic_model, dataclass_model, pydantic_only, dataclass_only):
    pydantic_fields = _pydantic_field_names(pydantic_model)
    dataclass_fields = _dataclass_field_names(dataclass_model)

    missing_in_dataclass = pydantic_fields - dataclass_fields - pydantic_only
    missing_in_pydantic = dataclass_fields - pydantic_fields - dataclass_only

    assert not missing_in_dataclass, (
        f"{pydantic_model.__name__} has fields not mirrored in {dataclass_model.__name__}: "
        f"{missing_in_dataclass}. Either map them when constructing {dataclass_model.__name__} "
        f"in backend/api.py, or add them to the `pydantic_only` allowlist if intentionally unused."
    )
    assert not missing_in_pydantic, (
        f"{dataclass_model.__name__} has fields backend/api.py never sets from "
        f"{pydantic_model.__name__}: {missing_in_pydantic}. The agent field can never be "
        f"influenced by an HTTP request as written."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
