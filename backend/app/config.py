from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "祁智运 API"
    environment: str = "development"
    database_url: str = "sqlite:///./qizhi.db"
    redis_url: str = "redis://127.0.0.1:6379/0"
    jwt_secret: str = "dev-only-change-me-at-least-32-bytes"
    ai_config_encryption_key: str = ""
    jwt_expire_minutes: int = 60
    login_max_attempts: int = 5
    login_lock_minutes: int = 15
    admin_username: str = "admin"
    admin_password: str = "QizhiDemo2026!"
    driver_username: str = "driver"
    driver_password: str = "DriverDemo2026!"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    routing_provider: str = "haversine"
    osrm_base_url: str = "https://router.project-osrm.org"
    osrm_profile: str = "driving"
    osrm_timeout_seconds: float = 4.0
    routing_cache_size: int = 128
    rural_detour_factor: float = 1.28
    rural_average_speed_kmh: float = 42.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
