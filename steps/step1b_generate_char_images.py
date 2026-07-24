import json
import os
import shutil
from provider.image_generator import ImageGenerator
from core.project_paths import resolve_previous_asset_dir


class CharacterImageGenerator:
    """步骤2：为每个角色生成角色设定图（脸部特写 + 全身正面/侧面/背面三视图）"""
    BASE_VISUAL_BIBLE = ""

    OLD_CONFLICT_MARKERS = (
        "不要动漫",
        "不要游戏原画",
        "不要厚涂插画",
        "自然肤色和真实皮肤纹理",
        "电影级写实角色设定图",
        "写实古风乡土质感",
        "从左到右依次为站立的全身正面、全身侧面、全身背面。高质量",
    )

    def __init__(self, output_dir="output"):
        self.image_gen = ImageGenerator(output_dir=output_dir, provider="seedream")
        self.output_dir = output_dir
        self.chars_dir = os.path.join(output_dir, "characters")
        self.save_path = os.path.join(output_dir, "character_images.json")

    def build_prompt(self, char, style="写实"):
        """构建角色设定图 prompt：左侧脸部特写，右侧全身三视图"""
        age = char.get('age', '')
        brief_description = str(char.get('brief_description') or '').rstrip("。")
        appearance = char['appearance'].rstrip("。")
        clothing = char['clothing'].rstrip("。")
        age_str = f"{age}，" if age else ""
        brief_description_line = f"当前角色定位：{brief_description}。\n" if brief_description else ""
        style_rules = self._build_style_rules(style)
        return (
            f"本项目统一风格：{style}。\n"
            f"{style_rules}\n"
            f"{brief_description_line}"
            f"当前角色设定：{age_str}{appearance}。\n"
            f"当前角色服装：{clothing}。\n"
            f"画面要求：角色设定图，白色背景，从左到右依次为站立的全身正面、全身侧面、全身背面。"
            f"三个人物视图必须等高、等比例、脚底在同一水平线上，主体高度占画面高度约80%-88%，"
            f"画面边缘留白均匀，不能出现某一视图特别小或特别大。"
            f"高质量，细节丰富，整张图必须符合上面的角色视觉圣经。"
        )

    @staticmethod
    def build_style_rules(style):
        """把抽象 style 转成强约束，避免基础规则和项目风格互相冲突。"""
        style_text = str(style or "写实").strip()
        if any(keyword in style_text for keyword in ("动漫", "动画", "漫画", "手绘", "卡通", "二次元")):
            return (
                "风格硬性要求：手绘动漫角色设定图，清晰干净的线稿，统一赛璐璐/手绘上色，"
                "采用标准影视动漫人物比例，儿童角色也必须保持符合年龄的正常身体比例，"
                "中式恐怖氛围可通过阴冷配色、夸张表情、诡异细节和光影表现；"
                "禁止生成真人照片质感、电影写实摄影、3D渲染、欧美超写实游戏原画、油画厚涂、Q版、"
                "大头娃娃、二头身、三头身或儿童绘本风。"
            )
        if "水墨" in style_text or "国画" in style_text:
            return (
                "风格硬性要求：水墨/国画角色设定图，墨线、宣纸质感、留白和东方色彩必须明显；"
                "禁止生成真人照片质感、3D渲染、欧美厚涂、现代商业摄影、Q版或大头娃娃比例。"
            )
        if "像素" in style_text:
            return (
                "风格硬性要求：像素风角色设定图，低分辨率像素块边缘、有限色盘、清晰轮廓；"
                "禁止生成真人照片质感、平滑写实绘画、3D渲染、Q版或大头娃娃比例。"
            )
        if "写实" in style_text or "电影" in style_text:
            return (
                "风格硬性要求：电影级写实角色设定图，真实服装材质、自然肤色、真实皮肤纹理和棚拍镜头质感；"
                "禁止动漫、卡通、Q版、大头娃娃、二头身、三头身、像素风、厚涂插画或明显游戏原画质感。"
            )
        return (
            f"风格硬性要求：所有线条、上色、材质、光影、面部表现和服装细节都必须服务于“{style_text}”；"
            "禁止写实摄影、动漫、厚涂、3D、像素、Q版、大头娃娃、二头身、三头身等非指定风格混入。"
        )

    def _build_style_rules(self, style):
        return self.build_style_rules(style)

    def _is_cached_prompt_stale(self, cached_info, style):
        prompt = cached_info.get("prompt", "")
        if f"本项目统一风格：{style}" not in prompt:
            return True
        if any(marker in prompt for marker in self.OLD_CONFLICT_MARKERS):
            return True
        return False

    def run(self, data):
        """data: dict with 'style' and 'characters' keys, or list of characters for backward compat"""
        if isinstance(data, list):
            style, characters = "写实", data
        else:
            style, characters = data.get("style", "写实"), data["characters"]

        print(f"\n[步骤2] 生成角色设定图（风格: {style}）...")
        os.makedirs(self.chars_dir, exist_ok=True)

        # 加载已有结果，跳过已成功生成的角色
        character_images = {}
        if os.path.exists(self.save_path):
            character_images = self.load()

        for char in characters:
            name = char["name"]
            char_id = char["id"]
            action = self._normalized_asset_action(char)
            previous_name = char.get("previous_name") or name
            save_path = os.path.join(self.chars_dir, f"character_{char_id}.png")

            cached_info = character_images.get(name, {})
            should_regenerate = self._is_cached_prompt_stale(cached_info, style) if cached_info else False
            if action in {"update", "new_variant"} and cached_info and cached_info.get("asset_action") != action:
                should_regenerate = True

            # 跳过已存在且 prompt 未过期的图片
            if name in character_images and os.path.exists(save_path) and not should_regenerate:
                print(f"  角色 [{name}] (character#{char_id}) 图片已存在，跳过")
                continue

            full_prompt = self.build_prompt(char, style)
            uses_reference = action in {"update", "new_variant"}
            reference_info = character_images.get(previous_name, {}) if uses_reference else {}
            reference_url = reference_info.get("image_url", "")
            reference_path = reference_info.get("path", "")
            reference_urls = [reference_url] if reference_url else []
            if action == "new_variant":
                if not reference_urls:
                    print(
                        f"  错误：换装角色 [{name}] 未找到同章基础造型 [{previous_name}] 的图片URL，"
                        "为避免角色漂移，本次不退回文生图"
                    )
                    continue
                full_prompt = (
                    "参考图1是同一角色的基础造型。严格保持其脸部、五官、发型、发色、年龄感、"
                    "肤色、体型、身材比例和身份辨识特征一致，只替换为下述新服装或身份造型。"
                    "不要改变人物身份，不要沿用参考图中的旧服装，不要生成第二个人物。"
                    f"换装原因：{char.get('asset_reason', '')}。\n{full_prompt}"
                )
                print(f"  角色 [{name}] 基于同章基础造型 [{previous_name}] 换装图生图")
            elif action == "update":
                full_prompt = (
                    "参考图1中同一角色原形态的脸部、五官、体型、服装来源和身份特征，"
                    "保持人物身份与画风一致；在此基础上生成下述新形态，不要生成无关的新角色。"
                    f"形态变化原因：{char.get('asset_reason', '')}。\n{full_prompt}"
                )
                if reference_urls:
                    print(f"  角色 [{name}] 基于同章角色 [{previous_name}] 图生图")
                else:
                    print(f"  警告：角色 [{name}] 未找到同章参考角色 [{previous_name}] 的图片URL，退回文生图")
            print(full_prompt)
            result_path, image_url = self.image_gen.generate_character_image(
                full_prompt,
                save_path=save_path,
                force=should_regenerate or uses_reference,
                reference_image_urls=reference_urls,
            )

            if result_path and os.path.exists(save_path):
                character_images[name] = {
                    "path": save_path,
                    "image_url": image_url,
                    "prompt": full_prompt,
                    "char_id": char_id,
                    "asset_action": action,
                    "asset_reason": char.get("asset_reason", ""),
                    "source_path": reference_path if uses_reference else "",
                }
                # 每成功一张就保存索引，避免中途失败丢失进度
                self.save(character_images)
                print(f"  角色 [{name}] (character#{char_id}) 设定图生成完成")
            else:
                print(f"  角色 [{name}] (character#{char_id}) 生成失败，下次运行会重试")

        self.save(character_images)
        return character_images

    def run_with_previous(self, data, previous_output_dir, previous_images=None):
        """后续章节角色图生成：按 asset_action 复用、参考更新或新增。"""
        if isinstance(data, list):
            style, characters = "写实", data
        else:
            style, characters = data.get("style", "写实"), data["characters"]

        print(f"\n[步骤2] 生成/复用角色设定图（风格: {style}）...")
        os.makedirs(self.chars_dir, exist_ok=True)
        previous_images = previous_images or self._load_previous_character_images(previous_output_dir)
        character_images = self.load() if os.path.exists(self.save_path) else {}

        for char in characters:
            name = char["name"]
            char_id = char["id"]
            action = self._normalized_asset_action(char)
            previous_name = char.get("previous_name") or name
            save_path = os.path.join(self.chars_dir, f"character_{char_id}.png")
            cached_info = character_images.get(name, {})
            should_regenerate = self._is_cached_prompt_stale(cached_info, style) if cached_info else False

            if name in character_images and os.path.exists(save_path) and not should_regenerate:
                print(f"  角色 [{name}] (character#{char_id}) 图片已存在，跳过")
                continue

            previous_info = (
                character_images.get(previous_name)
                or previous_images.get(previous_name)
                or previous_images.get(name)
                or {}
            )
            previous_path = previous_info.get("path", "")
            previous_url = previous_info.get("image_url", "")
            previous_prompt_stale = self._is_cached_prompt_stale(previous_info, style) if previous_info else False

            if action == "reuse" and previous_path and os.path.exists(previous_path) and not previous_prompt_stale:
                shutil.copy2(previous_path, save_path)
                prompt = previous_info.get("prompt", self.build_prompt(char, style))
                image_url = previous_url
                character_images[name] = {
                    "path": save_path,
                    "image_url": image_url,
                    "prompt": prompt,
                    "char_id": char_id,
                    "asset_action": "reuse",
                    "asset_reason": char.get("asset_reason", ""),
                    "source_path": previous_path,
                }
                self.save(character_images)
                print(f"  角色 [{name}] 复用上一章节图片")
                continue

            full_prompt = self.build_prompt(char, style)
            uses_reference = action in {"update", "new_variant"}
            reference_urls = [previous_url] if uses_reference and previous_url else []
            if action == "new_variant":
                if not reference_urls:
                    print(
                        f"  错误：换装角色 [{name}] 未找到基础造型 [{previous_name}] 的图片URL，"
                        "为避免角色漂移，本次不退回文生图"
                    )
                    continue
                full_prompt = (
                    "参考图1是同一角色的基础造型。严格保持其脸部、五官、发型、发色、年龄感、"
                    "肤色、体型、身材比例和身份辨识特征一致，只替换为下述新服装或身份造型。"
                    "不要改变人物身份，不要沿用参考图中的旧服装，不要生成第二个人物。"
                    f"换装原因：{char.get('asset_reason', '')}。\n{full_prompt}"
                )
                print(f"  角色 [{name}] 基于基础造型 [{previous_name}] 换装图生图")
            elif action == "update":
                full_prompt = (
                    f"参考图1中同一角色的脸部、五官、体型和身份特征，保持角色一致性。"
                    f"根据本章节变化更新角色设定：{char.get('asset_reason', '')}。\n"
                    f"{full_prompt}"
                )
                print(f"  角色 [{name}] 参考上一章节生成新图: {char.get('asset_reason', '')}")
            elif action == "reuse" and previous_prompt_stale:
                print(f"  角色 [{name}] 上一章节图片 prompt 已过期，按当前一致性规则重生成")
            else:
                print(f"  角色 [{name}] 生成新增角色图")

            result_path, image_url = self.image_gen.generate_character_image(
                full_prompt,
                save_path=save_path,
                force=True,
                reference_image_urls=reference_urls,
            )

            if result_path and os.path.exists(save_path):
                character_images[name] = {
                    "path": save_path,
                    "image_url": image_url,
                    "prompt": full_prompt,
                    "char_id": char_id,
                    "asset_action": action,
                    "asset_reason": char.get("asset_reason", ""),
                    "source_path": previous_path if uses_reference else "",
                }
                self.save(character_images)
                print(f"  角色 [{name}] (character#{char_id}) 设定图完成")
            else:
                print(f"  角色 [{name}] (character#{char_id}) 生成失败，下次运行会重试")

        self.save(character_images)
        return character_images

    @staticmethod
    def _normalized_asset_action(char):
        """兼容旧数据：把带明确换装关联信息的 new 视为 new_variant。"""
        action = char.get("asset_action", "new")
        if action == "new_variant":
            return action
        reason = str(char.get("asset_reason") or "")
        if action == "new" and char.get("previous_name") and any(
            marker in reason for marker in ("换装", "新造型", "身份造型", "独立角色资产")
        ):
            return "new_variant"
        return action

    def regenerate_one(self, char_name, prompt, char_id=None):
        """根据给定 prompt 重新生成单个角色图片"""
        os.makedirs(self.chars_dir, exist_ok=True)
        if char_id is None:
            # 从已有数据中查找
            existing = self.load()
            info = existing.get(char_name, {})
            char_id = info.get("char_id", 1)
        save_path = os.path.join(self.chars_dir, f"character_{char_id}.png")
        result_path, image_url = self.image_gen.generate_character_image(prompt, save_path=save_path, force=True)
        return result_path or save_path, image_url

    def save(self, character_images):
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(character_images, f, ensure_ascii=False, indent=2)
        print(f"  角色图片索引已保存: {self.save_path}")

    def load(self):
        with open(self.save_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_previous_character_images(self, previous_output_dir):
        previous_asset_dir = resolve_previous_asset_dir(previous_output_dir, "character_images.json")
        if not previous_asset_dir:
            return {}
        path = os.path.join(previous_asset_dir, "character_images.json")
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        normalized = {}
        for name, info in data.items():
            if isinstance(info, dict):
                normalized[name] = info
            else:
                normalized[name] = {"path": info, "image_url": "", "prompt": ""}
        return normalized


if __name__ == "__main__":
    import argparse
    from core.project_paths import resolve_chapter_output_dir, resolve_project_path
    from steps.step1_extract_characters import CharacterExtractor
    from core.global_asset_index import GlobalAssetIndex

    parser = argparse.ArgumentParser(description="步骤2：生成或复用角色设定图")
    parser.add_argument("--output-dir", default="output", help="当前章节输出目录")
    parser.add_argument("--chapter-name", default="chapter_01", help="章节文件夹名；留空则直接使用 output-dir")
    parser.add_argument("--model", default="gemini-3.1-pro-preview", help="兼容参数；本步骤不直接调用 LLM")
    parser.add_argument("--not-first-chapter", action="store_true", help="标记当前章节不是第一章节")
    parser.add_argument("--global-output-dir", default="", help="全局资产索引目录；默认使用 --output-dir")
    args = parser.parse_args()

    output_dir = resolve_project_path(args.output_dir)
    global_output_dir = resolve_project_path(args.global_output_dir) if args.global_output_dir else output_dir
    current_output_dir = resolve_chapter_output_dir(output_dir, args.chapter_name)
    data = CharacterExtractor(output_dir=current_output_dir, model=args.model).load()
    generator = CharacterImageGenerator(output_dir=current_output_dir)
    global_assets = GlobalAssetIndex(global_output_dir)
    if args.not_first_chapter:
        character_images = generator.run_with_previous(
            data,
            None,
            previous_images=global_assets.load_character_images(),
        )
    else:
        character_images = generator.run(data)
    global_assets.save_character_images_from_chapter(character_images)
