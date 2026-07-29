from pathlib import Path
import yaml
from openai import OpenAI


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def _resolve_config_path(config_path):
    if not config_path:
        return DEFAULT_CONFIG_PATH
    path = Path(config_path)
    if path.is_absolute() or path.exists():
        return path
    return PROJECT_ROOT / path


class LLMClient:
    def __init__(self, config_path=None, model=None):
        config_path = _resolve_config_path(config_path)
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self.llm_config = config["llm"]

        self.client = OpenAI(
            base_url=self.llm_config.get("base_url", "https://api.openai.com/v1"),
            api_key=self.llm_config["api_key"],
        )

        self.model = model or self.llm_config["model"]

    def generate(self, prompt: str) -> str:
        params = {
            "model": self.model,
            "input": prompt,
        }

        optional_params = [
            "temperature",
            "top_p",
            "max_output_tokens",
        ]

        for key in optional_params:
            value = self.llm_config.get(key)
            if value is not None:
                params[key] = value

        response = self.client.responses.create(**params)
        if getattr(response, "output_text", None):
            return response.output_text

        texts = []
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    texts.append(text)
        return "\n".join(texts)

if __name__ == "__main__":
    llm_client = LLMClient()
    prompt = "给我一个python的快排算法"
    print(llm_client.generate(prompt))
