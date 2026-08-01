import json
import os
import re
from provider.llm_provider import LLMClient
from core.project_paths import resolve_chapter_output_dir, resolve_previous_asset_dir


PROMPT_EXTRACT_PROPS = """你是一个专业的影视道具资产统筹。请仔细阅读以下小说章节内容，提取所有需要建立视觉资产的关键道具。

要求：
1. 只提取核心道具。核心道具是本章节中具有明显剧情意义、异常性、身份象征、能力属性、线索价值或后续伏笔的具体物品。
2. 核心道具必须同时满足：
   - 是具体物品，不是人物、地点、组织、抽象概念、能力名称或自然现象。
   - 在本章节中出现 2 次及以上，或虽然出现次数不多但被明显强调为关键物。
   - 不是普通背景物、生活用品、装饰物、交通工具、食物、普通武器、普通衣物、普通工具。
   - 不是配角临时使用、随手持有、一次性动作相关的物品。
   - 对主角、主要冲突、任务目标、秘密线索、身份识别、能力机制、战斗胜负或后续剧情有明显影响。
3. 优先提取：
   - 有专名的物品，例如“玄铁令”“噬魂珠”“无字天书”。
   - 被反复提到、争夺、隐藏、封印、赠予、认主、损坏、激活的物品。
   - 具有特殊能力、来源、等级、禁忌、传承、诅咒、钥匙作用的物品。
   - 能推动剧情或揭示秘密的信物、法器、书信、地图、令牌、药物、武器、容器等。
4. 不要提取：
   - 配角使用的普通物品，例如“茶杯”“木棍”“马车”“斗笠”“包袱”。
   - 只用于环境描写的物品，例如“桌椅”“灯笼”“窗帘”。
   - 普通战斗中随手出现的武器，例如“刀”“剑”“弓箭”，除非它有专名、特殊能力或被剧情重点强调。
   - 普通衣物、饰品、食物、钱币，除非它承担身份、线索、能力或伏笔作用。
   - 只出现一次且没有明显剧情意义的物品。
5. 每个道具必须有稳定名称；没有正式名字时，用具体称呼，如“朱红棺材”“青铜铃铛”“裂纹玉佩”，不要用“道具1”。
6. visual_description 只描述道具本体的外观，包括形状、尺寸、材质、颜色、纹理、破损/血迹/符文/光泽等标志性细节；不要包含构图、背景、角色动作。
7. 如果小说没有明确描述部分细节，请根据题材、时代背景和剧情作用合理推断，但不要改变道具核心功能。

请严格按照以下JSON格式输出，不要输出其他内容：
```json
{{
    "props": [
        {{
            "name": "道具名",
            "prop_type": "weapon/token/container/document/tool/ritual/vehicle_part/other",
            "brief_description": "极短道具标签，如：裂纹玉佩，青白玉质 / 朱红棺材，暗金符纹",
            "visual_description": "道具纯外观描述，不要包含构图、背景、角色动作",
            "function": "剧情功能或用途",
            "first_appearance": "首次出现的情节位置或简述"
        }}
    ]
}}
```

小说内容：
{novel_text}
"""


PROMPT_UPDATE_PROPS_FOR_CHAPTER = """你是一个连续剧道具资产统筹。请阅读新的小说章节，并参考截至当前章节前已经建立的全局道具资产，输出本章节要使用的关键道具清单。

目标：
1. 只输出核心道具。核心道具是本章节中具有明显剧情意义、异常性、身份象征、能力属性、线索价值或后续伏笔的具体物品。
2. 如果本章节道具与全局已有道具是同一个视觉资产，必须复用全局道具 id，不要新建 id。
3. 判断每个本章节道具的视觉资产动作：
   - "reuse": 外观、状态、材质、标志性细节没有明显变化，直接复用已有道具图
   - "update": 同一道具但需要新图，例如破损、沾血、烧焦、开启/关闭、符文发光、形态变化、关键内容显露等；要写清楚更新原因
   - "new": 全局资产里没有的新增道具
4. 如果是 update，visual_description 必须保留同一道具的核心形状、材质、颜色、纹理和标志性细节，同时写入本章节的新状态。
5. 如果是 reuse，visual_description 尽量沿用已有资产，避免漂移。
6. 新增道具 id 从已有最大 id 后继续递增。
7. 核心道具必须同时满足：
   - 是具体物品，不是人物、地点、组织、抽象概念、能力名称或自然现象。
   - 在本章节中出现 2 次及以上，或虽然出现次数不多但被明显强调为关键物。
   - 不是普通背景物、生活用品、装饰物、交通工具、食物、普通武器、普通衣物、普通工具。
   - 不是配角临时使用、随手持有、一次性动作相关的物品。
   - 对主角、主要冲突、任务目标、秘密线索、身份识别、能力机制、战斗胜负或后续剧情有明显影响。
8. 优先提取：
   - 有专名的物品，例如“玄铁令”“噬魂珠”“无字天书”。
   - 被反复提到、争夺、隐藏、封印、赠予、认主、损坏、激活的物品。
   - 具有特殊能力、来源、等级、禁忌、传承、诅咒、钥匙作用的物品。
   - 能推动剧情或揭示秘密的信物、法器、书信、地图、令牌、药物、武器、容器等。
9. 不要提取：
   - 配角使用的普通物品，例如“茶杯”“木棍”“马车”“斗笠”“包袱”。
   - 只用于环境描写的物品，例如“桌椅”“灯笼”“窗帘”。
   - 普通战斗中随手出现的武器，例如“刀”“剑”“弓箭”，除非它有专名、特殊能力或被剧情重点强调。
   - 普通衣物、饰品、食物、钱币，除非它承担身份、线索、能力或伏笔作用。
   - 只出现一次且没有明显剧情意义的物品。

全局道具资产：
{previous_props_json}

本章节小说内容：
{novel_text}

请严格按照以下JSON格式输出，不要输出其他内容：
```json
{{
    "props": [
        {{
            "id": 1,
            "name": "道具名",
            "prop_type": "weapon/token/container/document/tool/ritual/vehicle_part/other",
            "brief_description": "极短道具标签",
            "visual_description": "道具纯外观描述，不要包含构图、背景、角色动作",
            "function": "剧情功能或用途",
            "first_appearance": "首次出现的情节位置或简述",
            "asset_action": "reuse/update/new",
            "asset_reason": "为什么复用、更新或新增",
            "previous_name": "如果复用或更新，填全局资产里对应道具名；新增道具填空字符串"
        }}
    ]
}}
```
"""


class PropExtractor:
    """提取章节关键道具资产。"""

    def __init__(self, output_dir="output", model="gemini-3.1-pro-preview"):
        self.llm = LLMClient(model=model)
        self.model = model
        self.output_dir = output_dir
        self.save_path = os.path.join(output_dir, "props.json")

    def run(self, novel_file_path):
        print("\n[道具] 提取关键道具信息...")
        with open(novel_file_path, "r", encoding="utf-8") as f:
            novel_text = f.read()
        prompt = PROMPT_EXTRACT_PROPS.format(novel_text=novel_text)
        response = self.llm.generate(prompt)
        result = self._parse_json(response)
        props = result.get("props", [])
        for i, prop in enumerate(props):
            prop["id"] = i + 1
            prop.setdefault("asset_action", "new")
            prop.setdefault("asset_reason", "首章新增道具")
            prop.setdefault("previous_name", "")

        print(f"  共提取 {len(props)} 个关键道具:")
        for prop in props:
            print(f"    - #{prop['id']} {prop.get('name', '')}: {prop.get('function', '')}")
        data = {"props": props}
        self.save(data)
        return data

    def run_with_previous(self, novel_file_path, previous_output_dir=None, previous_data=None):
        print("\n[道具] 提取并对齐本章节关键道具信息...")
        with open(novel_file_path, "r", encoding="utf-8") as f:
            novel_text = f.read()
        previous_data = previous_data or self._load_previous_props(previous_output_dir)
        prompt = PROMPT_UPDATE_PROPS_FOR_CHAPTER.format(
            previous_props_json=json.dumps(previous_data, ensure_ascii=False, indent=2),
            novel_text=novel_text,
        )
        response = self.llm.generate(prompt)
        result = self._parse_json(response)
        props = result.get("props", [])

        max_previous_id = max((p.get("id", 0) for p in previous_data.get("props", [])), default=0)
        next_id = max_previous_id + 1
        used_ids = set()
        for prop in props:
            action = prop.get("asset_action", "new")
            if action in {"reuse", "update"}:
                prop_id = self._find_previous_prop_id(prop, previous_data.get("props", []))
                if prop_id is None:
                    prop_id = next_id
                    next_id += 1
                    prop["asset_action"] = "new"
            else:
                prop_id = prop.get("id")
                if not isinstance(prop_id, int) or prop_id in used_ids or prop_id <= max_previous_id:
                    prop_id = next_id
                    next_id += 1
                prop["asset_action"] = "new"
            prop["id"] = prop_id
            used_ids.add(prop_id)
            prop.setdefault("asset_reason", "")
            prop.setdefault("previous_name", prop.get("name", "") if prop.get("asset_action") in {"reuse", "update"} else "")

        print(f"  本章节共 {len(props)} 个关键道具:")
        for prop in props:
            print(f"    - #{prop['id']} {prop.get('name', '')}: {prop.get('asset_action', 'new')} {prop.get('asset_reason', '')}")
        data = {"props": props}
        self.save(data)
        return data

    def save(self, data):
        os.makedirs(self.output_dir, exist_ok=True)
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  道具信息已保存: {self.save_path}")

    def load(self):
        with open(self.save_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {"props": data}
        return data if isinstance(data, dict) else {"props": []}

    def _load_previous_props(self, previous_output_dir):
        previous_asset_dir = resolve_previous_asset_dir(previous_output_dir, "props.json")
        if not previous_asset_dir:
            return {"props": []}
        path = os.path.join(previous_asset_dir, "props.json")
        if not os.path.exists(path):
            return {"props": []}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {"props": data}
        return data if isinstance(data, dict) else {"props": []}

    def _find_previous_prop_id(self, prop, previous_props):
        previous_name = prop.get("previous_name") or prop.get("name")
        for previous in previous_props:
            if previous.get("name") == previous_name:
                return previous.get("id")
        for previous in previous_props:
            if previous.get("name") == prop.get("name"):
                return previous.get("id")
        return prop.get("id") if isinstance(prop.get("id"), int) else None

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
        print(f"警告：无法解析道具JSON，原始内容:\n{response[:500]}")
        return {}


if __name__ == "__main__":
    import argparse
    from core.global_asset_index import GlobalAssetIndex
    from core.project_paths import resolve_project_path

    parser = argparse.ArgumentParser(description="步骤2：提取章节关键道具信息")
    parser.add_argument("--story-file", default="story.txt", help="小说章节文本路径")
    parser.add_argument("--output-dir", default="output", help="当前章节输出目录")
    parser.add_argument("--chapter-name", default="chapter_01", help="章节文件夹名；留空则直接使用 output-dir")
    parser.add_argument("--model", default="gemini-3.1-pro-preview", help="LLM 模型")
    parser.add_argument("--not-first-chapter", action="store_true", help="标记当前章节不是第一章节")
    parser.add_argument("--global-output-dir", default="", help="全局资产索引目录；默认使用 --output-dir")
    args = parser.parse_args()

    output_dir = resolve_project_path(args.output_dir)
    story_file = resolve_project_path(args.story_file)
    global_output_dir = resolve_project_path(args.global_output_dir) if args.global_output_dir else output_dir
    current_output_dir = resolve_chapter_output_dir(output_dir, args.chapter_name)
    extractor = PropExtractor(output_dir=current_output_dir, model=args.model)
    global_assets = GlobalAssetIndex(global_output_dir)
    if args.not_first_chapter:
        data = extractor.run_with_previous(
            story_file,
            previous_data=global_assets.load_props(),
        )
    else:
        data = extractor.run(story_file)
    global_assets.save_props_from_chapter(data, args.chapter_name)
