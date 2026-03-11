from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "v1"


@lru_cache(maxsize=10)
def load_prompt(name: str) -> str:
    file_path = PROMPTS_DIR / f"{name}.md"
    if not file_path.exists():
        json_path = PROMPTS_DIR / f"{name}.json"
        if json_path.exists():
            return json_path.read_text(encoding="utf-8")
        raise FileNotFoundError(f"Prompt not found: {name}")
    return file_path.read_text(encoding="utf-8")
