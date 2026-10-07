"""main.py 的最小自检：JSON 提取与 CSV 输出。"""

import csv
from pathlib import Path

from main import apply_env_overrides, extract_json, load_dotenv, run


def test_load_dotenv(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('# comment\nLLM_BASE_URL="https://api.x.com/v1"\nLLM_API_KEY=sk-123\nBADLINE\n', encoding="utf-8")
    env = load_dotenv(env_file)
    assert env == {"LLM_BASE_URL": "https://api.x.com/v1", "LLM_API_KEY": "sk-123"}


def test_apply_env_overrides(tmp_path):
    config = {"llm_server": {"base_url": "http://localhost:11434/v1", "model": "llama3.2:3b"}}
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_BASE_URL=https://api.x.com/v1\nLLM_MODEL=deepseek-chat\n", encoding="utf-8")
    apply_env_overrides(config, env_file)
    assert config["llm_server"]["base_url"] == "https://api.x.com/v1"
    assert config["llm_server"]["model"] == "deepseek-chat"
    assert "api_key" not in config["llm_server"]  # 未提供则不覆盖


def test_extract_json_code_block():
    assert extract_json('```json\n{"category_matched": "public", "brief_explanation": "ok"}\n```') == {
        "category_matched": "public",
        "brief_explanation": "ok",
    }


def test_extract_json_bare_object():
    assert extract_json('prefix {"a": 1} suffix') == {"a": 1}


def test_run_writes_csv(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("hello", encoding="utf-8")

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**_):
                    return FakeResponse()

    class FakeResponse:
        def __init__(self):
            msg = '```json\n{"category_matched": "internal", "brief_explanation": "note"}\n```'
            self.choices = [type("C", (), {"message": type("M", (), {"content": msg})()})()]

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "llm_server:\n  base_url: http://x\n  model: m\n"
        "agent_settings:\n  agent_instructions: i\n  prompt: p\n  response_categories: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("main.OpenAI", lambda **_: FakeClient())
    out_csv = tmp_path / "out.csv"
    results = run(tmp_path / "docs", config_path, out_csv)

    assert results == [{"file_name": "a.md", "category_matched": "internal", "brief_explanation": "note", "error": ""}]
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert len(rows) == 1 and rows[0]["category_matched"] == "internal"
