import pytest

from tools import io_utils


@pytest.mark.parametrize("case_id", ["..", "../outside", "nested/case", "nested\\case"])
def test_checkpoint_paths_reject_case_ids_outside_the_session_namespace(monkeypatch, tmp_path, case_id):
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    (tmp_path / "sessions").mkdir(exist_ok=True)
    with pytest.raises(ValueError, match="case_id"):
        io_utils.get_checkpoint_path(case_id, "auditor")
