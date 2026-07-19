from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_flash_model: str = "deepseek-v4-flash"
    deepseek_pro_model: str = "deepseek-v4-pro"

    github_token: str = ""
    youtube_api_key: str = ""
    x_bearer_token: str = ""

    database_url: str = "sqlite:///frontier_signal.db"
    config_dir: Path = Path("config")
    output_dir: Path = Path("outputs")
    prompt_dir: Path = Path("prompts")

    max_daily_llm_cost_usd: float = 3.0
    max_pro_calls_per_day: int = 25
    max_items_analyzed_per_run: int = 150
    max_llm_content_chars: int = 8000
    max_translation_content_chars: int = 4000
    pro_priority_threshold: float = 68.0
    report_max_items: int = 15
    max_item_age_days: int = 7
    report_timezone: str = "America/Vancouver"
    report_github_max_items: int = 3
    report_per_source_max_items: int = 1
    report_china_min_items: int = 4
    report_social_min_items: int = 2
    report_academic_min_items: int = 3
    share_private_items: bool = False


settings = Settings()
