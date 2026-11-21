import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("PRAWDOWID_DATA_DIR", str(ROOT / "data"))))
    corpus: Path = field(default_factory=lambda: Path(os.getenv("PRAWDOWID_CORPUS", str(ROOT / "Research/Prawdowid_Korpus_Start.jsonl"))))
    environment: str = field(default_factory=lambda: os.getenv("PRAWDOWID_ENV", "development"))
    evaluator: str = field(default_factory=lambda: os.getenv("PRAWDOWID_EVALUATOR", "live"))
    model: str = field(default_factory=lambda: os.getenv("PRAWDOWID_MODEL", "gpt-6-luna"))
    guard_model: str = field(default_factory=lambda: os.getenv("PRAWDOWID_GUARD_MODEL", "gpt-6-luna"))
    key: str = field(default_factory=lambda: os.getenv("PRAWDOWID_API_KEY") or os.getenv("OPENAI_API_KEY", ""), repr=False)
    url: str = field(default_factory=lambda: os.getenv("PRAWDOWID_API_URL", "https://api.openai.com/v1/chat/completions"))
    price_in: str | None = field(default_factory=lambda: os.getenv("PRAWDOWID_PRICE_IN_PER_M"))
    price_out: str | None = field(default_factory=lambda: os.getenv("PRAWDOWID_PRICE_OUT_PER_M"))
    timeout: float = field(default_factory=lambda: float(os.getenv("PRAWDOWID_TIMEOUT_S", "22")))
    rate_limit_enabled: bool = field(default_factory=lambda: os.getenv("PRAWDOWID_RATE_LIMIT_ENABLED") == "1")
    paid_check_limit: int = field(default_factory=lambda: int(os.getenv("PRAWDOWID_PAID_CHECK_LIMIT", "0")))
    whatsapp_secret: str = field(default_factory=lambda: os.getenv("PRAWDOWID_WA_APP_SECRET", ""), repr=False)
    whatsapp_token: str = field(default_factory=lambda: os.getenv("PRAWDOWID_WA_VERIFY_TOKEN", ""), repr=False)

    def __post_init__(self):
        if self.evaluator not in {"live", "fake"}:
            raise ValueError("Unsupported evaluator")
        if self.environment == "production" and self.evaluator == "fake":
            raise ValueError("The fake evaluator is disabled in production")
        if self.timeout <= 0:
            raise ValueError("The model timeout must be positive")
        if self.paid_check_limit < 0:
            raise ValueError("The paid check limit must be nonnegative")
