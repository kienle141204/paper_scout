from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path("config.toml")


@dataclass(frozen=True)
class Config:
    openalex_email: str | None = None
    llm_provider: str = "openai"  # openai|gemini
    # Standard tier: chat, parse-query (needs accuracy)
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: str | None = None
    # Cheap tier: translate, summarize (mechanical tasks)
    openai_cheap_model: str = "gpt-4.1-nano"
    # Premium tier: paper analyze/visual (complex HTML output, cached)
    openai_analysis_model: str = "gpt-4.1"
    gemini_model: str = "gemini-2.5-flash"
    gemini_cheap_model: str = "gemini-2.0-flash-lite"
    gemini_analysis_model: str = "gemini-2.5-pro"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    # PDF parser (RAG ingest). MinerU = structure-aware OCR/layout for scientific papers.
    pdf_parser: str = "mineru"
    mineru_backend: str = "pipeline"   # pipeline (CPU) | vlm-transformers (GPU)
    mineru_device: str = "cpu"         # cpu | cuda
    mineru_lang: str = "en"


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
    parser = data.get("parser", {}) if isinstance(data, dict) else {}
    return Config(
        openalex_email=(openalex.get("email") or None),
        llm_provider=llm.get("provider", "openai"),
        openai_model=openai.get("model", "gpt-4.1-mini"),
        openai_base_url=openai.get("base_url"),
        openai_cheap_model=openai.get("cheap_model", "gpt-4.1-nano"),
        openai_analysis_model=openai.get("analysis_model", "gpt-4.1"),
        gemini_model=gemini.get("model", "gemini-2.5-flash"),
        gemini_cheap_model=gemini.get("cheap_model", "gemini-2.0-flash-lite"),
        gemini_analysis_model=gemini.get("analysis_model", "gemini-2.5-pro"),
        gemini_base_url=gemini.get("base_url", "https://generativelanguage.googleapis.com/v1beta"),
        pdf_parser=parser.get("parser", "mineru"),
        mineru_backend=parser.get("mineru_backend", "pipeline"),
        mineru_device=parser.get("mineru_device", "cpu"),
        mineru_lang=parser.get("mineru_lang", "en"),
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
# Thiết lập OPENAI_API_KEY trong env.
model = "gpt-4.1-mini"          # standard: chat, parse-query
cheap_model = "gpt-4.1-nano"    # cheap: translate, summarize
analysis_model = "gpt-4.1"      # premium: paper analyze/visual (cached) — đổi thành "gpt-5" / "o3" để tăng chất lượng visual
# base_url = "https://api.openai.com/v1"

[gemini]
# Thiết lập GEMINI_API_KEY trong env.
model = "gemini-2.5-flash"              # standard
cheap_model = "gemini-2.0-flash-lite"   # cheap
analysis_model = "gemini-2.5-pro"       # premium
base_url = "https://generativelanguage.googleapis.com/v1beta"

[parser]
# PDF parser cho RAG ingest. MinerU trích cấu trúc (section/bảng/công thức) cho bài báo khoa học.
parser = "mineru"
mineru_backend = "pipeline"   # pipeline = CPU; đổi "vlm-transformers" nếu có GPU NVIDIA
mineru_device = "cpu"          # cpu | cuda
mineru_lang = "en"
""",
        encoding="utf-8",
    )
    return True
