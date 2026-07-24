import hashlib
import json
import os
import re

from provider.llm_provider import LLMClient
from core.project_paths import resolve_chapter_output_dir
from steps.step1_extract_characters import CharacterExtractor
from steps.step2_extract_props import PropExtractor
from steps.step3_generate_storyboard import StoryboardGenerator


PROMPT_AUDIT_STORYBOARD_ASSETS = """你是一个严谨的AI短剧视频 Prompt 资产引用检查员。请检查每个视频片段 Prompt 中的角色图、道具图和环境图引用是否准确，既要补充遗漏，也要删除多余引用。

检查目标：
1. 如果某个片段的 video_prompt 中明确出现了【已有角色】的视觉实体，但 character_ids 没有包含该角色 id，则补充该 id。
2. 如果某个片段实际发生在【已有环境】中，但 environment_id 没有复用对应环境 id，则改成已有环境 id。
3. 如果某个片段的 video_prompt 中明确出现了【已有道具】的视觉实体，但 prop_ids 没有包含该道具 id，则补充该 id。
4. 如果 character_ids 中包含某个角色 id，但 video_prompt 画面描述中没有出现该角色对应的视觉实体，则从 character_ids 删除该 id。
5. 如果 prop_ids 中包含某个道具 id，但 video_prompt 画面描述中没有出现该道具对应的视觉实体，也没有被角色持有/使用/特写强调，则从 prop_ids 删除该 id。
6. 只检查“画面里实际可见”的角色、道具或场景。对白中单纯提到角色名、地名、道具名、亲属称呼，不代表画面出现，不要因此补充；反过来，如果某角色或道具只在 character_ids/prop_ids 中列出，但 video_prompt 里没有可见画面描述，也必须删除。
7. 判断多余角色时，以 video_prompt 中“图x中的角色”的可见行动、对白、姿态、站位或互动为准；如果一个角色没有任何可见动作、对白、出场位置、被看见/被触碰/被指向的描述，就不要保留在 character_ids。
8. 判断多余道具时，以 video_prompt 中“图x中的道具”的可见状态、持有、使用、移动、特写或互动为准；如果道具只是存在于 prop_ids，但 video_prompt 没有提到它，就不要保留在 prop_ids。
9. 如果只是“坟头”“棺材”“院门”等可交互物体或局部道具，不要误判为新环境图；环境必须按整体空间匹配。
10. 不要新增不存在的角色 id 或道具 id；普通环境不要新增不存在的 environment_id。唯一例外：当连续超过 3 个片段复用同一环境图，且后续片段剧情确实需要同场景图生图变体时，可以在 corrections 中新增本章节尚不存在的 environment_id。
11. 如果你修正了 character_ids、prop_ids 或 environment_id，必须同步返回修正后的 video_prompt，使其中的图号引用完全匹配新资产顺序：
   - 图1 永远是 environment_id 对应的环境图。
   - 图2、图3... 必须严格按 character_ids 顺序映射到角色图。
   - 角色图之后继续按 prop_ids 顺序映射到道具图。
   - 如果补充了角色 id，video_prompt 中新出现的该角色必须改成对应图号，例如补充第三个角色后应使用“图4中的角色”。
   - 如果补充了道具 id，video_prompt 中新出现的该道具必须改成“图x中的道具”。
   - 如果删除了角色 id 或道具 id，必须把 video_prompt 中剩余角色和道具的图号重新编号；不要保留跳号或旧图号。
   - 只能调整图号引用、角色/道具 id 列表，以及与图号绑定的极少量文字；不要改剧情、动作、对白和叙事内容。
12. 如果 character_ids、prop_ids 和 environment_id 已经正确，但 video_prompt 的图号引用与它们不一致，也要返回修正后的 video_prompt。
13. 修正后的 video_prompt 仍然禁止使用角色姓名；角色第一次出场、切换到另一个角色、或容易混淆主语时，必须保留“图x中的角色”作为主语。同一个角色的一组连续动作、表情变化或对白，可以只在第一个动作/第一句对白前保留“图x中的角色”，后续连续动作可以省略重复主语；不能用“他/她/少年/老人/师父/男孩”等代词或称呼替代。
14. 修正后的 video_prompt 中所有道具引用都必须写成“图x中的道具”，不能写“图x中的符纸/战刀/木柴”等带道具名称的表达。
15. 修正后的 video_prompt 中所有角色对白都必须使用中文双引号“……”包裹，不能使用英文双引号或单引号包裹对白。
16. 修正后的 video_prompt 中镜头语言只描述客观镜头和分镜形式，不能加入“为了表现/用于突出/体现/展现/这个片段属于/该片段属于”等意图解释或总结判断；“镜头采用/分镜采用/镜头语言采用”后面只能接客观镜头类型、运镜方式、剪辑速度或分镜形式，不能接角色、道具、图号、人物动作或剧情对象；video_prompt 末尾的镜头/分镜描述段不能出现“图x中的角色”“图x中的道具”或具体角色、道具、动作内容。
16.1 对照输入的“角色图索引”和“道具图索引”检查所有 environment 字段。environment 只能描述普通背景空间、建筑、地形、天气、光线、色调、氛围和稳定背景物，严禁包含索引中任何已有角色或已有道具的资产信息：不得出现已有角色的姓名、身份、年龄、外貌、服装、动作或其描述改写，也不得出现已有道具的名称、外形、材质、颜色、纹理、功能、状态或其描述改写。
16.2 如果 environment 混入了已有角色或已有道具的资产信息，必须在 corrections 中返回清理后的 environment：只删除或改写与索引资产匹配的部分，保留普通背景物、原地点识别度、建筑/地形空间关系、天气、光线、色调和氛围。被移除的已有角色、已有道具及其状态只能保留在 video_prompt 中。不得为了清理 environment 而删除、改写 video_prompt 中的剧情或动作。
17. 检查是否存在连续超过 3 个视频片段使用同一个 environment_id、且环境图描述完全相同或实际指向同一张环境图的情况；这不是必然错误，需要结合后续片段剧情判断是否应该继续复用，还是需要基于当前环境图生成同场景变体图。
18. 当第 4 个及后续连续片段仍发生在同一地点时，请判断当前片段剧情是否已经转移到原场景内不同观察方向、不同局部空间、不同建筑区域、不同地形范围或不同机位；如果是，应优先改用 storyboards 中已经存在的同场景变体环境 id；如果没有可用变体 id，可以在 corrections 中从当前已有最大 environment_id + 1 开始新增同场景图生图变体 environment_id。判断时可以参考 video_prompt 中的剧情发生点，但生成的 environment 描述不得写入角色图索引或道具图索引中的已有资产信息。
19. 同场景变体环境的目标是使用图生图方法参考当前/原环境图，保持地点、时代、风格、光线主基调、材质和空间连续性，同时根据当前片段剧情调整视角、局部细节、取景区域、景别距离、机位高度、前中后景关系或主要光源位置。
20. reference_environment_id 为 null、空值或省略时，不属于同场景图生图变体，不要按同场景变体规则修正 environment；只有 reference_environment_id 是有效数字且指向已有环境 id 时，才检查图生图变体描述。
21. 如果某个分镜带有有效 reference_environment_id，必须检查它的 environment 是否以“基于参考环境图，”开头，并结合当前片段剧情写出新的静态取景范围、构图方位或局部细节；描述正文中不要再写 environment_id，也不要再使用“图生图变体”等重复说明。不要只写“更压抑”“更局促”“更昏暗”，不要写入角色图索引或道具图索引中的已有资产信息，也不要生成与当前片段剧情无关的新地点、新天气或新布置。
22. 如果 reference_environment_id 变体环境的前缀不正确，或缺少基于当前剧情的视角、局部细节或构图调整，且该分镜本身有 environment 字段，必须在 corrections 中返回修正后的 environment，统一以“基于参考环境图，”开头，并补充具体的静态空间、稳定布置、光线、色调、构图方位和可稳定存在的背景元素；不要改剧情和 video_prompt。
23. 如果连续超过 3 个片段复用同一环境图，且你判断后续片段需要换视角、局部细节或根据剧情发生点调整环境图，但没有可用的同场景变体环境 id，必须在 corrections 中为对应 storyboard_id 新增本章节同场景图生图变体 environment_id、reference_environment_id 和 environment。新增 environment_id 必须从当前已有最大 environment_id + 1 开始递增；reference_environment_id 必须填写被参考的原 environment_id；environment 必须以“基于参考环境图，”开头，并按剧情发生位置调整视角、局部细节或取景范围，正文不再重复 environment_id。
23.1 新增同场景变体后，不要只修正创建变体的第一个片段。必须继续检查其后的连续片段：凡是仍发生在该变体所描述的同一取景区域、观察方向或剧情发生点，都要分别加入 corrections，并复用同一个新 environment_id、reference_environment_id 和 environment；直到剧情切回原环境取景、转到另一局部空间或切换地点为止。不要为这些连续片段重复创建多个内容相同的新 environment_id。
24. 检查多人物同场的空间交代：如果一个连续环境里有 3 个及以上重要人物，或后续有角色参与对白/动作但此前没有可见入场、站位、同框关系或镜头揭示，必须修正相关 video_prompt；同一连续场景里的全人物建立镜头只需要一次，不要要求每个后续片段都保留全场所有人物。
25. 修正多人物空间交代时，优先在该场景首次多人物同场的片段中加入一次全人物全景/中远景建立镜头，交代空间布局、人物大致站位、坐站状态、距离关系、视线方向或对峙关系；后续片段按照当前剧情正常安排单人、双人、特写、正反打或局部动作镜头。
26. 多人物空间交代的修正只能补充站位、入画方式、同框关系和客观镜头语言，不能新增原文没有的剧情事件、对白、冲突结果或人物关系；如果某角色在当前片段没有实际可见、说话、动作、被看见或被互动，必须从 character_ids 中删除，不要为了维持全场站位而保留；如果原文明确是突然闯入、伏击、暗中现身、揭示隐藏人物、惊吓出现，则不要提前暴露该角色，只在出现片段内补足入场/现身过程。
27. 不要修改 duration、rhythm 等其他字段。
28. 如果无需修改，返回空 corrections 数组。

请只输出 JSON，不要输出解释。格式如下：
```json
{{
  "corrections": [
    {{
      "storyboard_id": 1,
      "character_ids": [1, 3],
      "prop_ids": [1],
      "environment_id": 2,
      "reference_environment_id": 1,
      "environment": "修正后的环境描述；只有需要补充同场景图生图变体的剧情取景、视角或局部细节调整时返回",
      "environment_changed": false,
      "video_prompt": "修正图号引用后的完整 video_prompt",
      "reason": "简短说明为什么修正"
    }}
  ]
}}
```
字段说明：
- corrections 只包含需要修改的分镜。
- character_ids 必须是该分镜最终应使用的完整角色 id 列表，顺序按画面中图2、图3...引用顺序；如果删除后没有角色，返回空数组 []；如果不需要改角色，可省略。
- prop_ids 必须是该分镜最终应使用的完整道具 id 列表，顺序接在角色图之后；如果删除后没有道具，返回空数组 []；如果不需要改道具，可省略。
- environment_id 是该分镜最终应复用的环境 id；如果需要新增同场景图生图变体，可填写当前已有最大 environment_id + 1 起的新 id；如果不需要改环境，可省略。
- reference_environment_id 是当前环境图生成时应参考的本章节原环境 id；新增同场景图生图变体时必须填写，普通环境可省略或返回 null。
- environment 在原描述含有已有角色/已有道具的资产信息、新增同场景图生图变体，或同场景图生图变体的前缀、视角、局部细节或构图需要调整时返回；变体必须以“基于参考环境图，”开头，具体参考 id 只填写在 reference_environment_id 中，不要写进 environment 正文。environment 可以包含普通稳定背景物，但禁止出现角色图索引或道具图索引中已有资产的名称、身份、外观、材质、功能、状态或其描述改写。
- video_prompt 是修正图号引用后的完整视频生成 Prompt；只要 character_ids、prop_ids、environment_id 或原描述图号映射发生变化，就必须提供。
- environment_changed 按修正后的 environment_id 与上一分镜环境是否不同填写；如果不确定可省略，程序会自动重算。

用户输入：
- 角色图索引：
{characters_json}

- 道具图索引：
{props_json}

- 已有环境图/环境索引：
{environments_json}

- 待检查分镜：
{storyboards_json}
"""


class StoryboardAssetAuditor:
    """步骤3b：检查并修正分镜稿中的角色、道具和环境资产引用。"""

    def __init__(self, output_dir="output", model="gemini-3.1-pro-preview"):
        self.output_dir = output_dir
        self.model = model
        self.llm = LLMClient(model=model)
        self.storyboard_generator = StoryboardGenerator(output_dir=output_dir, model=model)
        self.save_path = os.path.join(output_dir, "storyboards_asset_audit.json")

    def run(self, characters=None, props=None, force=False):
        print("\n[步骤3b] 检查并修正视频 Prompt 资产引用...")
        storyboards = self.storyboard_generator.load()
        characters = characters if characters is not None else self._load_characters_for_asset_audit()
        props = props if props is not None else self._load_props_for_asset_audit()

        before = json.dumps(storyboards, ensure_ascii=False, sort_keys=True)
        storyboards = self.audit_and_fix_asset_references(storyboards, characters, props=props, force=force)
        after = json.dumps(storyboards, ensure_ascii=False, sort_keys=True)
        if after != before:
            self.storyboard_generator.save(storyboards)
        return storyboards

    def audit_and_fix_asset_references(self, storyboards, characters=None, props=None, force=False):
        """调用 LLM 检查分镜是否遗漏已有角色图、道具图或环境图引用，并自动修正字段。"""
        characters = characters or []
        props = props or []
        if not storyboards:
            return storyboards

        characters_for_prompt = self._build_character_asset_index(characters)
        props_for_prompt = self._build_prop_asset_index(props)
        environments_for_prompt = self._build_environment_asset_index(storyboards)
        if not characters_for_prompt and not environments_for_prompt:
            return storyboards

        audit_hash = self._asset_audit_hash(storyboards, characters_for_prompt, props_for_prompt, environments_for_prompt)
        if not force and self._asset_audit_is_current(audit_hash):
            print("  分镜资产引用检查已是最新，跳过LLM检查")
            return storyboards

        print("  调用LLM检查视频 Prompt 是否遗漏角色图或环境图引用...")
        prompt = PROMPT_AUDIT_STORYBOARD_ASSETS.format(
            characters_json=json.dumps(characters_for_prompt, ensure_ascii=False, indent=2),
            props_json=json.dumps(props_for_prompt, ensure_ascii=False, indent=2),
            environments_json=json.dumps(environments_for_prompt, ensure_ascii=False, indent=2),
            storyboards_json=json.dumps(self._storyboards_for_asset_audit(storyboards), ensure_ascii=False, indent=2),
        )
        response = self.llm.generate(prompt)
        audit_result = self._parse_json(response)
        if not isinstance(audit_result, dict) or "corrections" not in audit_result:
            print("  警告：分镜资产引用检查结果无法解析，跳过自动修正")
            return storyboards

        corrections = audit_result.get("corrections", [])
        changed = self._apply_asset_audit_corrections(
            storyboards,
            corrections,
            characters_for_prompt,
            props_for_prompt,
            environments_for_prompt,
        )
        final_audit_hash = self._asset_audit_hash(storyboards, characters_for_prompt, props_for_prompt, environments_for_prompt)
        self._save_asset_audit(final_audit_hash, corrections, changed)
        if changed:
            print("  视频 Prompt 资产引用检查完成，已自动修正遗漏引用")
        else:
            print("  视频 Prompt 资产引用检查完成，未发现需要修正的遗漏")
        return storyboards

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

    def _build_character_asset_index(self, characters):
        character_images = self._load_character_images_for_asset_audit()
        indexed = []
        for char in characters or []:
            if not isinstance(char, dict):
                continue
            char_id = char.get("id")
            if not isinstance(char_id, int):
                continue
            image_info = character_images.get(char.get("name", ""), {})
            indexed.append({
                "id": char_id,
                "name": char.get("name", ""),
                "brief_description": char.get("brief_description", ""),
                "appearance": char.get("appearance", ""),
                "clothing": char.get("clothing", ""),
                "image_path": image_info.get("path", "") if isinstance(image_info, dict) else "",
            })
        return indexed

    def _build_prop_asset_index(self, props):
        prop_images = self._load_prop_images_for_asset_audit()
        indexed = []
        for prop in props or []:
            if not isinstance(prop, dict):
                continue
            prop_id = prop.get("id")
            if not isinstance(prop_id, int):
                continue
            image_info = prop_images.get(prop.get("name", ""), {})
            indexed.append({
                "id": prop_id,
                "name": prop.get("name", ""),
                "brief_description": prop.get("brief_description", ""),
                "visual_description": prop.get("visual_description", ""),
                "function": prop.get("function", ""),
                "image_path": image_info.get("path", "") if isinstance(image_info, dict) else "",
            })
        return indexed

    def _build_environment_asset_index(self, storyboards):
        indexed = {}
        for sb in storyboards:
            env_id = sb.get("environment_id")
            env_desc = sb.get("environment", "")
            if not isinstance(env_id, int) or not env_desc:
                continue
            indexed.setdefault(env_id, {
                "id": env_id,
                "environment_description": env_desc,
                "image_path": "",
            })

        return [indexed[key] for key in sorted(indexed)]

    def _storyboards_for_asset_audit(self, storyboards):
        audit_items = []
        for sb in storyboards:
            audit_items.append({
                "storyboard_id": sb.get("storyboard_id"),
                "environment_id": sb.get("environment_id"),
                "reference_environment_id": sb.get("reference_environment_id"),
                "environment": sb.get("environment", ""),
                "environment_changed": sb.get("environment_changed"),
                "character_ids": sb.get("character_ids", []),
                "prop_ids": sb.get("prop_ids", []),
                "rhythm": sb.get("rhythm", ""),
                "video_prompt": sb.get("video_prompt", ""),
            })
        return audit_items

    def _apply_asset_audit_corrections(self, storyboards, corrections, characters_index, props_index, environments_index):
        if not isinstance(corrections, list):
            return self._recompute_environment_changed(storyboards)

        allowed_character_ids = {char["id"] for char in characters_index}
        allowed_prop_ids = {prop["id"] for prop in props_index}
        allowed_environment_ids = {env["id"] for env in environments_index}
        storyboards_by_id = {sb.get("storyboard_id"): sb for sb in storyboards}
        storyboard_order = {sb.get("storyboard_id"): index for index, sb in enumerate(storyboards)}
        corrections = sorted(
            (correction for correction in corrections if isinstance(correction, dict)),
            key=lambda correction: storyboard_order.get(correction.get("storyboard_id"), len(storyboards)),
        )
        changed = False

        for correction in corrections:
            sb = storyboards_by_id.get(correction.get("storyboard_id"))
            if not sb:
                continue

            # 先验证整条 correction，再统一提交，避免部分字段成功、部分字段失败。
            new_character_ids = None
            if "character_ids" in correction:
                new_character_ids = self._validated_ids(correction.get("character_ids"), allowed_character_ids)
                if new_character_ids is None:
                    print(f"  分镜 {sb.get('storyboard_id')} correction 无效：character_ids 格式或取值错误，整条跳过")
                    continue

            new_prop_ids = None
            if "prop_ids" in correction:
                new_prop_ids = self._validated_ids(correction.get("prop_ids"), allowed_prop_ids)
                if new_prop_ids is None:
                    print(f"  分镜 {sb.get('storyboard_id')} correction 无效：prop_ids 格式或取值错误，整条跳过")
                    continue

            environment_fields = {"environment_id", "reference_environment_id", "environment"}
            has_environment_correction = bool(environment_fields.intersection(correction))
            old_environment_id = sb.get("environment_id")
            new_environment_id = old_environment_id
            new_reference_environment_id = self._normalize_optional_int(sb.get("reference_environment_id"))
            new_environment = sb.get("environment", "")
            is_new_variant = False

            if has_environment_correction:
                if "environment_id" in correction:
                    new_environment_id = self._normalize_optional_int(correction.get("environment_id"))
                    if new_environment_id is None:
                        print(f"  分镜 {sb.get('storyboard_id')} correction 无效：environment_id 格式或取值错误，整条跳过")
                        continue

                if "reference_environment_id" in correction:
                    raw_reference_id = correction.get("reference_environment_id")
                    new_reference_environment_id = self._normalize_optional_int(raw_reference_id)
                    if raw_reference_id not in (None, "", "null") and new_reference_environment_id is None:
                        print(
                            f"  分镜 {sb.get('storyboard_id')} correction 无效："
                            "reference_environment_id 格式或取值错误，整条跳过"
                        )
                        continue

                if "environment" in correction:
                    raw_environment = correction.get("environment")
                    if not isinstance(raw_environment, str) or not raw_environment.strip():
                        print(f"  分镜 {sb.get('storyboard_id')} correction 无效：environment 不能为空，整条跳过")
                        continue
                    new_environment = raw_environment.strip()

                if new_environment_id in allowed_environment_ids:
                    if (
                        new_reference_environment_id is not None
                        and (
                            new_reference_environment_id not in allowed_environment_ids
                            or new_reference_environment_id == new_environment_id
                        )
                    ):
                        print(
                            f"  分镜 {sb.get('storyboard_id')} correction 无效："
                            "reference_environment_id 未指向其他已有环境，整条跳过"
                        )
                        continue

                    # 切换到已有环境时，以该环境资产的标准描述为准，防止 ID 与描述错位。
                    if new_environment_id != old_environment_id:
                        matched_environment = self._find_environment_asset(new_environment_id, environments_index)
                        if not matched_environment:
                            print(f"  分镜 {sb.get('storyboard_id')} correction 无效：找不到目标环境，整条跳过")
                            continue
                        new_environment = matched_environment.get("environment_description", "")
                        if not isinstance(new_environment, str) or not new_environment.strip():
                            print(f"  分镜 {sb.get('storyboard_id')} correction 无效：目标环境描述为空，整条跳过")
                            continue
                        new_environment = new_environment.strip()
                        if "reference_environment_id" not in correction:
                            new_reference_environment_id = None
                else:
                    if not self._is_valid_new_variant_environment(
                        new_environment_id,
                        correction,
                        allowed_environment_ids,
                        storyboards,
                        sb,
                    ):
                        print(f"  分镜 {sb.get('storyboard_id')} correction 无效：新增环境变体校验失败，整条跳过")
                        continue
                    is_new_variant = True
                    new_reference_environment_id = self._normalize_optional_int(
                        correction.get("reference_environment_id")
                    )
                    new_environment = correction.get("environment", "").strip()

            if "video_prompt" in correction:
                new_video_prompt = correction.get("video_prompt")
                if not isinstance(new_video_prompt, str) or not new_video_prompt.strip():
                    print(f"  分镜 {sb.get('storyboard_id')} correction 无效：video_prompt 不能为空，整条跳过")
                    continue
                new_video_prompt = new_video_prompt.strip()
            else:
                new_video_prompt = None

            # 所有字段验证完成，以下开始统一提交。
            if new_character_ids is not None:
                if new_character_ids != sb.get("character_ids", []):
                    print(
                        f"  分镜 {sb.get('storyboard_id')} 角色引用修正: "
                        f"{sb.get('character_ids', [])} -> {new_character_ids}"
                    )
                    sb["character_ids"] = new_character_ids
                    changed = True

            if new_prop_ids is not None:
                if new_prop_ids != sb.get("prop_ids", []):
                    print(
                        f"  片段 {sb.get('storyboard_id')} 道具引用修正: "
                        f"{sb.get('prop_ids', [])} -> {new_prop_ids}"
                    )
                    sb["prop_ids"] = new_prop_ids
                    changed = True

            if has_environment_correction:
                if new_environment_id != old_environment_id:
                    print(
                        f"  分镜 {sb.get('storyboard_id')} 环境引用修正: "
                        f"{old_environment_id} -> {new_environment_id}"
                    )
                    sb["environment_id"] = new_environment_id
                    changed = True

                if is_new_variant:
                    print(
                        f"  分镜 {sb.get('storyboard_id')} 新增同场景变体环境，"
                        f"参考环境 {new_reference_environment_id}"
                    )
                    allowed_environment_ids.add(new_environment_id)
                    environments_index.append({
                        "id": new_environment_id,
                        "environment_description": new_environment,
                        "image_path": "",
                    })
                    changed = True

                if new_reference_environment_id is None:
                    if "reference_environment_id" in sb:
                        sb.pop("reference_environment_id", None)
                        changed = True
                elif new_reference_environment_id != sb.get("reference_environment_id"):
                    sb["reference_environment_id"] = new_reference_environment_id
                    changed = True

                if new_environment != sb.get("environment", ""):
                    sb["environment"] = new_environment
                    changed = True

                # 修改已有环境的标准描述时，同步所有使用该 ID 且保存了描述的分镜。
                if not is_new_variant and "environment" in correction and new_environment_id == old_environment_id:
                    matched_environment = self._find_environment_asset(new_environment_id, environments_index)
                    if matched_environment is not None:
                        matched_environment["environment_description"] = new_environment
                    for related_sb in storyboards:
                        if (
                            related_sb is not sb
                            and related_sb.get("environment_id") == new_environment_id
                            and related_sb.get("environment")
                            and related_sb.get("environment") != new_environment
                        ):
                            related_sb["environment"] = new_environment
                            changed = True

            if new_video_prompt is not None and new_video_prompt != sb.get("video_prompt", ""):
                sb["video_prompt"] = new_video_prompt
                changed = True

        if self._recompute_environment_changed(storyboards):
            changed = True
        return changed

    def _validated_ids(self, values, allowed_ids):
        if not isinstance(values, list):
            return None
        cleaned = []
        for item_id in values:
            try:
                item_id = int(item_id)
            except (TypeError, ValueError):
                return None
            if item_id not in allowed_ids:
                return None
            if item_id not in cleaned:
                cleaned.append(item_id)
        return cleaned

    def _is_valid_new_variant_environment(
        self,
        environment_id,
        correction,
        allowed_environment_ids,
        storyboards,
        storyboard,
    ):
        if not isinstance(environment_id, int) or environment_id <= 0:
            return False
        if environment_id in allowed_environment_ids:
            return False
        if environment_id != max(allowed_environment_ids, default=0) + 1:
            return False
        reference_environment_id = self._normalize_optional_int(correction.get("reference_environment_id"))
        if reference_environment_id not in allowed_environment_ids or reference_environment_id == environment_id:
            return False
        if reference_environment_id != storyboard.get("environment_id"):
            return False
        if self._consecutive_environment_usage(storyboards, storyboard) <= 3:
            return False
        environment = correction.get("environment")
        if not isinstance(environment, str) or not environment.strip():
            return False
        if not environment.startswith("基于参考环境图，"):
            return False
        return True

    def _consecutive_environment_usage(self, storyboards, target_storyboard):
        """返回截至目标分镜（含目标）连续复用当前环境 id 的片段数。"""
        consecutive = 0
        target_environment_id = target_storyboard.get("environment_id")
        for storyboard in storyboards:
            if storyboard.get("environment_id") == target_environment_id:
                consecutive += 1
            else:
                consecutive = 0
            if storyboard is target_storyboard:
                return consecutive
        return 0

    def _clean_ids(self, values, allowed_ids):
        cleaned = []
        if not isinstance(values, list):
            return cleaned
        for item_id in values:
            try:
                item_id = int(item_id)
            except (TypeError, ValueError):
                continue
            if item_id in allowed_ids and item_id not in cleaned:
                cleaned.append(item_id)
        return cleaned

    def _normalize_optional_int(self, value):
        if value in (None, "", "null"):
            return None
        try:
            value = int(value)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def _find_environment_asset(self, environment_id, environments_index):
        for environment in environments_index:
            if environment.get("id") == environment_id:
                return environment
        return None

    def _recompute_environment_changed(self, storyboards):
        changed = False
        previous_env_id = None
        for index, sb in enumerate(storyboards):
            current_env_id = sb.get("environment_id")
            expected = True if index == 0 else current_env_id != previous_env_id
            if sb.get("environment_changed") is not expected:
                sb["environment_changed"] = expected
                changed = True
            previous_env_id = current_env_id
        return changed

    def _asset_audit_hash(self, storyboards, characters_index, props_index, environments_index):
        payload = {
            "storyboards": self._storyboards_for_asset_audit(storyboards),
            "characters": characters_index,
            "props": props_index,
            "environments": environments_index,
            "version": 10,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _asset_audit_is_current(self, audit_hash):
        if not os.path.exists(self.save_path):
            return False
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False
        return data.get("hash") == audit_hash

    def _save_asset_audit(self, audit_hash, corrections, changed):
        os.makedirs(self.output_dir, exist_ok=True)
        data = {
            "hash": audit_hash,
            "changed": changed,
            "corrections": corrections if isinstance(corrections, list) else [],
        }
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_characters_for_asset_audit(self):
        path = os.path.join(self.output_dir, "characters.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
        if isinstance(data, dict):
            return data.get("characters", [])
        if isinstance(data, list):
            return data
        return []

    def _load_character_images_for_asset_audit(self):
        path = os.path.join(self.output_dir, "character_images.json")
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(data, dict):
            return {}
        normalized = {}
        for name, info in data.items():
            normalized[name] = info if isinstance(info, dict) else {"path": info}
        return normalized

    def _load_props_for_asset_audit(self):
        path = os.path.join(self.output_dir, "props.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
        if isinstance(data, dict):
            return data.get("props", [])
        if isinstance(data, list):
            return data
        return []

    def _load_prop_images_for_asset_audit(self):
        path = os.path.join(self.output_dir, "prop_images.json")
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(data, dict):
            return {}
        normalized = {}
        for name, info in data.items():
            normalized[name] = info if isinstance(info, dict) else {"path": info}
        return normalized


def _load_props(output_dir, model):
    prop_extractor = PropExtractor(output_dir=output_dir, model=model)
    if not os.path.exists(prop_extractor.save_path):
        return []
    prop_data = prop_extractor.load()
    return prop_data.get("props", []) if isinstance(prop_data, dict) else []


if __name__ == "__main__":
    import argparse
    from core.project_paths import resolve_chapter_output_dir, resolve_project_path

    parser = argparse.ArgumentParser(description="步骤3b：检查并修正分镜稿资产引用")
    parser.add_argument("--output-dir", default="output", help="当前章节输出目录")
    parser.add_argument("--chapter-name", default="chapter_01", help="章节文件夹名；留空则直接使用 output-dir")
    parser.add_argument("--model", default="gemini-3.1-pro-preview", help="LLM 模型")
    parser.add_argument("--not-first-chapter", action="store_true", help="兼容参数；本步骤使用当前章节 assets")
    parser.add_argument("--force", action="store_true", help="忽略 storyboards_asset_audit.json 缓存，强制重新检查")
    args = parser.parse_args()

    output_dir = resolve_project_path(args.output_dir)
    current_output_dir = resolve_chapter_output_dir(output_dir, args.chapter_name)
    char_data = CharacterExtractor(output_dir=current_output_dir, model=args.model).load()
    props = _load_props(current_output_dir, args.model)
    StoryboardAssetAuditor(output_dir=current_output_dir, model=args.model).run(
        characters=char_data.get("characters", []),
        props=props,
        force=args.force,
    )
