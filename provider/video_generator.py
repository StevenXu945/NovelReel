import os
import time
import yaml
import requests
import mimetypes

from pathlib import Path
from google import genai
from google.genai import types
from volcenginesdkarkruntime import Ark


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"

DEFAULT_VIDEO_CONFIG = {
    "provider": "ark",
    "ratio": "16:9",
    "resolution": "480p",
    "poll_interval": 30,
    "generate_audio": True,
    "watermark": True,
    "providers": {
        "ark": {
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "api_key": "",
            "model": "doubao-seedance-2-0-260128",
        },
        "zenmux": {
            "base_url": "https://zenmux.ai/api/vertex-ai",
            "api_key": "",
            "model": "bytedance/doubao-seedance-2.0",
        },
    },
}


def _deep_merge(base, override):
    merged = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        elif value is not None:
            merged[key] = value
    return merged


def _resolve_config_path(config_path):
    if not config_path:
        return DEFAULT_CONFIG_PATH
    path = Path(config_path)
    if path.is_absolute() or path.exists():
        return path
    return PROJECT_ROOT / path


def _load_video_config(config_path):
    config_path = _resolve_config_path(config_path)
    if not config_path.exists():
        return DEFAULT_VIDEO_CONFIG
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return _deep_merge(DEFAULT_VIDEO_CONFIG, config.get("video", {}))


class VideoGeneratorMulti:
    """Video generator with Ark Seedance and Zenmux Seedance backends."""

    DEFAULT_DURATION = 11

    def __init__(
        self,
        provider=None,
        provider_config=None,
        ratio=None,
        resolution=None,
        poll_interval=None,
        generate_audio=None,
        watermark=None,
        config_path=None,
    ):
        video_config = _load_video_config(config_path)
        self.provider = provider or video_config.get("provider", "ark")
        self.providers_config = video_config.get("providers", {})
        self.provider_config = _deep_merge(
            self.providers_config.get(self.provider, {}),
            provider_config or {},
        )
        self.ratio = ratio or video_config.get("ratio", "16:9")
        self.resolution = resolution or video_config.get("resolution", "480p")
        self.poll_interval = poll_interval if poll_interval is not None else video_config.get("poll_interval", 30)
        self.generate_audio = generate_audio if generate_audio is not None else video_config.get("generate_audio", True)
        self.watermark = watermark if watermark is not None else video_config.get("watermark", True)

    def generate_video_clip(
        self,
        prompt,
        output_path,
        reference_image_urls=None,
        reference_image_paths=None,
        duration=None,
        generate_audio=None,
        watermark=None,
        provider=None,
    ):
        provider = provider or self.provider
        if provider == "ark":
            return self.generate_with_ark(
                prompt,
                output_path,
                reference_image_urls=reference_image_urls,
                duration=duration,
                generate_audio=generate_audio,
                watermark=watermark,
            )
        if provider == "zenmux":
            return self.generate_with_zenmux(
                prompt,
                output_path,
                reference_image_urls=reference_image_urls,
                reference_image_paths=reference_image_paths,
                duration=duration,
                generate_audio=generate_audio,
            )
        raise ValueError(f"Unsupported video provider: {provider}")

    def generate_with_ark(
        self,
        prompt,
        output_path,
        reference_image_urls=None,
        duration=None,
        generate_audio=None,
        watermark=None,
    ):
        """Generate video through Volcengine Ark content_generation.tasks."""
        ark_config = self._backend_config("ark")
        api_key = ark_config.get("api_key") or os.environ.get("ARK_API_KEY")
        client = Ark(base_url=ark_config.get("base_url"), api_key=api_key)
        duration = self._resolve_duration(duration)
        generate_audio = self.generate_audio if generate_audio is None else generate_audio
        watermark = self.watermark if watermark is None else watermark
        content = [{"type": "text", "text": prompt}]

        for url in reference_image_urls or []:
            content.append({
                "type": "image_url",
                "image_url": {"url": url},
                "role": "reference_image",
            })

        create_result = client.content_generation.tasks.create(
            model=ark_config.get("model"),
            content=content,
            generate_audio=generate_audio,
            ratio=self.ratio,
            duration=duration,
            watermark=watermark,
        )
        task_id = create_result.id
        print(f"[VideoGeneratorMulti:ark] 任务已创建: {task_id}")

        while True:
            get_result = client.content_generation.tasks.get(task_id=task_id)
            status = get_result.status
            if status == "succeeded":
                print(f"[VideoGeneratorMulti:ark] 任务成功: {task_id}")
                break
            if status == "failed":
                raise RuntimeError(f"Ark 视频生成失败: {get_result.error}")
            print(f"[VideoGeneratorMulti:ark] 当前状态: {status}，{self.poll_interval}秒后重试...")
            time.sleep(self.poll_interval)

        video_url = get_result.content.video_url
        return self._download_video(video_url, output_path)

    def generate_with_zenmux(
        self,
        prompt,
        output_path,
        reference_image_urls=None,
        reference_image_paths=None,
        duration=None,
        generate_audio=None,
    ):
        """Generate video through Zenmux's Google GenAI compatible endpoint."""
        zenmux_config = self._backend_config("zenmux")
        api_key = zenmux_config.get("api_key") or os.environ.get("ZENMUX_API_KEY")
        if not api_key:
            raise ValueError("Missing Zenmux API key. Set ZENMUX_API_KEY or pass provider_config={'api_key': ...}.")
        duration = self._resolve_duration(duration)
        generate_audio = self.generate_audio if generate_audio is None else generate_audio

        client = genai.Client(
            api_key=api_key,
            vertexai=True,
            http_options=types.HttpOptions(
                api_version="v1",
                base_url=zenmux_config.get("base_url"),
            ),
        )

        reference_images = self._build_zenmux_reference_images(
            reference_image_paths=reference_image_paths,
            reference_image_urls=reference_image_urls,
        )
        config = types.GenerateVideosConfig(
            reference_images=reference_images,
            aspect_ratio=self.ratio,
            resolution=self.resolution,
            duration_seconds=duration,
            generate_audio=generate_audio,
        )

        operation = client.models.generate_videos(
            model=zenmux_config.get("model"),
            prompt=prompt,
            config=config,
        )
        print("[VideoGeneratorMulti:zenmux] 任务已创建")

        while not operation.done:
            time.sleep(self.poll_interval)
            operation = client.operations.get(operation)
            print(f"[VideoGeneratorMulti:zenmux] 当前状态: done={operation.done}")

        if getattr(operation, "error", None):
            raise RuntimeError(f"Zenmux 视频生成失败: {operation.error}")

        generated_videos = getattr(operation.response, "generated_videos", None) or []
        if not generated_videos:
            raise RuntimeError("Zenmux 视频生成完成，但没有返回 generated_videos")

        video_bytes = self._extract_zenmux_video_bytes(generated_videos[0])

        return self._save_video_bytes(video_bytes, output_path)

    def _build_zenmux_reference_images(
        self,
        reference_image_paths=None,
        reference_image_urls=None,
    ):
        """Prefer local image bytes so expiring remote URLs are not required."""
        local_images = []
        for image_path in reference_image_paths or []:
            path = Path(image_path)
            if not path.is_file():
                print(f"[VideoGeneratorMulti:zenmux] 本地参考图不存在，已跳过: {path}")
                continue

            mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
            local_images.append(
                types.VideoGenerationReferenceImage(
                    image=types.Image(
                        image_bytes=path.read_bytes(),
                        mime_type=mime_type,
                    ),
                    reference_type="ASSET",
                )
            )

        if local_images:
            print(f"[VideoGeneratorMulti:zenmux] 使用 {len(local_images)} 张本地参考图")
            return local_images

        remote_images = [
            types.VideoGenerationReferenceImage(
                image=types.Image(gcs_uri=url),
                reference_type="ASSET",
            )
            for url in (reference_image_urls or [])
        ]
        if remote_images:
            print(f"[VideoGeneratorMulti:zenmux] 本地参考图不可用，回退到 {len(remote_images)} 个图片 URL")
        return remote_images

    def _backend_config(self, provider):
        if provider == self.provider:
            return self.provider_config
        return self.providers_config.get(provider, {})

    def _resolve_duration(self, duration):
        return duration if duration is not None else self.DEFAULT_DURATION

    def _download_video(self, video_url, output_path):
        output_path = str(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(video_url, timeout=300)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)
        print(f"[VideoGeneratorMulti] 视频已保存: {output_path}")
        return output_path

    def _save_video_bytes(self, video_bytes, output_path):
        output_path = str(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(video_bytes)
        print(f"[VideoGeneratorMulti] 视频已保存: {output_path}")
        return output_path

    def _extract_zenmux_video_bytes(self, generated_video):
        candidates = [
            ("video", "video_bytes"),
            ("video", "bytes"),
        ]
        for parent_attr, child_attr in candidates:
            parent = getattr(generated_video, parent_attr, None)
            value = getattr(parent, child_attr, None) if parent is not None else None
            if value:
                return value

        for attr in ("video_bytes", "bytes"):
            value = getattr(generated_video, attr, None)
            if value:
                return value
        return None


if __name__ == "__main__":
    import argparse
    import json

    DEFAULT_REFERENCE_IMAGE_URLS = [
        "https://ark-acg-cn-beijing.tos-cn-beijing.volces.com/doubao-seedream-5-0/021782292778216fdfd2e3c33d5b6eddad55ac385080e72a5282b_0.jpeg?X-Tos-Algorithm=TOS4-HMAC-SHA256&X-Tos-Credential=AKLTYWJkZTExNjA1ZDUyNDc3YzhjNTM5OGIyNjBhNDcyOTQ%2F20260624%2Fcn-beijing%2Ftos%2Frequest&X-Tos-Date=20260624T092012Z&X-Tos-Expires=86400&X-Tos-Signature=50b50df12c57047c747b044c9bcb26e1b6d8599fd5020d9bd31b4014fb4f8f34&X-Tos-SignedHeaders=host",
        "https://ark-acg-cn-beijing.tos-cn-beijing.volces.com/doubao-seedream-5-0/0217822904729377c52c410876ab8649e200d8680cedfa0d3d92e_0.jpeg?X-Tos-Algorithm=TOS4-HMAC-SHA256&X-Tos-Credential=AKLTYWJkZTExNjA1ZDUyNDc3YzhjNTM5OGIyNjBhNDcyOTQ%2F20260624%2Fcn-beijing%2Ftos%2Frequest&X-Tos-Date=20260624T084148Z&X-Tos-Expires=86400&X-Tos-Signature=2498e099ab244ffb6c4770f446c4e4e758ef76cbac49a7c0cf1c48c74ecf8257&X-Tos-SignedHeaders=host",
        "https://ark-acg-cn-beijing.tos-cn-beijing.volces.com/doubao-seedream-5-0/021782291191508d2ead8b3d4a98fc1d2171244f66732071a9b1e_0.jpeg?X-Tos-Algorithm=TOS4-HMAC-SHA256&X-Tos-Credential=AKLTYWJkZTExNjA1ZDUyNDc3YzhjNTM5OGIyNjBhNDcyOTQ%2F20260624%2Fcn-beijing%2Ftos%2Frequest&X-Tos-Date=20260624T085339Z&X-Tos-Expires=86400&X-Tos-Signature=c980784f19ed659aaf9115074348d514cd9ee228b51bfaf38955ca0097ef955f&X-Tos-SignedHeaders=host",
    ]

    def parse_url_args(values):
        urls = []
        for value in values or []:
            value = str(value).strip()
            if not value:
                continue
            if value.startswith("["):
                try:
                    parsed = json.loads(value)
                except json.JSONDecodeError:
                    parsed = [
                        item.strip().strip("'\"")
                        for item in value.strip()[1:-1].split(",")
                    ]
                if not isinstance(parsed, list):
                    raise ValueError("URL list argument must be a list")
                urls.extend(str(item).strip() for item in parsed if str(item).strip())
            else:
                urls.append(value)
        return urls

    parser = argparse.ArgumentParser(description="测试多后端视频生成器")
    parser.add_argument("--provider", choices=["ark", "zenmux"], default=None, help="视频生成后端；默认读取 config.yaml")
    parser.add_argument("--prompt", default="图1中的角色缓慢走向镜头，电影感运镜。", help="视频生成提示词")
    parser.add_argument("--output-path", default="output/test_video.mp4", help="输出视频路径")
    parser.add_argument("--reference-image-url", action="append", default=[], help="参考图 URL，可重复传入")
    parser.add_argument("--duration", type=int, default=7, help="生成视频时长")
    parser.add_argument("--run", action="store_true", help="实际提交生成任务；默认只打印 dry-run 参数")
    args = parser.parse_args()

    generator = VideoGeneratorMulti(provider=args.provider)
    reference_image_urls = parse_url_args(args.reference_image_url) or DEFAULT_REFERENCE_IMAGE_URLS
    payload = {
        "provider": args.provider or generator.provider,
        "prompt": args.prompt,
        "output_path": args.output_path,
        "reference_image_urls": reference_image_urls,
        "duration": args.duration,
    }

    if not args.run:
        print("Dry run. Add --run to submit the generation task.")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        result_path = generator.generate_video_clip(
            prompt=args.prompt,
            output_path=args.output_path,
            reference_image_urls=reference_image_urls,
            duration=args.duration,
            provider=args.provider,
        )
        print(result_path)
