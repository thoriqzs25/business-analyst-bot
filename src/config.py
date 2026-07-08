from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    opencode_go_api_key: str = ""
    opencode_go_base_url: str = "https://opencode.ai/zen/go/v1"
    llm_model: str = "deepseek-v4-flash"

    skills_group_jid: str = ""
    code_group_jid: str = ""

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "business_bot"
    postgres_user: str = "botuser"
    postgres_password: str = "changeme"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    mem0_qdrant_collection: str = "mem0"

    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "business-analyst-bot"

    log_level: str = "INFO"
    admin_username: str = "admin"
    admin_password: str = "changeme"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        pw = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{pw}{self.redis_host}:{self.redis_port}"


settings = Settings()
