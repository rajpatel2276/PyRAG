from pathlib import Path
from git import Repo,GitCommandError
from src.config.settings import settings    
from src.config.logging_config import setup_logging

logger = setup_logging(__name__)

def clone_repo(repo_url:str,repo_name: str | None = None) -> Path:
    repo_name = repo_name or repo_url.rstrip("/").split("/")[-1].replace(".git","")
    local_path = settings.repos_dir / repo_name

    if local_path.exists():
        logger.info(f"Repo '{repo_name}' already exist locally,pulling latest")
        try:
            repo = Repo(local_path)
            repo.remotes.origin.pull()
        except GitCommandError as e:
            logger.error(f"Failed to pull {repo_name}:{e}")
            raise
        return local_path
    
    logger.info(f"Cloning {repo_url} -> {local_path}")
    try:
        Repo.clone_from(repo_url,local_path)
    except GitCommandError as e:
        logger.error(f"Failed to clone {repo_url}: {e}")
        raise
    return local_path