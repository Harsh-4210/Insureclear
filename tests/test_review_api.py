from test_case_access import access, submit

CHECKS = dict(facts_checked=True, coverage_checked=True, legal_checked=True)


def completed(access):
    store, clients, _ = access
    job_id = submit(clients["alice"]).json()["job_id"]
    sources = {"denial": "The claim was denied because of a treatment exclusion.", "policy": "The policy covers hospital treatment subject to documented exclusions.", "regulatory": ""}
    store.update(job_id, status="completed", result={"appeal_letter": "Please review the claim against the supplied policy wording.", "source_evidence": sources, "regulatory_evidence": {"registry_fingerprint": "fixture"}, "evidence_validation": {"valid": True, "errors": []}, "pipeline_stats": {"final_recommendation": "REVIEW_REQUIRED"}})
    return store, clients, job_id


def test_reviewer_approves_exact_version_and_edit_invalidates_export(access):
    store, clients, job_id = completed(access)
    url = f"/api/jobs/{job_id}/review"
    initial = clients["alice"].get(url)
    assert initial.status_code == 200
    state = initial.json()
    assert state["version"] == 1 and state["status"] == "draft"
    assert clients["alice"].post(url + "/decision", json={"expected_version": 1, "decision": "approved", "checks": CHECKS}).status_code == 403
    approved = clients["reviewer"].post(url + "/decision", json={"expected_version": 1, "decision": "approved", "checks": CHECKS})
    assert approved.status_code == 200 and approved.json()["version"] == 2
    exported = clients["alice"].get(f"/api/jobs/{job_id}/download/approved-letter")
    assert exported.status_code == 200 and exported.text == state["letter"]
    edited = clients["alice"].put(url, json={"expected_version": 2, "letter": "Please reconsider the claim using the supplied policy.", "note": "Clarified request"})
    assert edited.status_code == 200 and edited.json()["status"] == "draft"
    assert clients["alice"].get(f"/api/jobs/{job_id}/download/approved-letter").status_code == 409
    assert clients["reviewer"].post(url + "/decision", json={"expected_version": 2, "decision": "approved", "checks": CHECKS}).status_code == 409


def test_review_routes_deny_cross_owner_org_and_require_csrf(access):
    _, clients, job_id = completed(access)
    for name in ["bob", "outsider"]:
        for path in [f"/api/jobs/{job_id}/review", f"/api/jobs/{job_id}/download/approved-letter"]:
            assert clients[name].get(path).status_code == 404
        assert clients[name].put(f"/api/jobs/{job_id}/review", json={"expected_version": 1, "letter": "Edit"}).status_code == 404
    clients["alice"].headers.pop("X-CSRF-Token")
    assert clients["alice"].put(f"/api/jobs/{job_id}/review", json={"expected_version": 1, "letter": "Edit"}).status_code == 403


def test_invalid_human_letter_can_be_saved_but_cannot_be_approved(access):
    _, clients, job_id = completed(access)
    url = f"/api/jobs/{job_id}/review"
    saved = clients["alice"].put(url, json={"expected_version": 1, "letter": "You must settle this claim within 15 days."})
    assert saved.status_code == 200 and not saved.json()["validation"]["valid"]
    decision = clients["reviewer"].post(url + "/decision", json={"expected_version": 2, "decision": "approved", "checks": CHECKS})
    assert decision.status_code == 422
    assert clients["alice"].get(url).json()["version"] == 2


def test_changed_or_missing_sources_refuse_approval(access):
    store, clients, job_id = completed(access)
    url = f"/api/jobs/{job_id}/review"
    assert clients["alice"].get(url).status_code == 200
    report = store.get(job_id)["result"]
    report["source_evidence"]["policy"] += " Altered wording."
    store.update(job_id, result=report)
    assert clients["reviewer"].post(url + "/decision", json={"expected_version": 1, "decision": "approved", "checks": CHECKS}).status_code == 409
    new_id = submit(clients["alice"]).json()["job_id"]
    store.update(new_id, status="completed", result={"appeal_letter": "Please review this claim."})
    assert clients["reviewer"].post(f"/api/jobs/{new_id}/review/decision", json={"expected_version": 1, "decision": "approved", "checks": CHECKS}).status_code == 422


def test_approval_cannot_validate_one_version_then_approve_a_different_one(access, monkeypatch):
    from web import reviews
    _, clients, job_id = completed(access)
    real_state_for = reviews.state_for
    def racing_state(*args):
        store, old, sources = real_state_for(*args)
        store.edit(job_id, "other-editor", old["version"], "Settle this claim within 15 days.", "Concurrent edit")
        return store, old, sources
    monkeypatch.setattr(reviews, "state_for", racing_state)
    response = clients["reviewer"].post(f"/api/jobs/{job_id}/review/decision", json={"expected_version": 2, "decision": "approved", "checks": CHECKS})
    assert response.status_code == 409


def test_original_validation_failure_requires_explicit_human_revision(access):
    store, clients, job_id = completed(access)
    report = store.get(job_id)["result"]
    report["evidence_validation"] = {"valid": False, "errors": [{"category": "historic_failure"}]}
    store.update(job_id, result=report)
    response = clients["reviewer"].post(f"/api/jobs/{job_id}/review/decision", json={"expected_version": 1, "decision": "approved", "checks": CHECKS})
    assert response.status_code == 422


def test_identical_text_edit_cannot_bypass_original_invalid_guard(access):
    store, clients, job_id = completed(access)
    report = store.get(job_id)["result"]; report["evidence_validation"] = {"valid": False, "errors": [{"category": "historic_failure"}]}
    store.update(job_id, result=report)
    assert clients["alice"].put(f"/api/jobs/{job_id}/review", json={"expected_version": 1, "letter": report["appeal_letter"]}).status_code == 200
    response = clients["reviewer"].post(f"/api/jobs/{job_id}/review/decision", json={"expected_version": 2, "decision": "approved", "checks": CHECKS})
    assert response.status_code == 422
