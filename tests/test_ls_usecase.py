from pathlib import Path

from gpt_oss_hackathon.adapters.fs_adapter import LocalFSAdapter
from gpt_oss_hackathon.adapters.llm_adapter import OpenAIAdapter
from gpt_oss_hackathon.usecases import LsUseCase


def test_ls_local_tmpdir(tmp_path: Path):
    # create files
    d = tmp_path / "sub"
    d.mkdir()
    _ = (d / "a.txt").write_text("x")
    _ = (d / "b.txt").write_text("y")

    llm = OpenAIAdapter()  # will fallback to simple parser when no API key
    fs = LocalFSAdapter(base_path=str(tmp_path))
    uc = LsUseCase(llm, fs)

    res = uc.execute("ls sub")
    assert res.path.endswith("/sub") or res.path.endswith("\\sub")
    assert set(res.entries) == {"a.txt", "b.txt"}
