from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, Field, ValidationError, field_validator

from config import get_gemini_api_key, get_gemini_model
from errors import AnalyzeError, gemini_client_error_to_analyze_error

SYSTEM_PROMPT = """You are an expert SRE performing root cause analysis on a production incident.

You will receive numbered evidence items (logs and metrics) collected around the incident window.
Each evidence item has a stable numeric ID. You MUST cite only IDs that appear in the evidence list.

Propose up to 3 ranked likely root causes (rank 1 = most likely).
For each cause provide:
- rank: integer starting at 1
- summary: concise root cause hypothesis
- evidence_ids: list of supporting evidence item IDs from the provided list
- justification: one sentence explaining how the cited evidence supports the hypothesis

Respond ONLY with JSON matching the required schema. Do not invent evidence IDs."""


class RootCause(BaseModel):
    rank: int = Field(ge=1, le=3)
    summary: str
    evidence_ids: list[int] = Field(min_length=1)
    justification: str


class RcaReport(BaseModel):
    causes: list[RootCause] = Field(min_length=1, max_length=3)

    @field_validator("causes")
    @classmethod
    def ranks_must_be_unique_and_sequential(cls, causes: list[RootCause]) -> list[RootCause]:
        ranks = [cause.rank for cause in causes]
        if len(set(ranks)) != len(ranks):
            raise ValueError("cause ranks must be unique")
        return causes


def _format_evidence_for_prompt(evidence: dict[str, Any]) -> str:
    lines = [
        f"Incident ID: {evidence['incident_id']}",
        f"Trigger: {evidence['trigger_type']}",
        f"Started: {evidence['incident_started_at']}",
        f"Ended: {evidence.get('incident_ended_at')}",
        f"Window: {evidence['window_start']} to {evidence['window_end']}",
        f"Total evidence items in window: {evidence['total_items']}",
        f"Evidence items provided (sampled={evidence['sampled']}): {evidence['returned_items']}",
        "",
        "Evidence items:",
    ]
    for item in evidence["items"]:
        if item["source"] == "logs":
            detail = (
                f"level={item['level']} message={item['message']!r} "
                f"trace_id={item.get('trace_id')}"
            )
        else:
            detail = f"metric={item['metric_name']} value={item['value']}"
        lines.append(
            f"  [{item['id']}] {item['timestamp']} {item['service']} "
            f"{item['source']} {detail}"
        )
    return "\n".join(lines)


def _validate_cited_ids(report: RcaReport, allowed_ids: set[int]) -> None:
    for cause in report.causes:
        invalid = [eid for eid in cause.evidence_ids if eid not in allowed_ids]
        if invalid:
            raise ValueError(
                f"cause rank {cause.rank} cites unknown evidence IDs: {invalid}. "
                f"Allowed IDs: {sorted(allowed_ids)}"
            )


def _call_gemini(prompt: str, validation_error: str | None = None) -> str:
    api_key = get_gemini_api_key()
    if not api_key:
        raise AnalyzeError(
            message=(
                "GEMINI_API_KEY is not set. Add it to services/telemetry/.env "
                "or export it in the environment before calling /analyze."
            ),
            status_code=503,
            error_type="missing_api_key",
        )

    model = get_gemini_model()
    client = genai.Client(api_key=api_key)
    user_prompt = prompt
    if validation_error:
        user_prompt += (
            "\n\nYour previous response failed validation. Fix it.\n"
            f"Validation error: {validation_error}\n"
            "Return valid JSON only."
        )

    try:
        response = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=RcaReport,
                temperature=0.2,
            ),
        )
    except genai_errors.ClientError as exc:
        raise gemini_client_error_to_analyze_error(exc) from exc
    except Exception as exc:
        raise AnalyzeError(
            message=f"Unexpected Gemini SDK error: {exc}",
            status_code=502,
            error_type="gemini_sdk_error",
        ) from exc

    text = response.text
    if not text:
        raise AnalyzeError(
            message="Gemini returned an empty response",
            status_code=502,
            error_type="empty_gemini_response",
        )
    return text


def analyze_incident(evidence: dict[str, Any]) -> RcaReport:
    allowed_ids = {item["id"] for item in evidence["items"]}
    prompt = _format_evidence_for_prompt(evidence)

    last_error: str | None = None
    for attempt in range(2):
        raw = _call_gemini(prompt, validation_error=last_error)
        try:
            report = RcaReport.model_validate_json(raw)
            _validate_cited_ids(report, allowed_ids)
            return report
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)
            if attempt == 1:
                raise AnalyzeError(
                    message=f"Gemini RCA response failed validation: {last_error}",
                    status_code=502,
                    error_type="rca_validation_error",
                ) from exc

    raise AnalyzeError(
        message="Gemini RCA analysis failed",
        status_code=502,
        error_type="rca_analysis_failed",
    )


def join_cited_evidence(
    report: RcaReport,
    evidence_index: dict[int, dict],
) -> dict[str, Any]:
    causes_with_evidence = []
    all_cited: dict[int, dict] = {}

    for cause in report.causes:
        items = []
        for eid in cause.evidence_ids:
            item = evidence_index.get(eid)
            if item is None:
                continue
            items.append(item)
            all_cited[eid] = item
        causes_with_evidence.append(
            {
                "rank": cause.rank,
                "summary": cause.summary,
                "evidence_ids": cause.evidence_ids,
                "justification": cause.justification,
                "evidence": items,
            }
        )

    return {
        "causes": causes_with_evidence,
        "all_cited_evidence": list(all_cited.values()),
    }
