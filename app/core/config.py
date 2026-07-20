from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_table: str = "chunks"
    supabase_match_fn: str = "match_chunks"

    # Chunking defaults
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # API defaults
    default_k: int = 4
    max_k: int = 20
    default_temperature: float = 0.4
    default_max_output_tokens: int = 400

    # Files
    tmp_dir: str = "./tmp"


settings = Settings()