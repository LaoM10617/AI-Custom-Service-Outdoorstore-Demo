"""Never let offline checks read or modify an operator's uploaded library."""
import pytest


@pytest.fixture(autouse=True)
def isolated_library(tmp_path, monkeypatch):
    monkeypatch.setenv("AIROBOT_LIBRARY_DIR", str(tmp_path / "library"))
