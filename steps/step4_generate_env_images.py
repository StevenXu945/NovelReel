import json
import os
import re
import shutil
from pathlib import Path
from PIL import Image
import yaml
from provider.image_generator import ImageGenerator
from provider.llm_provider import LLMClient
from core.project_paths import resolve_previous_asset_dir


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def _load_video_ratio(config_path=None):
    config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    if not config_path.exists():
        return "16:9"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return str(config.get("video", {}).get("ratio") or "16:9").strip() or "16:9"


PROMPT_PLAN_CHAPTER_ENV_ASSETS = """你是一个连续剧场景资产统筹。请根据本章节分镜里的环境，与截至当前章节前已经建立的全局环境资产对齐，决定每个本章节环境图如何处理。

动作定义：
- "reuse": 同一地点且时间、天气、布置、光线氛围基本一致，直接复用已有环境图
- "update": 同一地点但有明显变化，例如时间/季节/天气/损毁/布置/光线变化，需要参考已有环境图生成新图
- "new": 全局资产里没有的全新地点

只比较静态环境背景，不要因为角色动作或可移动道具导致误判。输出必须覆盖本章节所有 environment_id。

全局环境资产：
{previous_environments_json}

本章节环境：
{current_environments_json}

请只输出 JSON：
```json
{{
  "environments": [
    {{
      "environment_id": 1,
      "asset_action": "reuse/update/new",
      "previous_environment_id": 1,
      "reason": "判断理由"
    }}
  ]
}}
```
"""


class EnvironmentImageGenerator:
    """步骤4：根据分镜的环境描述生成环境图

    为每个环境生成单张参考图。
    """

    def __init__(self, output_dir="output", config_path=None):
        self.image_gen = ImageGenerator(output_dir=output_dir, provider="seedream")
        self.llm = LLMClient()
        self.output_dir = output_dir
        self.env_dir = os.path.join(output_dir, "environments")
        self.save_path = os.path.join(output_dir, "env_images.json")
        self.plan_save_path = os.path.join(output_dir, "env_asset_plan.json")
        self.aspect_ratio = _load_video_ratio(config_path)


    def run(self, storyboards, style="写实"):
        print(f"\n[步骤4] 生成环境图（风格: {style}，比例: {self.aspect_ratio}）...")
        os.makedirs(self.env_dir, exist_ok=True)

        env_images = {}
        for env in self._collect_current_environments(storyboards):
            self._generate_current_environment(env, style, env_images, force_new=False)

        self.save(env_images)
        return env_images

    def _generate_current_environment(self, env, style, env_images, force_new=False):
        env_id = env["environment_id"]
        env_desc = env["environment_description"]
        reference_environment_id = env.get("reference_environment_id")
        img_path = os.path.join(self.env_dir, f"env_{int(env_id):03d}.png")

        if str(env_id) in env_images:
            print(f"  环境 {env_id} 已生成，跳过")
            return

        if reference_environment_id:
            reference_info = env_images.get(str(reference_environment_id), {})
            reference_url = reference_info.get("image_url", "")
            reference_urls = [reference_url] if reference_url else []
            prompt = self.build_reference_variant_prompt(
                env_desc,
                style,
                reference_environment_id,
                has_reference=bool(reference_url),
            )
            if reference_url:
                print(f"  环境 {env_id} 基于本章节环境 {reference_environment_id} 图生图生成变体")
            else:
                print(f"  环境 {env_id} 标记为参考环境 {reference_environment_id} 的变体，但参考图暂无可用URL，退回文生图")
            result_path, image_url = self.image_gen.generate_reference_image(
                prompt,
                reference_urls,
                img_path,
                aspect_ratio=self.aspect_ratio,
                force=True,
            )
            source_path = reference_info.get("path", "")
            similarity = self._image_similarity_score(source_path, result_path or img_path)
            if reference_url and similarity is not None and similarity >= 0.9:
                print(f"  环境 {env_id} 与参考环境 {reference_environment_id} 构图过近，相似度 {similarity:.3f}，加强变体提示重试")
                retry_prompt = self.build_reference_variant_prompt(
                    env_desc,
                    style,
                    reference_environment_id,
                    has_reference=True,
                    force_camera_change=True,
                )
                result_path, image_url = self.image_gen.generate_reference_image(
                    retry_prompt,
                    reference_urls,
                    img_path,
                    aspect_ratio=self.aspect_ratio,
                    force=True,
                )
                retry_similarity = self._image_similarity_score(source_path, result_path or img_path)
                if retry_similarity is not None:
                    similarity = retry_similarity
                prompt = retry_prompt
                if similarity is not None and similarity >= 0.9:
                    print(f"  警告：环境 {env_id} 重试后仍与参考图过近，相似度 {similarity:.3f}")
            env_images[str(env_id)] = {
                "path": result_path or img_path,
                "image_url": image_url,
                "prompt": prompt,
                "environment_description": env_desc,
                "asset_action": "variant",
                "asset_reason": f"基于本章节环境 {reference_environment_id} 生成同场景变体",
                "reference_environment_id": reference_environment_id,
                "source_path": source_path,
            }
            if similarity is not None:
                env_images[str(env_id)]["reference_similarity"] = round(similarity, 4)
            print(f"  环境 {env_id} 完成")
            return

        prompt = self.build_prompt(env_desc, style)
        print(f"  环境 {env_id} 生成新环境图")
        print(prompt)
        result_path, image_url = self.image_gen._text_to_image(
            prompt,
            img_path,
            aspect_ratio=self.aspect_ratio,
            force=force_new,
        )

        env_images[str(env_id)] = {
            "path": result_path or img_path,
            "image_url": image_url,
            "prompt": prompt,
            "environment_description": env_desc,
            "asset_action": "new",
        }
        print(f"  环境 {env_id} 完成")

    def run_with_previous(self, storyboards, style="写实", previous_output_dir=None, model="gemini-3.1-pro-preview", previous_envs=None):
        print(f"\n[步骤4] 生成/复用环境图（风格: {style}，比例: {self.aspect_ratio}）...")
        os.makedirs(self.env_dir, exist_ok=True)

        previous_envs = previous_envs or self._load_previous_env_images(previous_output_dir)
        plan = self._plan_environment_assets(storyboards, previous_envs, model)
        env_images = {}

        for env in self._collect_current_environments(storyboards):
            env_id = env["environment_id"]
            env_desc = env["environment_description"]
            reference_environment_id = env.get("reference_environment_id")
            if reference_environment_id:
                self._generate_current_environment(env, style, env_images, force_new=True)
                continue

            action_info = plan.get(str(env_id), {"asset_action": "new", "previous_environment_id": None, "reason": ""})
            action = action_info.get("asset_action", "new")
            previous_id = action_info.get("previous_environment_id")
            previous_info = previous_envs.get(str(previous_id), {}) if previous_id is not None else {}
            img_path = os.path.join(self.env_dir, f"env_{int(env_id):03d}.png")
            prompt = self.build_prompt(env_desc, style)

            previous_path = previous_info.get("path", "")
            previous_url = previous_info.get("image_url", "")

            if action == "reuse" and previous_path and os.path.exists(previous_path):
                shutil.copy2(previous_path, img_path)
                env_images[str(env_id)] = {
                    "path": img_path,
                    "image_url": previous_url,
                    "prompt": previous_info.get("prompt", prompt),
                    "environment_description": env_desc,
                    "asset_action": "reuse",
                    "asset_reason": action_info.get("reason", ""),
                    "source_path": previous_path,
                    "previous_environment_id": previous_id,
                }
                print(f"  环境 {env_id} 复用已有环境 {previous_id}")
                continue

            reference_urls = [previous_url] if action == "update" and previous_url else []
            if action == "update":
                prompt = (
                    f"参考图1的场景空间结构、建筑/地形布局和美术风格，生成同一地点在本章节的新状态。"
                    f"变化原因：{action_info.get('reason', '')}。本章节环境：{env_desc}。"
                    f"\n{self.build_style_block(style)}\n"
                    f"画面要求：{self.build_aspect_ratio_prompt()}，不出现人物、角色、文字、字幕、标识或水印。"
                )
                print(f"  环境 {env_id} 参考已有环境 {previous_id} 生成新图")
                result_path, image_url = self.image_gen.generate_reference_image(
                    prompt,
                    reference_urls,
                    img_path,
                    aspect_ratio=self.aspect_ratio,
                    force=True,
                )
            else:
                print(f"  环境 {env_id} 生成新环境图")
                result_path, image_url = self.image_gen._text_to_image(
                    prompt,
                    img_path,
                    aspect_ratio=self.aspect_ratio,
                    force=True,
                )

            env_images[str(env_id)] = {
                "path": result_path or img_path,
                "image_url": image_url,
                "prompt": prompt,
                "environment_description": env_desc,
                "asset_action": action,
                "asset_reason": action_info.get("reason", ""),
                "source_path": previous_path if action == "update" else "",
                "previous_environment_id": previous_id,
            }
            print(f"  环境 {env_id} 完成")

        self.save(env_images)
        return env_images

    def build_style_block(self, style):
        style = str(style or "写实").strip() or "写实"
        style_rules = self.build_style_rules(style)
        return (
            f"本项目统一风格：{style}。\n"
            f"{style_rules}"
        )

    def build_aspect_ratio_prompt(self, shot_type="cinematic shot"):
        if self.aspect_ratio == "9:16":
            return f"9:16 竖版短视频环境参考图，vertical {shot_type}"
        if self.aspect_ratio == "16:9":
            return f"16:9 横版影视环境参考图，{shot_type}"
        return f"{self.aspect_ratio} 画幅环境参考图，{shot_type}"

    def build_style_rules(self, style):
        """把抽象 style 转成强约束，避免基础规则和项目风格互相冲突。"""
        style_text = str(style or "写实").strip()
        if any(keyword in style_text for keyword in ("动漫", "动画", "漫画", "手绘", "卡通", "二次元")):
            return (
                "风格硬性要求：手绘动漫角色设定图，清晰干净的线稿，统一赛璐璐/手绘上色，"
                "中式恐怖氛围可通过阴冷配色、夸张表情、诡异细节和光影表现；"
                "禁止生成真人照片质感、电影写实摄影、3D渲染、欧美超写实游戏原画或油画厚涂。"
            )
        if "水墨" in style_text or "国画" in style_text:
            return (
                "风格硬性要求：水墨/国画角色设定图，墨线、宣纸质感、留白和东方色彩必须明显；"
                "禁止生成真人照片质感、3D渲染、欧美厚涂或现代商业摄影。"
            )
        if "像素" in style_text:
            return (
                "风格硬性要求：像素风角色设定图，低分辨率像素块边缘、有限色盘、清晰轮廓；"
                "禁止生成真人照片质感、平滑写实绘画或3D渲染。"
            )
        if "写实" in style_text or "电影" in style_text:
            return (
                "风格硬性要求：电影级写实角色设定图，真实服装材质、自然肤色、真实皮肤纹理和棚拍镜头质感；"
                "禁止动漫、卡通、Q版、像素风、厚涂插画或明显游戏原画质感。"
            )
        return (
            f"风格硬性要求：所有线条、上色、材质、光影、面部表现和服装细节都必须服务于“{style_text}”；"
            "禁止写实摄影、动漫、厚涂、3D、像素等非指定风格混入。"
        )

    def build_prompt(self, env_desc, style="写实"):
        return (
            f"{self.build_style_block(style)}\n"
            f"当前环境设定：{env_desc}\n"
            f"画面要求：{self.build_aspect_ratio_prompt('cinematic wide shot')}，高质量，细节丰富；"
            "只画静态场景空间、建筑/地形布局、光线、天气、色调和氛围；"
            "不要出现人物、角色、文字、字幕、标识或水印；"
            "整张图必须严格执行本项目统一风格，保持一致的美术风格、线条/材质/光影/色彩分级和后期质感。"
        )

    def build_reference_variant_prompt(
        self,
        env_desc,
        style="写实",
        reference_environment_id=None,
        has_reference=True,
        force_camera_change=False,
    ):
        if has_reference:
            reference_instruction = (
                f"参考图1是本章节 environment_id {reference_environment_id} 的环境图。"
                "请保持参考图1的同一地点识别度、时代质感、主光线基调和美术风格，"
                "但必须重新取景：改变机位方向、镜头距离、景别或取景区域，生成同一场景内的环境变体图。"
            )
        else:
            reference_instruction = (
                f"当前环境是本章节 environment_id {reference_environment_id} 的同场景环境变体。"
                "请保持同一地点识别度、时代质感、主光线基调和美术风格，"
                "但必须重新取景：改变机位方向、镜头距离、景别或取景区域，生成同一场景内的环境图。"
            )
        camera_instruction = ""
        if force_camera_change:
            camera_instruction = (
                "\n强制构图差异：不要复刻参考图的同一远景、同一消失点、同一左右墙面比例或同一光斑位置；"
                "必须采用明显不同的镜头方案，例如近景、反打、侧向机位、低角度、局部空间、船舱内视角或洞壁贴近视角。"
                "画面中应能一眼看出这不是参考图的轻微重绘。"
            )
        return (
            f"{self.build_style_block(style)}\n"
            f"{reference_instruction}\n"
            f"{camera_instruction}\n"
            f"当前变体环境设定：{env_desc}\n"
            f"画面要求：{self.build_aspect_ratio_prompt('cinematic shot')}，高质量，细节丰富；"
            "只画静态场景空间、建筑/地形布局、光线、天气、色调、构图方位和氛围；"
            "不要出现人物、角色、文字、字幕、标识或水印；"
            "不能改变原场景的核心地点识别度，不能生成完全不同的新地点；"
            "禁止生成与参考图几乎相同的构图或只做轻微局部变化。"
        )

    def _image_similarity_score(self, reference_path, candidate_path):
        """Return rough visual similarity in [0, 1], where 1 is nearly identical."""
        if not reference_path or not candidate_path:
            return None
        if not os.path.exists(reference_path) or not os.path.exists(candidate_path):
            return None
        try:
            with Image.open(reference_path) as ref_img, Image.open(candidate_path) as cand_img:
                ref = ref_img.convert("L").resize((64, 36))
                cand = cand_img.convert("L").resize((64, 36))
                ref_values = list(ref.get_flattened_data())
                cand_values = list(cand.get_flattened_data())
        except Exception as exc:
            print(f"  警告：无法计算环境图相似度: {exc}")
            return None
        if not ref_values or len(ref_values) != len(cand_values):
            return None
        total_delta = sum(abs(a - b) for a, b in zip(ref_values, cand_values))
        max_delta = 255 * len(ref_values)
        return 1 - (total_delta / max_delta)

    def save(self, env_images):
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(env_images, f, ensure_ascii=False, indent=2)
        print(f"  环境图索引已保存: {self.save_path}")

    def load(self):
        with open(self.save_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _collect_current_environments(self, storyboards):
        envs = {}
        for sb in storyboards:
            env_id = sb.get("environment_id", sb.get("storyboard_id"))
            if env_id is None:
                continue
            try:
                env_id = int(env_id)
            except (TypeError, ValueError):
                continue
            env_desc = sb.get("environment")
            if not env_desc:
                continue
            item = envs.setdefault(str(env_id), {
                "environment_id": env_id,
                "environment_description": env_desc,
            })
            reference_environment_id = self._reference_environment_id_from_storyboard(sb, env_id, env_desc)
            if reference_environment_id and not item.get("reference_environment_id"):
                item["reference_environment_id"] = reference_environment_id
        return [envs[key] for key in sorted(envs, key=lambda value: int(value))]

    def _reference_environment_id_from_storyboard(self, storyboard, env_id, env_desc):
        reference_environment_id = self._normalize_reference_environment_id(
            storyboard.get("reference_environment_id"),
            current_environment_id=env_id,
        )
        if reference_environment_id:
            return reference_environment_id
        return self._extract_reference_environment_id(env_desc, current_environment_id=env_id)

    def _normalize_reference_environment_id(self, value, current_environment_id=None):
        if value in (None, "", "null"):
            return None
        try:
            reference_environment_id = int(value)
        except (TypeError, ValueError):
            return None
        if reference_environment_id <= 0 or reference_environment_id == current_environment_id:
            return None
        return reference_environment_id

    def _extract_reference_environment_id(self, env_desc, current_environment_id=None):
        if not isinstance(env_desc, str):
            return None
        patterns = [
            r"基于\s*environment_id\s*(\d+)",
            r"基于\s*环境\s*(\d+)",
            r"参考\s*environment_id\s*(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, env_desc, re.IGNORECASE)
            if not match:
                continue
            return self._normalize_reference_environment_id(
                match.group(1),
                current_environment_id=current_environment_id,
            )
        return None

    def _load_previous_env_images(self, previous_output_dir):
        previous_asset_dir = resolve_previous_asset_dir(previous_output_dir, "env_images.json")
        if not previous_asset_dir:
            return {}
        path = os.path.join(previous_asset_dir, "env_images.json")
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        normalized = {}
        for env_id, info in data.items():
            if isinstance(info, dict):
                normalized[str(env_id)] = info
            else:
                normalized[str(env_id)] = {"path": info, "image_url": "", "environment_description": ""}
        return normalized

    def _plan_environment_assets(self, storyboards, previous_envs, model):
        current_envs = [
            env for env in self._collect_current_environments(storyboards)
            if not env.get("reference_environment_id")
        ]
        if not previous_envs:
            return {str(env["environment_id"]): {"asset_action": "new", "previous_environment_id": None, "reason": "无上一章节环境资产"} for env in current_envs}

        previous_for_prompt = [
            {
                "environment_id": int(env_id),
                "environment_description": info.get("environment_description", "") or info.get("prompt", ""),
                "path": info.get("path", ""),
            }
            for env_id, info in previous_envs.items()
            if str(env_id).isdigit()
        ]
        prompt = PROMPT_PLAN_CHAPTER_ENV_ASSETS.format(
            previous_environments_json=json.dumps(previous_for_prompt, ensure_ascii=False, indent=2),
            current_environments_json=json.dumps(current_envs, ensure_ascii=False, indent=2),
        )
        response = self.llm.generate(prompt)
        parsed = self._parse_json(response)
        plan_items = parsed.get("environments", []) if isinstance(parsed, dict) else []
        plan = {}
        for item in plan_items:
            if not isinstance(item, dict):
                continue
            env_id = item.get("environment_id")
            if env_id is None:
                continue
            action = item.get("asset_action", "new")
            if action not in {"reuse", "update", "new"}:
                action = "new"
            plan[str(env_id)] = {
                "asset_action": action,
                "previous_environment_id": item.get("previous_environment_id"),
                "reason": item.get("reason", ""),
            }
        for env in current_envs:
            plan.setdefault(str(env["environment_id"]), {
                "asset_action": "new",
                "previous_environment_id": None,
                "reason": "模型未返回该环境，默认新建",
            })
        self._save_plan(plan)
        return plan

    def _save_plan(self, plan):
        with open(self.plan_save_path, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)

    def _parse_json(self, response):
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        print(f"警告：无法解析环境资产规划JSON，原始内容:\n{response[:500]}")
        return {}


if __name__ == "__main__":
    import argparse
    from core.project_paths import resolve_chapter_output_dir, resolve_project_path
    from steps.step1_extract_characters import CharacterExtractor
    from steps.step3_generate_storyboard import StoryboardGenerator
    from core.global_asset_index import GlobalAssetIndex

    parser = argparse.ArgumentParser(description="步骤4：生成或复用环境图")
    parser.add_argument("--output-dir", default="output", help="当前章节输出目录")
    parser.add_argument("--chapter-name", default="chapter_01", help="章节文件夹名；留空则直接使用 output-dir")
    parser.add_argument("--model", default="gemini-3.1-pro-preview", help="LLM 模型")
    parser.add_argument("--not-first-chapter", action="store_true", help="标记当前章节不是第一章节")
    parser.add_argument("--global-output-dir", default="", help="全局资产索引目录；默认使用 --output-dir")
    args = parser.parse_args()

    output_dir = resolve_project_path(args.output_dir)
    global_output_dir = resolve_project_path(args.global_output_dir) if args.global_output_dir else output_dir
    current_output_dir = resolve_chapter_output_dir(output_dir, args.chapter_name)
    char_data = CharacterExtractor(output_dir=current_output_dir, model=args.model).load()
    sbs = StoryboardGenerator(output_dir=current_output_dir, model=args.model).load()
    generator = EnvironmentImageGenerator(output_dir=current_output_dir)
    global_assets = GlobalAssetIndex(global_output_dir)
    if args.not_first_chapter:
        env_images = generator.run_with_previous(
            sbs,
            style=char_data.get("style", "写实"),
            previous_output_dir=None,
            model=args.model,
            previous_envs=global_assets.load_environments(),
        )
    else:
        env_images = generator.run(sbs, style=char_data.get("style", "写实"))
    global_assets.save_environments_from_chapter(env_images, args.chapter_name)
