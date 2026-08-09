"""Adapter seam: OpenAI-compatible LlmJudge / LlmCvTailor and default wiring (ADR-0015)."""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from job_finding_assistant.candidate_snapshot import CandidateSnapshot
from job_finding_assistant.fakes import FakeLlmCvTailor, FakeLlmJudge
from job_finding_assistant.llm_runtime import (
    DEFAULT_LLM_MODEL,
    LlmUnavailableError,
    OpenAiCompatibleLlmClient,
    OpenAiCompatibleLlmCvTailor,
    OpenAiCompatibleLlmJudge,
    UnavailableLlmCvTailor,
    UnavailableLlmJudge,
    build_llm_ports,
    load_llm_runtime_config,
)
from job_finding_assistant.match_assessment import EvidencePair
from job_finding_assistant.web.app import build_default_assistant


def _snapshot() -> CandidateSnapshot:
    return CandidateSnapshot(
        contact="Ada Lovelace",
        education=["BSc Math"],
        experience=["Engineer at Analytical"],
        projects=["Difference Engine"],
        skills_tools=["Python"],
    )


def _chat_response(payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {"message": {"content": json.dumps(payload)}},
            ]
        },
    )


def test_openai_client_default_timeout_is_thirty_seconds() -> None:
    client = OpenAiCompatibleLlmClient(api_key="sk-test")
    assert client._timeout == 30.0
    assert client._http.timeout.read == 30.0
    client.close()


def test_provider_timeout_maps_to_llm_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        raise httpx.TimeoutException("read timed out", request=None)

    judge = OpenAiCompatibleLlmJudge(
        OpenAiCompatibleLlmClient(
            api_key="sk-test",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    )
    with pytest.raises(LlmUnavailableError) as err:
        judge.judge_relevance(
            job_detail_fields={"title": "SWE"},
            candidate_snapshot=_snapshot(),
        )
    assert err.value.reason == "LLM Unavailable: provider timed out"


def test_missing_api_key_config_is_unavailable() -> None:
    with patch.dict(os.environ, {}, clear=True):
        config = load_llm_runtime_config()
    assert config.api_key is None
    assert config.model == DEFAULT_LLM_MODEL
    assert config.base_url.endswith("/v1")


def test_env_overrides_base_url_and_model() -> None:
    config = load_llm_runtime_config(
        {
            "JOB_FINDING_ASSISTANT_LLM_API_KEY": "secret-key",
            "JOB_FINDING_ASSISTANT_LLM_BASE_URL": "https://example.test/v1",
            "JOB_FINDING_ASSISTANT_LLM_MODEL": "my-model",
        }
    )
    assert config.api_key == "secret-key"
    assert config.base_url == "https://example.test/v1"
    assert config.model == "my-model"


def test_build_llm_ports_without_key_are_unavailable_not_fake() -> None:
    judge, tailor = build_llm_ports(api_key=None)
    assert isinstance(judge, UnavailableLlmJudge)
    assert isinstance(tailor, UnavailableLlmCvTailor)
    assert not isinstance(judge, FakeLlmJudge)
    assert not isinstance(tailor, FakeLlmCvTailor)
    assert judge.available() is False
    assert tailor.available() is False
    assert judge.unavailable_reason() == "LLM Unavailable: API key not configured"
    assert tailor.unavailable_reason() == "LLM Unavailable: API key not configured"


def test_build_default_assistant_never_wires_fake_llm(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("JOB_FINDING_ASSISTANT_LLM_API_KEY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    captured: list[object] = []

    def tracking_build_llm_ports(**kwargs: object) -> tuple[object, object]:
        ports = build_llm_ports(**kwargs)  # type: ignore[arg-type]
        captured.extend(ports)
        return ports

    monkeypatch.setattr(
        "job_finding_assistant.web.app.build_llm_ports",
        tracking_build_llm_ports,
    )
    assistant = build_default_assistant(db_path=tmp_path / "catalog.db")
    assert len(captured) == 2
    assert isinstance(captured[0], UnavailableLlmJudge)
    assert isinstance(captured[1], UnavailableLlmCvTailor)
    assert not isinstance(captured[0], FakeLlmJudge)
    assert not isinstance(captured[1], FakeLlmCvTailor)
    assert assistant.get_llm_unavailable_reason() == (
        "LLM Unavailable: API key not configured"
    )


def test_build_default_assistant_uses_live_ports_when_key_present(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JOB_FINDING_ASSISTANT_LLM_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("HOME", str(tmp_path))
    captured: list[object] = []

    def tracking_build_llm_ports(**kwargs: object) -> tuple[object, object]:
        ports = build_llm_ports(**kwargs)  # type: ignore[arg-type]
        captured.extend(ports)
        return ports

    monkeypatch.setattr(
        "job_finding_assistant.web.app.build_llm_ports",
        tracking_build_llm_ports,
    )
    assistant = build_default_assistant(db_path=tmp_path / "catalog.db")
    assert isinstance(captured[0], OpenAiCompatibleLlmJudge)
    assert isinstance(captured[1], OpenAiCompatibleLlmCvTailor)
    assert assistant.get_llm_unavailable_reason() is None


def test_hard_constraint_judge_parses_provider_json_and_isolates_inputs() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content.decode())
        return _chat_response(
            {
                "outcome": "fail",
                "reason": "Must be Hong Kong — posting requires London",
                "evidence": [
                    {
                        "job_excerpt": "London on-site",
                        "candidate_excerpt": "Must be Hong Kong",
                        "role": "contradicts Hard Constraint",
                    }
                ],
            }
        )

    client = OpenAiCompatibleLlmClient(
        api_key="sk-test",
        base_url="https://example.test/v1",
        model="gpt-test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    judge = OpenAiCompatibleLlmJudge(client)
    result = judge.judge_hard_constraint(
        hard_constraints_text="Must be Hong Kong",
        job_detail_fields={"title": "Engineer", "location": "London on-site"},
    )

    assert result.outcome == "fail"
    assert "Hong Kong" in result.reason
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-test"
    assert captured["body"]["model"] == "gpt-test"
    user = captured["body"]["messages"][1]["content"]
    assert "Must be Hong Kong" in user
    assert "London on-site" in user
    assert "Preferences" not in user
    assert "Candidate Snapshot" not in user
    assert "Master CV" not in user


def test_preference_judge_never_sends_cv() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return _chat_response(
            {
                "preference": "Strong",
                "reason": "Remote matches top preference",
                "evidence": [],
            }
        )

    judge = OpenAiCompatibleLlmJudge(
        OpenAiCompatibleLlmClient(
            api_key="sk-test",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    )
    result = judge.judge_preference(
        preferences_text="Prefer remote",
        job_detail_fields={"title": "SWE", "location": "Remote"},
    )
    assert result.preference == "Strong"
    user = captured["body"]["messages"][1]["content"]
    assert "Prefer remote" in user
    assert "Candidate Snapshot" not in user
    assert "Master CV" not in user


def test_relevance_judge_never_sends_preferences() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return _chat_response(
            {
                "relevance": "Mixed",
                "evidence": [
                    {
                        "job_excerpt": "Python required",
                        "candidate_excerpt": "Python",
                        "role": "supports Relevance",
                    }
                ],
            }
        )

    judge = OpenAiCompatibleLlmJudge(
        OpenAiCompatibleLlmClient(
            api_key="sk-test",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    )
    result = judge.judge_relevance(
        job_detail_fields={"title": "SWE", "description": "Python required"},
        candidate_snapshot=_snapshot(),
    )
    assert result.relevance == "Mixed"
    assert len(result.evidence) == 1
    user = captured["body"]["messages"][1]["content"]
    assert "Candidate Snapshot" in user
    assert "Preferences" not in user


def test_provider_http_error_is_llm_unavailable_without_leaking_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(401, text="invalid sk-abcdef1234567890token")

    judge = OpenAiCompatibleLlmJudge(
        OpenAiCompatibleLlmClient(
            api_key="sk-abcdef1234567890token",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    )
    with pytest.raises(LlmUnavailableError) as err:
        judge.judge_relevance(
            job_detail_fields={"title": "SWE"},
            candidate_snapshot=_snapshot(),
        )
    assert "LLM Unavailable" in err.value.reason
    assert "sk-abcdef" not in err.value.reason
    assert "sk-abcdef" not in str(err.value)


def test_tailor_parses_packet_and_omits_preferences_from_request() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return _chat_response(
            {
                "gap_report": {
                    "items": [
                        {
                            "requirement": "Kubernetes",
                            "status": "missing",
                            "evidence": "not found",
                            "suggestion": "Learn k8s basics before applying",
                        }
                    ]
                },
                "edit_summary": {
                    "omissions": ["Dropped unrelated club bullet"],
                    "section_order": [],
                    "cross_role_chronology": [],
                    "summary_rewrite": [],
                    "pin_notes": [],
                    "material_rephrases": [],
                },
                "tailored_yaml": "cv:\n  name: Ada\n  sections: {}\n",
            }
        )

    tailor = OpenAiCompatibleLlmCvTailor(
        OpenAiCompatibleLlmClient(
            api_key="sk-test",
            model="shared-model",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    )
    result = tailor.tailor(
        master_cv_yaml="cv:\n  name: Ada\n  sections: {}\n",
        candidate_snapshot=_snapshot(),
        job_detail_fields={"title": "SRE", "description": "Kubernetes"},
        relevance_evidence=[
            EvidencePair(
                job_excerpt="Kubernetes",
                candidate_excerpt="not found",
                role="weakens Relevance",
            )
        ],
        hard_constraint_outcome="pass",
        hard_constraint_reason="No hard constraint violations",
    )

    assert result.gap_report.items[0].requirement == "Kubernetes"
    assert result.edit_summary.omissions == ("Dropped unrelated club bullet",)
    assert "name: Ada" in result.tailored_yaml
    assert captured["body"]["model"] == "shared-model"
    user = captured["body"]["messages"][1]["content"]
    assert "Master CV YAML" in user
    assert "Preferences" not in user


def test_judge_and_tailor_share_one_model_from_build_llm_ports() -> None:
    models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        models.append(body["model"])
        path = str(request.url)
        if "chat/completions" in path and len(models) == 1:
            return _chat_response(
                {
                    "relevance": "Strong",
                    "evidence": [
                        {
                            "job_excerpt": "Python",
                            "candidate_excerpt": "Python",
                            "role": "supports Relevance",
                        }
                    ],
                }
            )
        return _chat_response(
            {
                "gap_report": {"items": []},
                "edit_summary": {
                    "omissions": [],
                    "section_order": [],
                    "cross_role_chronology": [],
                    "summary_rewrite": [],
                    "pin_notes": [],
                    "material_rephrases": [],
                },
                "tailored_yaml": "cv:\n  name: Ada\n",
            }
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    judge, tailor = build_llm_ports(
        api_key="sk-test",
        model="one-model",
        http_client=http,
    )
    judge.judge_relevance(
        job_detail_fields={"title": "SWE"},
        candidate_snapshot=_snapshot(),
    )
    tailor.tailor(
        master_cv_yaml="cv:\n  name: Ada\n",
        candidate_snapshot=_snapshot(),
        job_detail_fields={"title": "SWE"},
        relevance_evidence=[],
        hard_constraint_outcome="unknown",
        hard_constraint_reason="empty",
    )
    assert models == ["one-model", "one-model"]
