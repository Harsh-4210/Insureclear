import os
from pathlib import Path
import shutil
import subprocess
import sys


def test_bundled_registry_survives_existing_mutable_data_volume(tmp_path):
    project = Path(__file__).resolve().parents[1]
    image = tmp_path / "image"
    (image / "tools").mkdir(parents=True)
    for filename in ("regulatory_registry.py", "document_context.py"):
        shutil.copyfile(project / "tools" / filename, image / "tools" / filename)
    (image / "tools" / "__init__.py").write_text("")
    # Simulate an old mounted data volume: it has jobs but no newly bundled corpus.
    (image / "data").mkdir()
    (image / "data" / "existing-jobs.txt").write_text("previous persisted jobs")
    corpus = project / "resources" / "regulatory"
    if corpus.exists():
        shutil.copytree(corpus, image / "resources" / "regulatory")
    else:
        # Reproduce the image layout before the fix; /app/data is masked by volume.
        (image / "resources").mkdir()
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run([sys.executable, "-B", "-c", "from tools.regulatory_registry import load_registry; r=load_registry(); print(len(r.sources),len(r.clauses))"], cwd=image, env=env, capture_output=True, text=True, timeout=15, creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "3 9"
    assert (image / "data" / "existing-jobs.txt").read_text() == "previous persisted jobs"
