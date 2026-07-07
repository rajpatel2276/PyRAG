from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    # Paths
    project_root: Path = Path(__file__).parent.parent.parent
    repos_dir: Path = project_root / "data" / "repos"
    chunks_dir: Path = project_root / "data" / "chunks"
    logs_dir: Path = project_root / "logs"

    # Parsing
    supported_extensions: tuple[str, ...] = (".py",)
    max_file_size_bytes: int = 500_000  # skip huge generated files

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
settings.repos_dir.mkdir(parents=True, exist_ok=True)
settings.chunks_dir.mkdir(parents=True, exist_ok=True)
settings.logs_dir.mkdir(parents=True, exist_ok=True)