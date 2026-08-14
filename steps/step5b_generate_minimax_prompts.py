import argparse
import json
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.project_paths import resolve_chapter_output_dir, resolve_project_path
from provider.llm_provider import LLMClient


class MinimaxPromptGenerator:
    """步骤5b：一次 LLM 调用将整章 video_prompt 转为 SKILL.md 规定的格式。"""

    def __init__(self, output_dir="output", model=None, skill_path=None, llm=None):
        self.output_dir = output_dir
        self.save_path = os.path.join(output_dir, "minimax.json")
        self.skill_path = skill_path or os.path.join(os.path.dirname(__file__), "SKILL.md")
        self.llm = llm or LLMClient(model=model)

    def run(self, storyboards=None, characters=None, props=None, env_images=None):
        storyboards = storyboards if storyboards is not None else self._load_json("storyboards.json")
        characters = characters if characters is not None else self._load_json("characters.json")
        props = props if props is not None else self._load_json_with_fallback("prop.json", "props.json")
        env_images = env_images if env_images is not None else self._load_json("env_images.json")
        with open(self.skill_path, "r", encoding="utf-8") as f:
            skill = f.read()

        source_items = self._build_source_items(storyboards, characters, props, env_images)
        prompt = self._build_prompt(skill, source_items)

        # 整章只调用一次大模型。
        response = self.llm.generate(prompt)
        result = self._parse_json(response)
        minimax_items = self._normalize_result(result)
        self._validate_model_result(source_items, minimax_items)
        minimax_items = self._attach_source_ids(source_items, minimax_items)

        os.makedirs(self.output_dir, exist_ok=True)
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(minimax_items, f, ensure_ascii=False, indent=2)
        print(f"步骤5b完成，Minimax 提示词已保存: {self.save_path}")
        return minimax_items

    def _build_source_items(self, storyboards, characters, props, env_images):
        character_items = characters.get("characters", characters) if isinstance(characters, dict) else characters
        prop_items = props.get("props", props) if isinstance(props, dict) else props
        character_map = self._index_by_id(character_items)
        prop_map = self._index_by_id(prop_items)

        items = []
        for storyboard in storyboards:
            character_ids = storyboard.get("character_ids", [])
            prop_ids = storyboard.get("prop_ids", [])
            references = []

            env_id = storyboard.get("environment_id")
            env_info = env_images.get(str(env_id), {}) if isinstance(env_images, dict) else {}
            if isinstance(env_info, str):
                env_description = storyboard.get("environment", "")
            else:
                env_description = env_info.get("environment_description", "")
            env_description = env_description or storyboard.get("environment", "")
            references.append({
                "picture": "<Picture 1>",
                "asset_type": "environment",
                "asset_id": env_id,
                "description": env_description,
            })

            picture_number = 2
            for character_id in character_ids:
                character = character_map.get(str(character_id), {})
                references.append({
                    "picture": f"<Picture {picture_number}>",
                    "asset_type": "character",
                    "asset_id": character_id,
                    "description": character.get("appearance", ""),
                })
                picture_number += 1

            for prop_id in prop_ids:
                prop = prop_map.get(str(prop_id), {})
                references.append({
                    "picture": f"<Picture {picture_number}>",
                    "asset_type": "prop",
                    "asset_id": prop_id,
                    "description": prop.get("visual_description", ""),
                })
                picture_number += 1

            items.append({
                "storyboard_id": storyboard.get("storyboard_id"),
                "environment_id": env_id,
                "character_ids": character_ids,
                "prop_ids": prop_ids,
                "duration": storyboard.get("duration"),
                "video_prompt": storyboard.get("video_prompt", ""),
                "reference_descriptions": references,
            })
        return items

    @staticmethod
    def _build_prompt(skill, source_items):
        return f"""请严格按照下方 SKILL.md，将全部分镜的 video_prompt 转换为规定格式。

补充说明：
1. 一次处理全部分镜，不遗漏、不合并、不拆分。
2. 你不会看到图片。参考图片内容只能来自 reference_descriptions，不得补充其中没有的稳定视觉特征。
3. 原 video_prompt 中的“图N”对应 reference_descriptions 中的 <Picture N>。
4. 输出 JSON 数组，每项只能包含 storyboard_id 和 video_prompt。
5. 不要输出 Markdown 代码围栏、解释或 JSON 之外的内容。

--- SKILL.md ---
{skill}
--- SKILL.md END ---

Input storyboards:
{json.dumps(source_items, ensure_ascii=False, indent=2)}
"""

    @staticmethod
    def _index_by_id(items):
        result = {}
        for item in items or []:
            if isinstance(item, dict) and item.get("id") is not None:
                result[str(item["id"])] = item
        return result

    def _load_json(self, filename):
        path = os.path.join(self.output_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"缺少步骤5b输入文件: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_json_with_fallback(self, *filenames):
        for filename in filenames:
            path = os.path.join(self.output_dir, filename)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        candidates = ", ".join(os.path.join(self.output_dir, name) for name in filenames)
        raise FileNotFoundError(f"缺少步骤5b输入文件，尝试过: {candidates}")

    @staticmethod
    def _parse_json(response):
        text = str(response or "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
        raise ValueError(f"大模型返回内容不是有效 JSON: {text[:500]}")

    @staticmethod
    def _normalize_result(result):
        if isinstance(result, dict):
            for key in ("storyboards", "items", "minimax"):
                if isinstance(result.get(key), list):
                    result = result[key]
                    break
        if not isinstance(result, list):
            raise ValueError("大模型返回 JSON 必须是数组")
        return result

    @staticmethod
    def _validate_model_result(source_items, result_items):
        expected_ids = [item["storyboard_id"] for item in source_items]
        actual_ids = [item.get("storyboard_id") for item in result_items if isinstance(item, dict)]
        if actual_ids != expected_ids:
            raise ValueError(f"返回的 storyboard_id 不完整或顺序错误，期望 {expected_ids}，实际 {actual_ids}")

        required_sections = (
            "subject_definitions:",
            "summary:",
            "retention_analysis:",
            "detailed_description:",
            "overall_soundscape:",
            "non_diegetic_music:",
        )
        source_by_id = {item["storyboard_id"]: item for item in source_items}
        for item in result_items:
            if set(item) != {"storyboard_id", "video_prompt"}:
                raise ValueError(f"分镜 {item.get('storyboard_id')} 包含多余或缺失字段")
            video_prompt = item.get("video_prompt")
            if not isinstance(video_prompt, str) or not video_prompt.strip():
                raise ValueError(f"分镜 {item.get('storyboard_id')} 的 video_prompt 为空")
            positions = [video_prompt.find(section) for section in required_sections]
            if any(position < 0 for position in positions) or positions != sorted(positions):
                raise ValueError(f"分镜 {item.get('storyboard_id')} 未按 SKILL.md 顺序输出六个部分")
            duration = source_by_id[item["storyboard_id"]].get("duration")
            shot_numbers = [int(value) for value in re.findall(r"\[Shot\s+(\d+)\]", video_prompt)]
            if not shot_numbers:
                raise ValueError(f"分镜 {item.get('storyboard_id')} 的 detailed_description 缺少 [Shot 1]")
            if isinstance(duration, (int, float)) and duration >= 15 and len(set(shot_numbers)) < 2:
                raise ValueError(f"分镜 {item.get('storyboard_id')} 时长为 {duration} 秒，至少需要两个 Shot")

    @staticmethod
    def _attach_source_ids(source_items, result_items):
        """ID 字段取自原分镜，避免模型漏写或篡改资产引用。"""
        source_by_id = {item["storyboard_id"]: item for item in source_items}
        output = []
        for item in result_items:
            source = source_by_id[item["storyboard_id"]]
            video_prompt = re.sub(
                r"(non_diegetic_music:\s*)[\s\S]*$",
                r"\1N/A",
                item["video_prompt"],
                count=1,
            )
            output.append({
                "storyboard_id": item["storyboard_id"],
                "duration": source.get("duration"),
                "environment_id": source.get("environment_id"),
                "character_ids": source.get("character_ids", []),
                "prop_ids": source.get("prop_ids", []),
                "video_prompt": video_prompt,
            })
        return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="步骤5b：将 storyboards.json 转换为 Minimax 提示词")
    parser.add_argument("--output-dir", default="output", help="章节输出根目录")
    parser.add_argument("--chapter-name", default="chapter_01", help="章节文件夹名；留空则直接使用 output-dir")
    parser.add_argument("--model", default=None, help="LLM 模型；默认读取 config.yaml")
    parser.add_argument("--skill-path", default=None, help="SKILL.md 路径；默认使用 steps/SKILL.md")
    args = parser.parse_args()

    output_dir = resolve_project_path(args.output_dir)
    current_output_dir = resolve_chapter_output_dir(output_dir, args.chapter_name)
    skill_path = resolve_project_path(args.skill_path) if args.skill_path else None
    MinimaxPromptGenerator(
        output_dir=current_output_dir,
        model=args.model,
        skill_path=skill_path,
    ).run()
