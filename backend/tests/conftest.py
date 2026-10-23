import pytest

@pytest.fixture(autouse=True)
def isolated_usage_ledger(tmp_path,monkeypatch):
    monkeypatch.setenv('AI_USAGE_DB',str(tmp_path/'usage.db'))

    monkeypatch.setenv('AI_PROVIDER','openai')
