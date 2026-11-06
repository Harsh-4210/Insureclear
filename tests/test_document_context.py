import pytest

from tools.document_context import chunk_document, estimate_tokens, select_context, fit_document_prompt, source_marker


def test_chunks_preserve_unicode_source_slices_and_terminate():
    text = ("भारतीय बीमा policy words.\n" * 30) + "X" * 400
    chunks = chunk_document(text, "policy", chunk_units=100, overlap_units=12)
    assert chunks
    assert chunks[0].start == 0 and chunks[-1].end == len(text)
    assert all(c.text == text[c.start:c.end] for c in chunks)
    assert all(0 < estimate_tokens(c.text) <= 100 for c in chunks)
    assert [c.id for c in chunks] == [c.id for c in chunk_document(text, "policy", 100, 12)]
    assert all(b.start > a.start and b.start <= a.end for a, b in zip(chunks, chunks[1:]))


@pytest.mark.parametrize("size,overlap", [(0,0), (10,10), (10,-1)])
def test_invalid_chunk_budgets_fail_explicitly(size, overlap):
    with pytest.raises(ValueError):
        chunk_document("some text", "policy", size, overlap)


def test_short_sources_are_complete_and_coverage_is_explicit():
    context = select_context({"denial": "Claim denied under Clause 8.7.", "policy": "Clause 8.7 does not exclude this procedure."}, "8.7", 2000)
    assert "Clause 8.7 does not exclude this procedure." in context.text
    assert not context.as_dict()["requires_manual_review"]
    assert all(s["full_document_included"] for s in context.as_dict()["sources"].values())


def test_retrieves_late_exact_clause_without_losing_negation():
    policy = "Ordinary repeated heading and generic policy terms.\n" * 200
    policy += "\nClause 8.7: This procedure is not excluded from cover.\n"
    policy += "End matter. " * 120
    context = select_context({"policy": policy}, "Claim denied under Clause 8.7", 3000)
    assert "This procedure is not excluded from cover." in context.text
    assert estimate_tokens(context.text) <= 3000
    coverage = context.as_dict()
    assert coverage["requires_manual_review"]
    assert coverage["sources"]["policy"]["omitted_chunk_ids"]
    assert not coverage["sources"]["policy"]["full_document_included"]


def test_whole_prompt_bound_includes_scaffolding_system_and_output(monkeypatch):
    monkeypatch.setenv("INSURECLEAR_PROMPT_BUDGET", "5000")
    source = "Word " * 4000 + "Clause 9.4 excludes cosmetic treatment."
    template = "Review policy:\n" + source_marker("policy") + "\nReturn JSON."
    prompt, coverage = fit_document_prompt(template, "System instructions.", {"policy": source}, "9.4", 1000)
    assert "Clause 9.4 excludes cosmetic treatment." in prompt
    assert estimate_tokens(prompt) + estimate_tokens("System instructions.") + 1000 + 512 <= 5000
    assert coverage["budget_method"] == "utf8_byte_upper_bound"
    assert coverage["requires_manual_review"]


def test_impossible_prompt_budget_fails_instead_of_silent_truncation(monkeypatch):
    monkeypatch.setenv("INSURECLEAR_PROMPT_BUDGET", "100")
    with pytest.raises(ValueError, match="budget"):
        fit_document_prompt(source_marker("policy"), "system", {"policy": "meaningful source"}, "", 1000)


def test_repeated_clause_query_features_do_not_multiply_per_chunk_work(monkeypatch):
    from tools import document_context
    real_search = document_context.re.search
    calls = []
    def counted(*args, **kwargs):
        calls.append(1)
        return real_search(*args, **kwargs)
    monkeypatch.setattr(document_context.re, "search", counted)
    source = "Ordinary policy paragraph and coverage terms. " * 1000 + "Clause 4.2 applies."
    context = select_context({"policy": source}, "Clause 4.2 " * 200, 3000)
    assert "Clause 4.2 applies." in context.text
    assert len(calls) < 500, "Repeating one query reference must not cause repeated searches per chunk"
