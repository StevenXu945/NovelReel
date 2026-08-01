import json
import os
import shutil
from provider.image_generator import ImageGenerator
from core.project_paths import resolve_chapter_output_dir, resolve_previous_asset_dir


class PropImageGenerator:
    """为关键道具生成可复用道具设定图。"""
    BASE_VISUAL_BIBLE = ""

    def __init__(self, output_dir="output"):
        self.image_gen = ImageGenerator(output_dir=output_dir)
        self.output_dir = output_dir
        self.props_dir = os.path.join(output_dir, "props")
        self.save_path = os.path.join(output_dir, "prop_images.json")

    @staticmethod
    def build_style_rules(style):
        """把抽象 style 转成道具图的强约束。"""
        style_text = str(style or "写实").strip()
        if any(keyword in style_text for keyword in ("动漫", "动画", "漫画", "手绘", "卡通", "二次元")):
            return (
                "风格硬性要求：手绘动漫道具设定图，清晰干净的线稿，统一赛璐璐/手绘上色；"
                "禁止生成真人照片质感、电影写实摄影、3D渲染、欧美超写实游戏原画或油画厚涂。"
            )
        if "水墨" in style_text or "国画" in style_text:
            return (
                "风格硬性要求：水墨/国画道具设定图，墨线、宣纸质感、留白和东方色彩必须明显；"
                "禁止生成真人照片质感、3D渲染、欧美厚涂或现代商业摄影。"
            )
        if "像素" in style_text:
            return (
                "风格硬性要求：像素风道具设定图，低分辨率像素块边缘、有限色盘、清晰轮廓；"
                "禁止生成真人照片质感、平滑写实绘画或3D渲染。"
            )
        if "写实" in style_text or "电影" in style_text:
            return (
                "风格硬性要求：电影级写实道具设定图，真实材质纹理、自然光影和棚拍镜头质感；"
                "禁止动漫、卡通、像素风、厚涂插画或明显游戏原画质感。"
            )
        return (
            f"风格硬性要求：所有线条、上色、材质、光影和细节都必须服务于{style_text}；"
            "禁止写实摄影、动漫、厚涂、3D、像素等非指定风格混入。"
        )

    def build_prompt(self, prop, style="写实"):
        style = str(style or "写实").strip() or "写实"
        style_rules = self.build_style_rules(style)
        visual = prop.get("visual_description", "").rstrip("。")
        function = prop.get("function", "").rstrip("。")
        prop_type = prop.get("prop_type", "")
        return (
            f"本项目统一风格：{style}。\n"
            f"{style_rules}\n"
            f"当前道具类型：{prop_type}。\n"
            f"当前道具设定：{visual}。\n"
            f"剧情功能：{function}。\n"
            "画面要求：单个道具设定图，白色背景，主体居中，完整展示道具外形和关键细节；"
            "不要出现人物、手、环境、文字、字幕、标识或水印。"
        )

    def run(self, data, style="写实"):
        props = self._normalize_props(data)
        print(f"\n[道具] 生成道具设定图（风格: {style}）...")
        os.makedirs(self.props_dir, exist_ok=True)
        prop_images = self.load() if os.path.exists(self.save_path) else {}

        for prop in props:
            name = prop["name"]
            prop_id = prop["id"]
            save_path = os.path.join(self.props_dir, f"prop_{prop_id}.png")
            if name in prop_images and os.path.exists(save_path):
                print(f"  道具 [{name}] (prop#{prop_id}) 图片已存在，跳过")
                continue

            prompt = self.build_prompt(prop, style)
            print(f"  道具 [{name}] 生成新增道具图")
            result_path, image_url = self.image_gen._text_to_image(prompt, save_path, aspect_ratio="1:1")
            if result_path and os.path.exists(save_path):
                prop_images[name] = {
                    "path": save_path,
                    "image_url": image_url,
                    "prompt": prompt,
                    "prop_id": prop_id,
                    "asset_action": prop.get("asset_action", "new"),
                    "asset_reason": prop.get("asset_reason", ""),
                }
                self.save(prop_images)
                print(f"  道具 [{name}] (prop#{prop_id}) 设定图生成完成")
            else:
                print(f"  道具 [{name}] (prop#{prop_id}) 生成失败，下次运行会重试")

        self.save(prop_images)
        return prop_images

    def run_with_previous(self, data, previous_output_dir=None, previous_images=None, style="写实"):
        props = self._normalize_props(data)
        print(f"\n[道具] 生成/复用道具设定图（风格: {style}）...")
        os.makedirs(self.props_dir, exist_ok=True)
        previous_images = previous_images or self._load_previous_prop_images(previous_output_dir)
        prop_images = self.load() if os.path.exists(self.save_path) else {}

        for prop in props:
            name = prop["name"]
            prop_id = prop["id"]
            action = prop.get("asset_action", "new")
            previous_name = prop.get("previous_name") or name
            save_path = os.path.join(self.props_dir, f"prop_{prop_id}.png")

            if name in prop_images and os.path.exists(save_path):
                print(f"  道具 [{name}] (prop#{prop_id}) 图片已存在，跳过")
                continue

            previous_info = previous_images.get(previous_name) or previous_images.get(name) or {}
            previous_path = previous_info.get("path", "")
            previous_url = previous_info.get("image_url", "")
            prompt = self.build_prompt(prop, style)

            if action == "reuse" and previous_path and os.path.exists(previous_path):
                shutil.copy2(previous_path, save_path)
                prop_images[name] = {
                    "path": save_path,
                    "image_url": previous_url,
                    "prompt": previous_info.get("prompt", prompt),
                    "prop_id": prop_id,
                    "asset_action": "reuse",
                    "asset_reason": prop.get("asset_reason", ""),
                    "source_path": previous_path,
                }
                self.save(prop_images)
                print(f"  道具 [{name}] 复用上一章节图片")
                continue

            reference_urls = [previous_url] if action == "update" and previous_url else []
            if action == "update":
                prompt = (
                    f"参考图1中同一道具的核心形状、材质、颜色、纹理和标志性细节，保持道具一致性。"
                    f"根据本章节变化更新道具状态：{prop.get('asset_reason', '')}。\n"
                    f"{prompt}"
                )
                print(f"  道具 [{name}] 参考上一章节生成新图: {prop.get('asset_reason', '')}")
                result_path, image_url = self.image_gen.generate_reference_image(
                    prompt,
                    reference_urls,
                    save_path,
                    aspect_ratio="1:1",
                    force=True,
                    reference_image_paths=[previous_path] if previous_path and os.path.exists(previous_path) else [],
                )
            else:
                print(f"  道具 [{name}] 生成新增道具图")
                result_path, image_url = self.image_gen._text_to_image(prompt, save_path, aspect_ratio="1:1", force=True)

            if result_path and os.path.exists(save_path):
                prop_images[name] = {
                    "path": save_path,
                    "image_url": image_url,
                    "prompt": prompt,
                    "prop_id": prop_id,
                    "asset_action": action,
                    "asset_reason": prop.get("asset_reason", ""),
                    "source_path": previous_path if action == "update" else "",
                }
                self.save(prop_images)
                print(f"  道具 [{name}] (prop#{prop_id}) 设定图完成")
            else:
                print(f"  道具 [{name}] (prop#{prop_id}) 生成失败，下次运行会重试")

        self.save(prop_images)
        return prop_images

    def save(self, prop_images):
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(prop_images, f, ensure_ascii=False, indent=2)
        print(f"  道具图片索引已保存: {self.save_path}")

    def load(self):
        with open(self.save_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _normalize_props(self, data):
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("props", [])
        return []

    def _load_previous_prop_images(self, previous_output_dir):
        previous_asset_dir = resolve_previous_asset_dir(previous_output_dir, "prop_images.json")
        if not previous_asset_dir:
            return {}
        path = os.path.join(previous_asset_dir, "prop_images.json")
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        normalized = {}
        for name, info in data.items():
            normalized[name] = info if isinstance(info, dict) else {"path": info, "image_url": "", "prompt": ""}
        return normalized


if __name__ == "__main__":
    import argparse
    from core.global_asset_index import GlobalAssetIndex
    from core.project_paths import resolve_chapter_output_dir, resolve_project_path
    from steps.step1_extract_characters import CharacterExtractor
    from steps.step2_extract_props import PropExtractor

    parser = argparse.ArgumentParser(description="步骤2b：生成或复用道具设定图")
    parser.add_argument("--output-dir", default="output", help="当前章节输出目录")
    parser.add_argument("--chapter-name", default="chapter_01", help="章节文件夹名；留空则直接使用 output-dir")
    parser.add_argument("--model", default="gemini-3.1-pro-preview", help="兼容参数；本步骤不直接调用 LLM")
    parser.add_argument("--not-first-chapter", action="store_true", help="标记当前章节不是第一章节")
    parser.add_argument("--global-output-dir", default="", help="全局资产索引目录；默认使用 --output-dir")
    args = parser.parse_args()

    output_dir = resolve_project_path(args.output_dir)
    global_output_dir = resolve_project_path(args.global_output_dir) if args.global_output_dir else output_dir
    current_output_dir = resolve_chapter_output_dir(output_dir, args.chapter_name)
    style = CharacterExtractor(output_dir=current_output_dir, model=args.model).load().get("style", "写实")
    data = PropExtractor(output_dir=current_output_dir, model=args.model).load()
    generator = PropImageGenerator(output_dir=current_output_dir)
    global_assets = GlobalAssetIndex(global_output_dir)
    if args.not_first_chapter:
        prop_images = generator.run_with_previous(
            data,
            previous_images=global_assets.load_prop_images(),
            style=style,
        )
    else:
        prop_images = generator.run(data, style=style)
    global_assets.save_prop_images_from_chapter(prop_images)
