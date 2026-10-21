from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    litellm_base_url: str = "http://localhost:4000"
    litellm_api_key: str = "sk-placeholder"
    litellm_model: str = "claude-sonnet-4-6"
    wiremock_base_url: str = "http://localhost:8080"
    mcp_server_url: str = "http://localhost:3001"
    app_port: int = 8000

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "env_prefix": "",
        "populate_by_name": True,
    }


settings = Settings()
