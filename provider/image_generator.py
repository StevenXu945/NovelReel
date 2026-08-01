import os
from pathlib import Path
import requests
import yaml
import mimetypes
from urllib.parse import urlparse

from google import genai
from google.genai import types
from volcenginesdkarkruntime import Ark


DEFAULT_SEEDREAM_CONFIG = {
    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "api_key": "",
    "model": "doubao-seedream-5-0-260128",
    "sizes": {
        "16:9": "2848x1600",
        "9:16": "1600x2848",
        "1:1": "2048x2048",
    },
}

DEFAULT_IMAGE_CONFIG = {
    "provider": "seedream",
    "seedream": DEFAULT_SEEDREAM_CONFIG,
    "zenmux": {
        "base_url": "https://zenmux.ai/api/vertex-ai",
        "api_key": "",
        "model": "bytedance/doubao-seedream-5.0-pro",
        "image_size": "2K",
    },
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def _resolve_config_path(config_path):
    if not config_path:
        return DEFAULT_CONFIG_PATH
    path = Path(config_path)
    if path.is_absolute() or path.exists():
        return path
    return PROJECT_ROOT / path


def _deep_merge(base, override):
    merged = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        elif value is not None:
            merged[key] = value
    return merged


def _load_image_config(config_path):
    config_path = _resolve_config_path(config_path)
    if not config_path.exists():
        return DEFAULT_IMAGE_CONFIG
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return _deep_merge(DEFAULT_IMAGE_CONFIG, config.get("image", {}))


class ImageGenerator(object):
    """图像生成模型，支持 Seedream Ark 与 Zenmux。

    功能：文生图，用于生成角色图和环境图
    """

    def __init__(self, output_dir="output", provider=None, config_path=None):
        """
        Args:
            output_dir: 输出目录
            provider: 生图引擎，支持 "seedream"、"zenmux"；不传时读取 config.yaml
            config_path: 配置文件路径
        """
        self.output_dir = output_dir
        image_config = _load_image_config(config_path)
        self.provider = provider or image_config.get("provider", "seedream")
        if self.provider not in {"seedream", "zenmux"}:
            raise ValueError(f"Unsupported image provider: {self.provider}")

        if self.provider == "seedream":
            seedream_config = image_config.get("seedream", {})
            self.seedream_model = seedream_config.get("model")
            self.seedream_sizes = seedream_config["sizes"]
            api_key = seedream_config.get("api_key", "") or os.environ.get("ARK_API_KEY")
            if not api_key:
                raise ValueError("Missing image.seedream.api_key in config.yaml or ARK_API_KEY")
            self.ark_client = Ark(
                base_url=seedream_config.get("base_url"),
                api_key=api_key,
            )
        else:
            zenmux_config = image_config.get("zenmux", {})
            self.zenmux_model = zenmux_config.get("model")
            self.zenmux_image_size = zenmux_config.get("image_size", "2K")
            api_key = zenmux_config.get("api_key", "") or os.environ.get("ZENMUX_API_KEY")
            if not api_key:
                raise ValueError("Missing image.zenmux.api_key in config.yaml or ZENMUX_API_KEY")
            self.zenmux_client = genai.Client(
                api_key=api_key,
                vertexai=True,
                http_options=types.HttpOptions(
                    api_version="v1",
                    base_url=zenmux_config.get("base_url"),
                ),
            )

    def _text_to_image(self, prompt, save_path, aspect_ratio="16:9", force=False):
        """文生图，根据 provider 选择不同的生图引擎

        Args:
            prompt: 生图 prompt
            save_path: 图片保存路径
            aspect_ratio: 宽高比，如 "9:16", "16:9", "1:1"
            force: 是否强制覆盖已有图片

        Returns:
            tuple: (保存的图片路径, image_url)，失败返回 ("", "")
                   Seedream 返回远程 URL；Zenmux 直接返回图片字节，因此 URL 为空
        """
        if os.path.exists(save_path) and not force:
            print(f"  图片已存在，跳过: {save_path}")
            return save_path, ""

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        if self.provider == "zenmux":
            return self._text_to_image_zenmux(prompt, save_path, aspect_ratio)
        return self._text_to_image_seedream(prompt, save_path, aspect_ratio)

    def _text_to_image_zenmux(self, prompt, save_path, aspect_ratio="16:9"):
        """通过 Zenmux Google GenAI 兼容端点文生图。"""
        try:
            response = self.zenmux_client.models.generate_images(
                model=self.zenmux_model,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                    image_size=self.zenmux_image_size,
                    add_watermark=False,
                ),
            )
            return self._save_zenmux_generated_image(response, save_path)
        except Exception as e:
            print(f"  Zenmux 生图失败: {e}")
            return "", ""

    def _text_to_image_seedream(self, prompt, save_path, aspect_ratio="16:9"):
        """调用 Volcengine Ark API (seedream) 文生图"""
        size = self.seedream_sizes.get(aspect_ratio, self.seedream_sizes.get("16:9", "2848x1600"))

        try:
            response = self.ark_client.images.generate(
                model=self.seedream_model,
                prompt=prompt,
                sequential_image_generation="disabled",
                response_format="url",
                size=size,
                stream=False,
                watermark=False,
            )

            image_url = response.data[0].url
            # 下载图片并保存
            img_resp = requests.get(image_url, timeout=120)
            img_resp.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(img_resp.content)
            print(f"  图片已保存: {save_path}")
            return save_path, image_url
        except Exception as e:
            print(f"  生图失败: {e}")
            return "", ""

    def _image_to_image_seedream(self, prompt, image_urls, save_path, aspect_ratio="16:9", force=False):
        """用 seedream 参考图生成新图。

        Ark 的 image 参数需要可访问 URL；如果没有 URL，调用方应回退到文生图。
        """
        if os.path.exists(save_path) and not force:
            print(f"  图片已存在，跳过: {save_path}")
            return save_path, ""

        clean_urls = [
            url for url in (image_urls or [])
            if isinstance(url, str) and urlparse(url).scheme in {"http", "https"}
        ]
        if not clean_urls:
            return self._text_to_image(prompt, save_path, aspect_ratio=aspect_ratio, force=force)

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        size = self.seedream_sizes.get(aspect_ratio, self.seedream_sizes.get("16:9", "2848x1600"))

        try:
            response = self.ark_client.images.generate(
                model=self.seedream_model,
                prompt=prompt,
                image=clean_urls,
                sequential_image_generation="disabled",
                response_format="url",
                size=size,
                stream=False,
                watermark=False,
            )

            image_url = response.data[0].url
            img_resp = requests.get(image_url, timeout=120)
            img_resp.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(img_resp.content)
            print(f"  图片已保存: {save_path}")
            return save_path, image_url
        except Exception as e:
            print(f"  参考图生图失败: {e}")
            return "", ""

    def _image_to_image(
        self,
        prompt,
        image_urls,
        save_path,
        aspect_ratio="16:9",
        force=False,
        image_paths=None,
    ):
        if self.provider == "zenmux":
            return self._image_to_image_zenmux(
                prompt,
                image_urls,
                save_path,
                aspect_ratio=aspect_ratio,
                force=force,
                image_paths=image_paths,
            )
        return self._image_to_image_seedream(
            prompt,
            image_urls,
            save_path,
            aspect_ratio=aspect_ratio,
            force=force,
        )

    def _image_to_image_zenmux(
        self,
        prompt,
        image_urls,
        save_path,
        aspect_ratio="16:9",
        force=False,
        image_paths=None,
    ):
        """通过 Zenmux 使用本地图片字节（优先）或远程 URL 图生图。"""
        if os.path.exists(save_path) and not force:
            print(f"  图片已存在，跳过: {save_path}")
            return save_path, ""

        reference_images = []
        for image_path in image_paths or []:
            path = Path(image_path)
            if not path.is_file():
                continue
            mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
            reference_images.append(
                types.RawReferenceImage(
                    reference_image=types.Image(
                        image_bytes=path.read_bytes(),
                        mime_type=mime_type,
                    )
                )
            )

        if not reference_images:
            for url in image_urls or []:
                if not isinstance(url, str) or urlparse(url).scheme not in {"http", "https"}:
                    continue
                try:
                    response = requests.get(url, timeout=120)
                    response.raise_for_status()
                    mime_type = response.headers.get("Content-Type", "").split(";")[0] or "image/png"
                    reference_images.append(
                        types.RawReferenceImage(
                            reference_image=types.Image(
                                image_bytes=response.content,
                                mime_type=mime_type,
                            )
                        )
                    )
                except Exception as e:
                    print(f"  Zenmux 参考图下载失败，已跳过: {e}")

        if not reference_images:
            return self._text_to_image(prompt, save_path, aspect_ratio=aspect_ratio, force=force)

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        try:
            response = self.zenmux_client.models.edit_image(
                model=self.zenmux_model,
                prompt=prompt,
                reference_images=reference_images,
                config=types.EditImageConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                    add_watermark=False,
                ),
            )
            return self._save_zenmux_generated_image(response, save_path)
        except Exception as e:
            print(f"  Zenmux 参考图生图失败: {e}")
            return "", ""

    def _save_zenmux_generated_image(self, response, save_path):
        generated_images = getattr(response, "generated_images", None) or []
        if not generated_images:
            raise RuntimeError("Zenmux 生图完成，但没有返回 generated_images")
        image = getattr(generated_images[0], "image", None)
        image_bytes = getattr(image, "image_bytes", None)
        if not image_bytes:
            raise RuntimeError("Zenmux 生图完成，但没有返回图片字节")
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(image_bytes)
        print(f"  图片已保存: {save_path}")
        return save_path, ""

    def generate_character_image(
        self,
        character_description,
        save_path=None,
        force=False,
        reference_image_urls=None,
        reference_image_paths=None,
    ):
        """根据角色描述生成全身形象图（白色背景）

        Returns:
            tuple: (图片路径, image_url)
        """
        if save_path is None:
            os.makedirs(os.path.join(self.output_dir, "characters"), exist_ok=True)
            save_path = os.path.join(self.output_dir, "characters", "char_auto.png")
        if reference_image_urls or reference_image_paths:
            return self._image_to_image(
                character_description,
                reference_image_urls,
                save_path,
                aspect_ratio="16:9",
                force=force,
                image_paths=reference_image_paths,
            )
        return self._text_to_image(character_description, save_path, aspect_ratio="16:9", force=force)

    def generate_reference_image(
        self,
        prompt,
        reference_image_urls,
        save_path,
        aspect_ratio="16:9",
        force=False,
        reference_image_paths=None,
    ):
        """根据参考图生成图片；没有可用 URL 时自动回退到文生图。"""
        return self._image_to_image(
            prompt,
            reference_image_urls,
            save_path,
            aspect_ratio=aspect_ratio,
            force=force,
            image_paths=reference_image_paths,
        )
