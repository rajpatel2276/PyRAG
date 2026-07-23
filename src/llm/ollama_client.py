import requests
from src.config.logging_config import setup_logging

logger = setup_logging(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "qwen2.5-coder:1.5b-instruct-q4_K_M"
DEFAULT_TIMEOUT_SECONDS = 60


class OllamaClient:
    def __init__(self, model: str = MODEL_NAME, base_url: str = OLLAMA_BASE_URL):
        self.model = model
        self.base_url = base_url
        self._verify_model_available()

    def _verify_model_available(self):
        """Fail fast and clearly at startup if Ollama isn't running or the
        model isn't pulled, rather than letting the first real request fail
        with a confusing error deep in application logic later.
        """
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            logger.error(
                f"Could not connect to Ollama at {self.base_url}. "
                f"Is the Ollama service running? (systemctl status ollama)"
            )
            raise RuntimeError("Ollama service unreachable")
        except requests.exceptions.RequestException as e:
            logger.error(f"Unexpected error checking Ollama status: {e}")
            raise

        available_models = [m["name"] for m in resp.json().get("models", [])]
        if self.model not in available_models:
            logger.error(
                f"Model '{self.model}' not found in Ollama. "
                f"Available: {available_models}. Run: ollama pull {self.model}"
            )
            raise RuntimeError(f"Model '{self.model}' not pulled")

        logger.info(f"Ollama connected, model '{self.model}' available")

    def generate(self, prompt: str, system: str | None = None, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,   # we'll add streaming later in Phase 6 if needed; keep this simple for now
        }
        if system:
            payload["system"] = system

        try:
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=timeout)
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            logger.error(f"Ollama request timed out after {timeout}s")
            raise RuntimeError(f"LLM generation timed out after {timeout}s")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama request failed: {e}")
            raise RuntimeError(f"LLM generation failed: {e}")

        return resp.json()["response"]