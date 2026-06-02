from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path("config.toml")


@dataclass(frozen=True)
class Config:
    openalex_email: str | None = None
    llm_provider: str = "openai"  # openai|gemini
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    if not path.exists():
        return Config()

    try:
        import tomllib  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    openalex = data.get("openalex", {}) if isinstance(data, dict) else {}
    llm = data.get("llm", {}) if isinstance(data, dict) else {}
    openai = data.get("openai", {}) if isinstance(data, dict) else {}
    gemini = data.get("gemini", {}) if isinstance(data, dict) else {}
    return Config(
        openalex_email=(openalex.get("email") or None),
        llm_provider=llm.get("provider", "openai"),
        openai_model=openai.get("model", "gpt-4.1-mini"),
        openai_base_url=openai.get("base_url"),
        gemini_model=gemini.get("model", "gemini-2.5-flash"),
        gemini_base_url=gemini.get("base_url", "https://generativelanguage.googleapis.com/v1beta"),
    )


def write_default_config(path: Path = DEFAULT_CONFIG_PATH) -> bool:
    if path.exists():
        return False
    path.write_text(
        """# Cấu hình paper-agent

[openalex]
# OpenAlex khuyến nghị gửi email trong User-Agent để liên hệ khi cần.
email = ""

[llm]
# openai hoặc gemini
provider = "openai"

[openai]
# Dùng cho các tool dịch/tóm tắt (tuỳ chọn).
# Thiết lập OPENAI_API_KEY trong env.
model = "gpt-4.1-mini"
# base_url = "https://api.openai.com/v1"

[gemini]
# Thiết lập GEMINI_API_KEY trong env.
model = "gemini-2.5-flash"
base_url = "https://generativelanguage.googleapis.com/v1beta"
""",
        encoding="utf-8",
    )
    return True
