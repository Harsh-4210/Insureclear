"""Authorized human review, distinct from the model's quality assessment."""
from __future__ import annotations
import hashlib
import json
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, StrictBool, StrictInt
from tools.evidence_validator import validate_appeal_letter
from tools.review_store import ReviewStore, ReviewConflict

router = APIRouter(tags=["reviews"])


def _api():
    from web import api
    return api


def principal(request: Request, x_api_key: str | None = Header(default=None)):
    identity = _api()._authenticate(request, x_api_key)
    if identity.get("legacy"):
        raise HTTPException(403, "Named account required for human review")
    return identity


class Edit(BaseModel):
    letter: str = Field(min_length=1, max_length=50000)
    expected_version: StrictInt = Field(ge=1)
    note: str = Field(default="", max_length=2000)


class Decision(BaseModel):
    expected_version: StrictInt = Field(ge=1)
    decision: str = Field(pattern="^(approved|changes_requested)$")
    note: str = Field(default="", max_length=2000)
    checks: dict[str, StrictBool] = Field(default_factory=dict)


def state_for(job_id, identity):
    job = _api().get_authorized_job(job_id, identity)
    if job["status"] != "completed" or not job.get("result"):
        raise HTTPException(409, "Completed draft required")
    report = job["result"]
    sources = report.get("source_evidence") or {}
    if not isinstance(sources, dict) or not all(isinstance(v, str) for v in sources.values()):
        raise HTTPException(422, "Original evidence snapshot is unavailable")
    fingerprint = hashlib.sha256(json.dumps([sources, report.get("regulatory_evidence", {}).get("registry_fingerprint")], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    store = ReviewStore(_api().job_store.db_path)
    try:
        state = store.initialize(job_id, job["org_id"], report.get("appeal_letter", ""), fingerprint)
    except ReviewConflict as error:
        raise HTTPException(409, str(error)) from None
    return store, state, sources


def decorated(state, sources):
    return {**state, "validation": validate_appeal_letter(state["letter"], sources).as_dict()}


@router.get("/api/jobs/{job_id}/review")
def get_review(job_id: str, identity: dict = Depends(principal)):
    _, state, sources = state_for(job_id, identity)
    return decorated(state, sources)


@router.put("/api/jobs/{job_id}/review")
def edit_review(job_id: str, body: Edit, request: Request, identity: dict = Depends(principal)):
    _api()._mutation(request, identity)
    store, _, sources = state_for(job_id, identity)
    try:
        state = store.edit(job_id, identity["user_id"], body.expected_version, body.letter, body.note)
    except ReviewConflict as error:
        raise HTTPException(409, str(error)) from None
    return decorated(state, sources)


@router.post("/api/jobs/{job_id}/review/decision")
def decide_review(job_id: str, body: Decision, request: Request, identity: dict = Depends(principal)):
    _api()._mutation(request, identity)
    if identity["role"] not in {"reviewer", "admin"}:
        raise HTTPException(403, "Reviewer role required")
    store, current, sources = state_for(job_id, identity)
    if body.expected_version != current["version"]:
        raise HTTPException(409, "Review version changed; refresh before deciding")
    original_report = _api().get_authorized_job(job_id, identity)["result"]
    originally_invalid = original_report.get("evidence_validation", {}).get("valid") is False
    if body.decision == "approved" and originally_invalid and (not any(event["action"] == "edited" for event in current["history"]) or " ".join(current["letter"].split()) == " ".join(current["history"][0]["letter"].split())):
        raise HTTPException(422, "Original validation failure requires an explicit corrected human revision")
    validation = validate_appeal_letter(current["letter"], sources)
    if body.decision == "approved" and not validation.valid:
        raise HTTPException(422, detail={"message": "Correct evidence issues before approving", "validation": validation.as_dict()})
    try:
        state = store.decide(job_id, identity["user_id"], body.expected_version, body.decision, body.note, body.checks)
    except ReviewConflict as error:
        raise HTTPException(409, str(error)) from None
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    return decorated(state, sources)


@router.get("/api/jobs/{job_id}/download/approved-letter")
def approved_letter(job_id: str, identity: dict = Depends(principal)):
    _, state, sources = state_for(job_id, identity)
    approval = state.get("approval")
    if state["status"] != "approved" or not approval or approval["letter_sha256"] != state["letter_sha256"] or approval["version"] != state["version"]:
        raise HTTPException(409, "Current draft has no human approval")
    if not validate_appeal_letter(state["letter"], sources).valid:
        raise HTTPException(422, "Current draft fails evidence validation")
    return PlainTextResponse(state["letter"], headers={"Cache-Control": "no-store", "Content-Disposition": f"attachment; filename=approved-letter-v{state['version']}.txt"})
