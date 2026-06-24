from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_vision_api_key: str = ""
    google_translate_api_key: str = ""

    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "products"

    postgres_dsn: str = "postgresql://user:password@localhost:5432/marketplace"

    label_cache_ttl_seconds: int = 3600

    rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60

    use_mock: bool = False
    mock_data_path: str = "mock_data/products.json"

    max_image_size_bytes: int = 10 * 1024 * 1024  # 10 MB
    compressed_image_size_bytes: int = 1 * 1024 * 1024  # 1 MB
    vision_confidence_threshold: float = 0.70
    vision_top_labels: int = 5
    search_max_results: int = 20

    class Config:
        env_file = ".env"


settings = Settings()
