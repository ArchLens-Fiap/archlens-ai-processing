import pytest

from app.prompts.loader import load_prompt


class TestPromptLoader:
    def test_load_system_prompt(self):
        text = load_prompt("system")
        assert isinstance(text, str)
        assert len(text) > 0

    def test_load_analysis_prompt(self):
        text = load_prompt("analysis")
        assert isinstance(text, str)
        assert len(text) > 0

    def test_load_chat_prompt(self):
        text = load_prompt("chat")
        assert isinstance(text, str)
        assert len(text) > 0

    def test_load_schema_json(self):
        text = load_prompt("schema")
        assert isinstance(text, str)
        assert len(text) > 0

    def test_load_nonexistent_prompt_raises(self):
        # Clear lru_cache for this test
        load_prompt.cache_clear()
        with pytest.raises(FileNotFoundError, match="Prompt not found"):
            load_prompt("nonexistent_prompt_xyz")
