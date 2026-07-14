import json
import os
import re

from core.project_paths import resolve_chapter_output_dir, resolve_previous_asset_dir
from provider.llm_provider import LLMClient


PROMPT_EXTRACT_CHARACTERS = """你是一个专业的影视编剧助手。请仔细阅读以下小说章节内容，提取所有需要建立视觉资产的出场角色，并为每个角色生成详细的外貌形象描述。

要求：
1. 角色不只限于人类。除人类角色外，多次出现、被命名、对剧情有重要作用、或需要在后续分镜中复用视觉形象的怪物、妖兽、灵兽、鬼怪、傀儡等非人类实体也必须提取为角色资产。
2. 不要把一次性背景群体、无独立视觉身份的杂兵、纯环境物体提取为角色；但如果某个非人类实体反复出现或有明确外貌特征，就要提取。
3. 列出每个角色/实体的名字；没有正式名字时，用稳定且具体的称呼，如“黑鳞妖兽”“独眼怪物”，不要用泛称“怪物1”。
4. 为每个角色撰写详细的“标准定妆照”外貌描述。人类包括：性别、年龄、身高体型、发型发色、五官特征、肤色、长期稳定的标志性特征、自然表情气质；非人类包括：物种/类型、体型尺寸、轮廓、皮毛/鳞甲/皮肤/甲壳质感、头部和五官、角/爪/尾/翅等肢体特征、颜色、长期稳定的标志性特征。
5. appearance字段只描述角色标准定妆照中的纯外貌特征，不要包含构图、布局、背景、服装、动作、剧情瞬间状态。人类必须明确指出人种（亚洲人/白人/黑人）和性别（男性/女性/男孩/女孩），并保持表情自然；非人类必须明确指出物种/类型和可见性别特征（若无法判断，写“性别特征不明显”），不要硬套人种。
6. clothing字段只描述服装或外部装备；非人类没有服装时，写“无服装”，不要把鳞片、毛发、甲壳等身体特征写入 clothing。
7. 如果小说中没有明确描述某些特征，请根据角色性格、物种设定和情节合理推断。
8. 本任务用于生成角色“标准定妆照/角色资产图”，不是剧情瞬间截图。角色形象应表现为常态、干净、自然、可复用的基础造型。
9. 所有角色默认表情自然、平静或符合性格的轻微神态，不要生成痛苦、惊恐、受伤、战斗中、濒死、流血、狼狈等剧情瞬间状态。
10. appearance字段只描述角色长期稳定、可复用的外貌特征。不要写入以下临时或剧情瞬间特征：
   - 近期伤口、血迹、淤青、烧伤、破皮、手术痕迹
   - 刚愈合的新生疤痕、粉色疤痕、药剂作用痕迹
   - 战斗造成的破损、污渍、狼狈状态
   - 某一章节临时姿势、表情、情绪、动作
   - 会暴露身体隐私部位或需要特殊裸露才能看见的细节
11. 只有当疤痕、残疾、纹身、异色眼、义肢等是角色长期稳定且具有辨识度的设定时，才可以写入 appearance。
12. 如果同一角色在本章节前后出现明显换装、身份装束变化、制服/便服切换、伪装造型、战甲/礼服/囚服等不同可复用造型，必须把换装前后的造型分别保存为不同角色资产。name 要用稳定名称区分造型，例如“秦羽（常服）”“秦羽（战甲）”“秦羽（伪装后）”；appearance 保持同一角色的核心外貌一致，clothing 分别写对应造型。
13. 人类角色的年龄变化只按四个视觉年龄阶段判断：幼年、少年、中年、老年。同一角色从 6 岁到 8 岁这类仍处于同一年龄阶段的变化，不要拆成两个独立角色资产；只有跨越上述年龄阶段时，才需要作为新的成长阶段角色资产。

请严格按照以下JSON格式输出，不要输出其他内容：
```json
{{
    "characters": [
        {{
            "name": "角色名",
            "entity_type": "human/monster/beast/spirit/other",
            "gender": "性别",
            "age": "年龄（具体的年龄数字或一个预估的数字年龄段）",
            "brief_description": "极短的角色标签，如：年轻女人，白衣长裙 / 中年男人，黑色西装 / 黑鳞妖兽，巨角利爪",
            "appearance": "角色标准定妆照的纯外貌描述。人类必须包含人种和性别，表情自然；非人类必须包含物种/类型和性别特征判断；只写长期稳定、可复用的外貌特征，不写近期伤口、血迹、污渍、狼狈状态、临时姿势、表情、情绪、动作、服装、构图、布局或背景信息",
            "clothing": "常见着装或外部装备描述；非人类无服装时写无服装",
            "personality_traits": "性格特征简述"
        }}
    ]
}}
```

小说内容：
{novel_text}
"""


PROMPT_UPDATE_CHARACTERS_FOR_CHAPTER = """你是一个连续剧角色资产统筹。请阅读新的小说章节，并参考截至当前章节前已经建立的全局角色资产，输出本章节要使用的角色清单。

目标：
1. 角色不只限于人类。多次出现、被命名、对剧情有重要作用、或需要在后续分镜中复用视觉形象的怪物、妖兽、灵兽、鬼怪、傀儡等非人类实体，也必须作为角色资产输出。
2. 如果本章节角色/实体与全局已有角色是同一个视觉身份且标准造型/服装没有明显变化，必须复用全局角色 id，不要新建 id。非人类实体也要按同一规则复用，例如同一只妖兽、同一个鬼怪、同一具傀儡。
3. 判断每个本章节出场角色的视觉资产动作：
   - "reuse": 标准定妆照外貌、年龄段/成长阶段、常见服装或长期稳定身体设定没有明显变化，直接复用已有角色图
   - "update": 同一角色同一造型但需要新图，例如长期稳定且在标准定妆照中一眼可见的面部疤痕、残疾、义肢、明显纹身、异色眼等；非人类也包括长期稳定的蜕变、变身、断角、增生、形态强化等；要写清楚更新原因
   - "new": 全局资产里没有的新增角色，或同一角色在本章节出现了新的可复用服装/身份造型，或同一人类角色跨越了幼年/少年/中年/老年四个视觉年龄阶段而需要新的成长阶段人物 id
4. 如果是 update，appearance 保持同一角色/实体的核心身份特征；人类保持核心五官、体型、发型等，非人类保持物种轮廓、角/爪/尾/翅、纹理、颜色和标志性特征，只写入本章节已经变成长期稳定设定的新年龄阶段或外貌变化。临时受伤、血迹、狼狈、战斗状态不作为 update 理由，也不要写入 appearance。
5. 如果全局资产里已经存在同一角色身份，绝对不要因为新揭示的外貌细节输出 asset_action="new"；同一身份只有换装/新身份造型或跨视觉年龄阶段才允许 new。若确实需要改同一角色同一造型，必须用 update。
6. 局部肢体细节或动作中才看见的细节，例如手指特别长、指节修长、手掌粗糙、指甲、手部小疤、短暂露出的皮肤纹理等，不足以更新标准角色资产；这类信息不要写入 appearance，必须 reuse 已有角色。
7. 如果是 reuse，appearance 和 clothing 尽量沿用已有资产，避免漂移。
8. 新增角色 id 从已有最大 id 后继续递增。
9. 不要判断或输出整体画面风格，画面风格由调用方人工传入。
10. 不要把一次性背景群体、无独立视觉身份的杂兵、纯环境物体提取为角色；但如果某个非人类实体反复出现或有明确外貌特征，就要提取。
11. 本任务用于生成角色“标准定妆照/角色资产图”，不是剧情瞬间截图。角色形象应表现为常态、干净、自然、可复用的基础造型。
12. 所有角色默认表情自然、平静或符合性格的轻微神态，不要生成痛苦、惊恐、受伤、战斗中、濒死、流血、狼狈等剧情瞬间状态。
13. 为每个角色撰写详细的“标准定妆照”外貌描述。人类包括：性别、年龄、身高体型、发型发色、五官特征、肤色、长期稳定的标志性特征、自然表情气质；非人类包括：物种/类型、体型尺寸、轮廓、皮毛/鳞甲/皮肤/甲壳质感、头部和五官、角/爪/尾/翅等肢体特征、颜色、长期稳定的标志性特征。
14. appearance字段只描述角色标准定妆照中的纯外貌特征，不要包含构图、布局、背景、服装、动作、剧情瞬间状态。人类必须明确指出人种（亚洲人/白人/黑人）和性别（男性/女性/男孩/女孩），并保持表情自然；非人类必须明确指出物种/类型和可见性别特征（若无法判断，写“性别特征不明显”），不要硬套人种。
15. appearance字段只描述角色长期稳定、可复用的外貌特征。不要写入以下临时或剧情瞬间特征：
   - 近期伤口、血迹、淤青、烧伤、破皮、手术痕迹
   - 刚愈合的新生疤痕、粉色疤痕、药剂作用痕迹
   - 战斗造成的破损、污渍、狼狈状态
   - 某一章节临时姿势、表情、情绪、动作
   - 会暴露身体隐私部位或需要特殊裸露才能看见的细节
16. 只有当疤痕、残疾、纹身、异色眼、义肢等是角色长期稳定、具有辨识度、且会明显改变标准定妆照观感的设定时，才可以写入 appearance。
17. 如果同一角色在本章节前后出现明显换装、身份装束变化、制服/便服切换、伪装造型、战甲/礼服/囚服等不同可复用造型，必须把换装前后的造型分别保存为不同角色资产：
   - 已有造型继续 reuse 对应全局角色 id。
   - 新造型必须 asset_action="new"，分配新 id，不要用 update 覆盖旧造型。
   - name 要用稳定名称区分造型，例如“秦羽（常服）”“秦羽（战甲）”“秦羽（伪装后）”。
   - appearance 保持同一角色的核心外貌一致，clothing 分别写对应造型。
   - previous_name 对新造型填空字符串；asset_reason 写明“同一角色新增换装造型，需要独立角色资产”。
18. 人类角色的成长/年龄变化只按四个视觉年龄阶段判断：幼年、少年、中年、老年。同一角色只要仍在同一年龄阶段，例如从 6 岁到 8 岁、8 岁到 10 岁，不要 new 或 update，不要生成新人物 id，必须 reuse 原 id；只有跨越上述年龄阶段时，才允许因成长阶段变化生成新的角色资产和新的人物 id。

全局角色资产：
{previous_characters_json}

本章节小说内容：
{novel_text}

请严格按照以下JSON格式输出，不要输出其他内容：
```json
{{
    "characters": [
        {{
            "id": 1,
            "name": "角色名",
            "entity_type": "human/monster/beast/spirit/other",
            "gender": "性别",
            "age": "年龄",
            "brief_description": "极短角色标签",
            "appearance": "角色标准定妆照的纯外貌描述。人类必须包含人种和性别，表情自然；非人类必须包含物种/类型和性别特征判断；只写长期稳定、可复用的外貌特征，不写近期伤口、血迹、污渍、狼狈状态、临时姿势、表情、情绪、动作、服装、构图、布局或背景信息",
            "clothing": "本章节服装或外部装备描述；非人类无服装时写无服装",
            "personality_traits": "性格特征简述",
            "asset_action": "reuse/update/new",
            "asset_reason": "为什么复用、更新或新增",
            "previous_name": "如果复用或更新，填全局资产里对应角色名；新增角色填空字符串"
        }}
    ]
}}
```
"""


PROMPT_AUDIT_CHARACTER_COSTUME_VARIANTS = """你是一个严谨的连续剧角色资产审计员。请只检查“同一角色在同一章节中是否因为明显换装/身份装束变化而漏拆为多个角色资产”。

背景：
- 角色资产用于生成标准定妆照，不是剧情瞬间截图。
- 同一角色如果在本章节中出现两个或更多可复用造型，例如常服/制服、便服/战甲、伪装前/伪装后、礼服/囚服、门派服/夜行衣等，必须在 characters 中拥有两个不同角色 id。
- 只要是短暂沾灰、受伤、流血、披散头发、表情变化、临时动作、临时手持道具，不算换装，不要新增资产。
- 同一人类角色仍处于同一视觉年龄阶段（幼年、少年、中年、老年）时，不因年龄细微变化新增资产；跨阶段才需要新成长阶段资产。

审计任务：
1. 阅读本章节小说内容、当前章节角色 JSON，以及全局角色资产 JSON。
2. 如果当前章节已经为每个可复用换装造型分别保留了角色资产，不要改动。
3. 如果发现本章节遗漏了某个换装造型，必须补充为独立角色资产。
4. 补充的新造型如果全局角色资产中已经存在同一造型，则复用该全局 id，asset_action="reuse"，previous_name 填全局对应角色名。
5. 补充的新造型如果全局角色资产中不存在，则新增角色资产，asset_action="new"，id 可先填 null 或临时数字，调用方会统一分配最终 id；previous_name 填空字符串；asset_reason 写明“同一角色新增换装造型，需要独立角色资产”。
6. 不要删除当前已有角色，除非它明显是把两个造型错误合并后的重复错误项；如不确定，不要删除。
7. 对新造型：appearance 保持同一角色核心外貌一致；clothing 写该造型的服装/外部装备。不要把剧情瞬间伤口、血迹、狼狈状态写入 appearance。
8. 只输出完整修正后的角色 JSON，不要输出解释。

本章节小说内容：
{novel_text}

当前章节角色 JSON：
{current_characters_json}

全局角色资产 JSON：
{previous_characters_json}

请严格按照以下JSON格式输出，不要输出其他内容：
```json
{{
    "characters": [
        {{
            "id": 1,
            "name": "角色名或角色名（造型）",
            "entity_type": "human/monster/beast/spirit/other",
            "gender": "性别",
            "age": "年龄",
            "brief_description": "极短角色标签",
            "appearance": "角色标准定妆照的纯外貌描述",
            "clothing": "该造型服装或外部装备描述",
            "personality_traits": "性格特征简述",
            "asset_action": "reuse/update/new",
            "asset_reason": "为什么复用、更新或新增",
            "previous_name": "如果复用或更新，填全局资产里对应角色名；新增角色填空字符串"
        }}
    ]
}}
```
"""


class CharacterExtractor:
    """步骤1：从小说中提取角色信息"""

    def __init__(self, output_dir="output", model="gemini-3.1-pro-preview"):
        self.llm = LLMClient()
        self.model = model
        self.output_dir = output_dir
        self.save_path = os.path.join(output_dir, "characters.json")

    def run(self, novel_file_path, style="写实"):
        print("\n[步骤1] 提取角色信息...")
        with open(novel_file_path, "r", encoding="utf-8") as f:
            novel_text = f.read()
        print(f"  读取完成，共 {len(novel_text)} 字")

        prompt = PROMPT_EXTRACT_CHARACTERS.format(novel_text=novel_text)
        response = self.llm.generate(prompt)
        result = self._parse_json(response)
        style = self._normalize_style(style)
        characters = result.get("characters", [])

        for i, char in enumerate(characters):
            char["id"] = i + 1
            char.setdefault("asset_action", "new")
            char.setdefault("asset_reason", "首章新增角色资产")
            char.setdefault("previous_name", "")

        characters = self._audit_and_fix_costume_variants(novel_text, characters, {"style": style, "characters": []})
        characters = self._assign_first_chapter_ids(characters)
        characters = self._link_first_chapter_transformation_variants(characters)

        print(f"  画面风格: {style}")
        print(f"  共提取 {len(characters)} 个角色:")
        for char in characters:
            print(f"    - {char['name']}: {char.get('personality_traits', '')}")

        data = {"style": style, "characters": characters}
        self.save(data)
        return data

    def run_with_previous(self, novel_file_path, previous_output_dir, previous_data=None, style="写实"):
        """后续章节角色抽取：对齐已有全局角色，并标注复用/更新/新增。"""
        print("\n[步骤1] 提取并对齐本章节角色信息...")
        with open(novel_file_path, "r", encoding="utf-8") as f:
            novel_text = f.read()
        print(f"  读取完成，共 {len(novel_text)} 字")

        previous_data = previous_data or self._load_previous_characters(previous_output_dir)
        prompt = PROMPT_UPDATE_CHARACTERS_FOR_CHAPTER.format(
            previous_characters_json=json.dumps(previous_data, ensure_ascii=False, indent=2),
            novel_text=novel_text,
        )
        response = self.llm.generate(prompt)
        result = self._parse_json(response)
        style = self._normalize_style(style)
        characters = result.get("characters", [])

        characters = self._normalize_chapter_character_ids(characters, previous_data)
        characters = self._audit_and_fix_costume_variants(novel_text, characters, previous_data)
        characters = self._normalize_chapter_character_ids(characters, previous_data)

        print(f"  画面风格: {style}")
        print(f"  本章节共 {len(characters)} 个角色:")
        for char in characters:
            print(f"    - #{char['id']} {char['name']}: {char.get('asset_action', 'new')} {char.get('asset_reason', '')}")

        data = {"style": style, "characters": characters}
        self.save(data)
        return data

    def _assign_first_chapter_ids(self, characters):
        next_id = 1
        used_ids = set()
        for char in characters:
            char_id = char.get("id")
            if not isinstance(char_id, int) or char_id in used_ids or char_id <= 0:
                char_id = next_id
            while char_id in used_ids or char_id <= 0:
                char_id += 1
            char["id"] = char_id
            used_ids.add(char_id)
            next_id = max(next_id, char_id + 1)
            char.setdefault("asset_action", "new")
            char.setdefault("asset_reason", "首章新增角色资产")
            char.setdefault("previous_name", "")
        return characters

    def _link_first_chapter_transformation_variants(self, characters):
        """首章中的变身形态应参考同章常态资产，而不是作为无参考的新角色生成。"""
        transformation_markers = (
            "变身", "变异", "异化", "半人", "半蛇", "兽化", "妖化", "魔化",
            "怪物形态", "战斗形态", "强化形态", "第二形态", "最终形态",
        )
        base_by_name = {}
        for char in characters:
            name = str(char.get("name") or "").strip()
            base_name = re.sub(r"[（(][^）)]*[）)]\s*$", "", name).strip()
            variant_text = " ".join((
                name,
                str(char.get("brief_description") or ""),
                str(char.get("appearance") or ""),
            ))
            base_char = base_by_name.get(base_name)
            if base_char and any(marker in variant_text for marker in transformation_markers):
                char["asset_action"] = "update"
                char["asset_reason"] = f"同一角色的新形态，基于{base_char.get('name')}角色图进行图生图"
                char["previous_name"] = base_char.get("name", "")
            elif base_name:
                base_by_name.setdefault(base_name, char)
        return characters

    def _normalize_chapter_character_ids(self, characters, previous_data):
        max_previous_id = max((c.get("id", 0) for c in previous_data.get("characters", [])), default=0)
        next_id = max_previous_id + 1
        used_ids = set()
        for char in characters:
            action = char.get("asset_action", "new")
            previous_char = self._find_previous_character(char, previous_data.get("characters", []))
            if previous_char and action in {"new", "update"} and self._looks_like_minor_local_body_detail(char):
                action = "reuse"
                char["asset_action"] = "reuse"
                char["asset_reason"] = "局部肢体细节不足以更新标准角色资产，复用已有角色资产"
                char["previous_name"] = previous_char.get("name", "")
                self._copy_previous_visual_fields(char, previous_char)
            elif previous_char and action == "new" and not self._looks_like_new_costume_asset(char) and not self._is_cross_human_age_stage(char, previous_char):
                action = "update"
                char["asset_action"] = "update"
                char["previous_name"] = previous_char.get("name", "")
            if action == "update" and self._looks_like_new_costume_asset(char):
                action = "new"
                char["asset_action"] = "new"
                char.setdefault("asset_reason", "同一角色新增换装造型，需要独立角色资产")
                char["previous_name"] = ""
            elif action == "update" and self._is_cross_human_age_stage(char, previous_char):
                action = "new"
                char["asset_action"] = "new"
                char["asset_reason"] = "同一角色跨越视觉年龄阶段，需要生成新的成长阶段人物 id"
                char["previous_name"] = previous_char.get("name", "")
            elif action in {"update", "new"} and self._should_reuse_same_age_stage(char, previous_char):
                action = "reuse"
                char["asset_action"] = "reuse"
                char["asset_reason"] = "同一角色仍处于同一视觉年龄阶段，复用已有角色资产"
                char["previous_name"] = previous_char.get("name", "")
            if action in {"reuse", "update"}:
                char_id = self._find_previous_character_id(char, previous_data.get("characters", []))
                if char_id is None:
                    char_id = next_id
                    next_id += 1
                    char["asset_action"] = "new"
            else:
                char_id = char.get("id")
                if not isinstance(char_id, int) or char_id in used_ids or char_id <= max_previous_id:
                    char_id = next_id
                    next_id += 1
                char["asset_action"] = "new"
            char["id"] = char_id
            used_ids.add(char_id)
            char.setdefault("asset_reason", "")
            char.setdefault("previous_name", char.get("name", "") if char.get("asset_action") in {"reuse", "update"} else "")
        return characters

    def _audit_and_fix_costume_variants(self, novel_text, characters, previous_data=None):
        previous_data = previous_data or {"style": "写实", "characters": []}
        if not characters:
            return characters

        print("  调用LLM检查同章换装造型是否漏拆角色 id...")
        prompt = PROMPT_AUDIT_CHARACTER_COSTUME_VARIANTS.format(
            novel_text=novel_text,
            current_characters_json=json.dumps({"characters": characters}, ensure_ascii=False, indent=2),
            previous_characters_json=json.dumps(previous_data, ensure_ascii=False, indent=2),
        )
        response = self.llm.generate(prompt)
        result = self._parse_json(response)
        audited = result.get("characters", []) if isinstance(result, dict) else []
        if not audited:
            print("  换装审计未返回有效角色 JSON，保留初始结果")
            return characters

        before = self._character_variant_signature_set(characters)
        after = self._character_variant_signature_set(audited)
        added_count = max(0, len(after - before))
        if added_count:
            print(f"  换装审计补充 {added_count} 个疑似遗漏造型")
        else:
            print("  换装审计未发现遗漏造型")
        return audited

    def save(self, data):
        os.makedirs(self.output_dir, exist_ok=True)
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  角色信息已保存: {self.save_path}")

    def load(self):
        with open(self.save_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 兼容旧格式（纯列表）
        if isinstance(data, list):
            data = {"style": "写实", "characters": data}
        characters = data.get("characters", [])
        before = json.dumps(characters, ensure_ascii=False, sort_keys=True)
        data["characters"] = self._link_first_chapter_transformation_variants(characters)
        if json.dumps(data["characters"], ensure_ascii=False, sort_keys=True) != before:
            self.save(data)
        return data

    def _load_previous_characters(self, previous_output_dir):
        previous_asset_dir = resolve_previous_asset_dir(previous_output_dir, "characters.json")
        if not previous_asset_dir:
            return {"style": "写实", "characters": []}
        path = os.path.join(previous_asset_dir, "characters.json")
        if not os.path.exists(path):
            return {"style": "写实", "characters": []}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {"style": "写实", "characters": data}
        return data if isinstance(data, dict) else {"style": "写实", "characters": []}

    def _normalize_style(self, style):
        style = str(style or "").strip()
        return style or "写实"

    def _find_previous_character_id(self, char, previous_characters):
        previous = self._find_previous_character(char, previous_characters)
        if previous:
            return previous.get("id")
        return char.get("id") if isinstance(char.get("id"), int) else None

    def _find_previous_character(self, char, previous_characters):
        previous_name = char.get("previous_name") or char.get("name")
        for previous in previous_characters:
            if previous.get("name") == previous_name:
                return previous
        for previous in previous_characters:
            if previous.get("name") == char.get("name"):
                return previous
        return None

    def _character_variant_signature_set(self, characters):
        signatures = set()
        for char in characters or []:
            if not isinstance(char, dict):
                continue
            name = re.sub(r"\s+", "", str(char.get("name", "")))
            clothing = re.sub(r"\s+", "", str(char.get("clothing", "")))[:80]
            signatures.add((name, clothing))
        return signatures

    def _looks_like_new_costume_asset(self, char):
        text = " ".join(
            str(char.get(key, ""))
            for key in ("name", "clothing", "asset_reason", "brief_description")
        )
        costume_keywords = (
            "换装", "新造型", "造型", "服装变化", "身份装束", "制服", "便服",
            "常服", "战甲", "礼服", "囚服", "伪装", "女装", "男装", "盔甲",
            "铠甲", "斗篷", "婚服", "官服", "校服", "病号服",
        )
        return any(keyword in text for keyword in costume_keywords)

    def _looks_like_minor_local_body_detail(self, char):
        text = " ".join(
            str(char.get(key, ""))
            for key in ("name", "brief_description", "appearance", "asset_reason")
        )
        local_body_keywords = (
            "手指", "中指", "食指", "指节", "手掌", "手部", "指甲", "双指",
            "局部", "细节", "局部肢体",
        )
        significant_keywords = (
            "断臂", "断手", "义肢", "残疾", "明显畸形", "变异", "兽化", "异化",
            "全身", "脸部", "面部", "毁容", "异色眼", "纹身", "大面积",
        )
        return any(keyword in text for keyword in local_body_keywords) and not any(
            keyword in text for keyword in significant_keywords
        )

    def _copy_previous_visual_fields(self, char, previous_char):
        for key in ("brief_description", "appearance", "clothing"):
            previous_value = previous_char.get(key)
            if previous_value:
                char[key] = previous_value

    def _should_reuse_same_age_stage(self, char, previous_char):
        if not previous_char:
            return False
        if self._looks_like_new_costume_asset(char):
            return False
        if not self._is_human_character(char):
            return False
        text = " ".join(
            str(char.get(key, ""))
            for key in ("age", "brief_description", "asset_reason")
        )
        reuse_markers = (
            "无明显变化", "没有明显变化", "复用", "同一视觉年龄阶段", "仍处于同一年龄阶段",
            "年龄细微变化", "年龄变化不明显",
        )
        age_markers = ("年龄", "年纪", "岁", "成长", "年龄阶段")
        significant_update_markers = (
            "疤痕", "残疾", "义肢", "纹身", "异色眼", "毁容", "断臂", "断手",
            "变身", "变异", "异化", "形态强化",
        )
        if any(keyword in text for keyword in significant_update_markers):
            return False
        if not any(keyword in text for keyword in reuse_markers + age_markers):
            return False
        current_stage = self._human_age_stage(char.get("age", ""))
        previous_stage = self._human_age_stage(previous_char.get("age", ""))
        return bool(current_stage and current_stage == previous_stage)

    def _is_cross_human_age_stage(self, char, previous_char):
        if not previous_char or not self._is_human_character(char):
            return False
        current_stage = self._human_age_stage(char.get("age", ""))
        previous_stage = self._human_age_stage(previous_char.get("age", ""))
        return bool(current_stage and previous_stage and current_stage != previous_stage)

    def _is_human_character(self, char):
        entity_type = str(char.get("entity_type", "")).lower()
        return entity_type in {"human", "人类", ""}

    def _human_age_stage(self, age_text):
        text = str(age_text or "").strip()
        if not text:
            return ""
        if any(keyword in text for keyword in ("幼年", "幼儿", "孩童", "儿童", "小孩", "男孩", "女孩")):
            return "幼年"
        if any(keyword in text for keyword in ("少年", "少女", "青少年")):
            return "少年"
        if any(keyword in text for keyword in ("中年", "成年", "青年")):
            return "中年"
        if any(keyword in text for keyword in ("老年", "老人", "老者", "花甲", "古稀")):
            return "老年"

        ages = [int(value) for value in re.findall(r"\d+", text)]
        if not ages:
            return ""
        age = sum(ages[:2]) / min(len(ages), 2)
        if age <= 12:
            return "幼年"
        if age <= 25:
            return "少年"
        if age < 60:
            return "中年"
        return "老年"

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
        print(f"警告：无法解析JSON，原始内容:\n{response[:500]}")
        return {}


if __name__ == "__main__":
    import argparse
    from core.global_asset_index import GlobalAssetIndex
    from core.project_paths import resolve_project_path

    parser = argparse.ArgumentParser(description="步骤1：提取章节角色信息")
    parser.add_argument("--story-file", default="story.txt", help="小说章节文本路径")
    parser.add_argument("--output-dir", default="output", help="当前章节输出目录")
    parser.add_argument("--chapter-name", default="chapter_01", help="章节文件夹名；留空则直接使用 output-dir")
    parser.add_argument("--model", default="gemini-3.1-pro-preview", help="LLM 模型")
    parser.add_argument("--style", default="盗墓题材写实奇幻动漫", help="人工指定的整体画面风格")
    parser.add_argument("--not-first-chapter", action="store_true", help="标记当前章节不是第一章节")
    parser.add_argument("--global-output-dir", default="", help="全局资产索引目录；默认使用 --output-dir")
    args = parser.parse_args()

    output_dir = resolve_project_path(args.output_dir)
    story_file = resolve_project_path(args.story_file)
    global_output_dir = resolve_project_path(args.global_output_dir) if args.global_output_dir else output_dir
    current_output_dir = resolve_chapter_output_dir(output_dir, args.chapter_name)
    extractor = CharacterExtractor(output_dir=current_output_dir, model=args.model)
    global_assets = GlobalAssetIndex(global_output_dir)
    if args.not_first_chapter:
        data = extractor.run_with_previous(
            story_file,
            None,
            previous_data=global_assets.load_characters(),
            style=args.style,
        )
    else:
        data = extractor.run(story_file, style=args.style)
    global_assets.save_characters_from_chapter(data, args.chapter_name)
