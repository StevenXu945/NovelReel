import json
import os
import re
from provider.llm_provider import LLMClient


MIN_STORYBOARD_DURATION_SECONDS = 8.0
MAX_STORYBOARD_DURATION_SECONDS = 15.0
DEFAULT_STORYBOARD_DURATION_SECONDS = 15.0
STORYBOARD_COUNT_MULTIPLIER = 2


PROMPT_GENERATE_STORYBOARD = """你是一个专业的AI短剧导演、小说情节复现编剧和视频生成提示词编剧。请将以下小说章节严格复现为多个适合输入视频生成模型的短剧视频片段 Prompt。

核心目标：
- 生成适合视频生成模型使用的短剧视频片段 Prompt；目标是严格复现小说原文情节，不是另行改编、浓缩剧情或传统逐镜头编号表。
- 所有片段必须符合整体画面风格“{style}”，包括角色外貌、服装、环境氛围、光影色调、镜头质感和剪辑节奏。
- 必须严格遵循小说原文的事件顺序、人物关系、主线因果、信息揭露顺序、对白推进、动作过程、情绪变化和关键剧情结果。

剧情复现：
- 先按小说原文从头到尾拆分连续剧情节点，再为每个节点生成一个视频片段；每个片段只能覆盖原文中相邻、连续的一段情节，不能把相隔很远的事件合并成一个片段。
- 严格保留原文出现的剧情事件、过渡动作、因果信息、角色反应、环境变化、重要心理转折和对白推进；不能为了节奏压缩或删掉原文中的情节过程。
- 不要把小说情节概括成几个大事件；应按原文实际发生的动作、对话、观察、反应、停顿、转场和信息揭露逐段复现。
- 原文中看似日常的寒暄、停顿、沉默、观察、走动、等待、重复确认，只要承担人物关系、气氛、因果过渡或信息铺垫作用，都必须保留为可见画面或对白。
- 禁止重组信息揭露顺序，禁止提前揭露后文信息，禁止把后发生的对白、动作或反应挪到前面的片段。
- 每个片段不能只写“人物做了一件事”的简单梗概，必须写清楚该剧情节点中“哪个图号角色做了什么、对谁说了什么、造成什么结果”。优先呈现人物行动链和对白推进，身体或情绪反应只写影响剧情理解的关键反应。
- 单个视频片段默认 duration 为 15.0 秒；只有纯场景氛围、环境转场、人物表情反应特写、短暂停顿类低动作量片段，才可以缩短到 8.0 秒。duration 必须在 8.0-15.0 秒之间，不能输出小于 8 秒或大于 15 秒的片段。
- 15 秒片段应尽量承载原文当前节点中更多连续动作和对白，可以包含一组完整的“发起动作 -> 对话回应 -> 继续行动 -> 结果变化”。不要把可以自然连在一起的动作和对白拆成过多只表现表情、眼神、呼吸或停顿的小片段。
- 对 8-15 秒片段，video_prompt 内应优先包含原文当前节点中连续发生的可见动作和对白；如果原文当前节点动作很少，再表现必要的停顿、表情、眼神、呼吸、环境声或沉默，不要为了凑动作新增原文没有的事件。
- 动作场景要按原文写清楚谁先行动、谁回应、谁阻止、谁失败或成功、结果如何变化；阻碍升级只写推动剧情的部分，不需要展开过多手指、衣角、呼吸等微细节。
- 情感场景要优先写角色说了什么、做了什么选择、如何回应对方；表情和眼神只作为辅助，不要把大量篇幅用于细腻表情描写。
- 每个片段的戏剧功能必须来自原文当前剧情节点，例如抛出问题、升级矛盾、暴露秘密、逼迫选择、制造误会、反转局势、推进关系、留下钩子；不要为了增强短剧效果新增原文没有的冲突、误会、反转、危险或钩子。
- 结尾片段必须对应原文章节结尾的实际功能；只有原文结尾本身包含悬念、危险、选择压力或下一步行动欲望时，才强化这种效果。
- 不要删除原文中的走路、看风景、沉默观察、重复情绪等内容；即使它们不承担强情节作用，也应按原文位置并入相邻片段中呈现，不能造成情节跳跃或内容缺失。

片段连贯与自包含：
- 每个 video_prompt 在结合当前 JSON 字段和对应参考图输入时必须自包含，不能使用“上一段”“之前”“刚才”“继续”“同前”等依赖上下文的表达。
- 当前片段中出现的重要人物、道具、环境状态都必须重新描述清楚；物体状态发生变化时，直接写当前状态，例如“一口已经被掀开盖子的棺材”。
- 相邻片段的对白和动作必须严格承接原文前后因果：后一个片段必须从前一个片段结束后的状态自然开始，不要突然切到缺少交代的新行动、新地点、新人物关系或新信息。
- 不要省略关键连接动作，例如角色为什么离开、如何进入新场景、谁先开口、某个决定如何导致下一步行动；这些连接如果在原文中存在，必须体现在相邻片段中。
- 多人物同场时，必须在该连续场景首次多人同场的片段建立一次空间与人物站位，再进入单人特写、正反打、道具特写或局部动作；不能让某个尚未建立过位置的重要角色在后续片段里无铺垫地突然参与对白、动作或互动。
- 当一个连续场景会出现 3 个及以上重要人物，或虽然少于 3 人但站位/关系容易混淆时，只在场景开始、人物群首次同场、或新人物首次进入后的一个片段中安排全人物全景/中远景建立镜头，交代空间布局、所有可见人物的大致站位、坐站状态、距离关系、视线方向或对峙关系；这个全人物建立镜头在同一连续场景中只需要一次。
- 后续片段如果继续使用同一环境图，应按照当前剧情需要正常安排特写、过肩正反打、局部动作、单人或双人镜头；character_ids 只包含当前 video_prompt 画面里实际可见、说话、动作、被看见或被互动的角色，不要为了维持全场站位而把已经建立过但本片段不出场、不说话、不参与动作的角色继续放入 character_ids。
- 后续片段中，只有角色在当前片段首次参与动作/对白且站位可能影响理解时，才补充一句当前站位或入画方式，避免人物像突然出现。
- 只有原文明确设计为突然闯入、伏击、暗中现身、揭示隐藏人物、惊吓出现时，才可以不提前暴露该角色；但必须在出现的片段内写清楚入场/现身过程和镜头揭示方式。
- 每个片段必须输出 continuity 字段，用一句话说明本片段对应原文中的哪一段连续情节、承接了什么前置状态、结尾推进到什么新状态；continuity 可以提到“承接前一片段”，但 video_prompt 里不能出现“上一段”“之前”“刚才”“继续”“同前”等依赖上下文的表达。
- 注意区分“自包含”和“连贯”：自包含的是当前画面状态、人物身份、人物当前状态、关键道具状态和环境描述；连贯的是人物目标、冲突压力、信息递进和对白因果。
- video_prompt 内禁止使用角色姓名，也不要用“年轻道士”“师父”“秦羽”这类称呼单独指代角色；角色第一次出场、切换到另一个角色、或容易混淆主语时，必须写成“图x中的角色”，可以在同一句里描述其年龄感、服装、表情、姿态和当前状态。
- 如果是同一个角色的一组连续动作、表情变化或对白，只需要在第一个动作/第一句对白前写“图x中的角色”，后续连续动作可以省略重复主语，例如“图2中的角色深吸一口气，猛地抬头打断对方，沉声发问“……””。当主语切换到另一个角色时，必须重新写“图x中的角色”。
- 不要用“他/她/少年/老人/师父/男孩接着……”这类代词或称呼替代角色图号；可以直接省略同一角色连续动作的主语，但不能用代词承接。
- video_prompt 内所有道具引用必须写成“图x中的道具”，不要写“图x中的符纸”“图x中的战刀”“图x中的木柴”这类带道具名称的表达；可以在同一句里描述该道具的形状、材质、颜色、纹理和当前状态。

镜头节奏与 video_prompt 写法：
- 每个 video_prompt 是一段完整视频生成提示词，必须包含画面风格、场景空间、出场角色、角色动作、关键道具或事件、必要对白、镜头语言、剪辑节奏、氛围和声音提示；表情情绪只在推动剧情、解释态度变化或承接对白时简洁描述。
- 不要逐镜头编号；根据剧情类型决定分镜格式、运镜方式、镜头切换密度和剪辑风格，并在 video_prompt 中用自然语言客观写清楚镜头和分镜形式。
- 镜头语言只描述客观形式，例如“低角度跟拍、手部特写、眼神特写、道具特写、过肩镜头、双人同框、广角远景、快速推近、横移、遮挡式构图、短促快切、中慢速推进”。不要写“为了表现……”“用于突出……”“体现……”“展现……”“这个片段属于……”“该片段属于……”等意图解释或总结判断。
- “镜头采用……”“分镜采用……”“镜头语言采用……”这类句式后面只能接客观镜头类型、运镜方式、剪辑速度或分镜形式，例如“中慢速推进、短促快切、慢速长镜头、手持跟拍、固定机位、过肩镜头、广角远景、横移镜头、特写交替”。不要在“采用”后面写角色、道具、图号、人物动作或剧情对象。
- video_prompt 末尾的镜头/分镜描述段只写客观镜头类型和剪辑形式，不要出现“图x中的角色”“图x中的道具”或具体角色、道具、动作内容。角色、道具和动作细节只能放在前面的剧情画面描述中，不要放在结尾镜头总结里。
- 可以描述镜头语言和剪辑倾向，但不要使用 Shot 1 / Shot 2 或“一镜、二镜、三镜”逐项列镜头。
- video_prompt 要优先写可见、可听、可被镜头捕捉的主要行为和对白，例如角色进入、阻拦、递交、抢夺、追问、回答、离开、倒下、扶起、拿起或放下道具；微表情、手指、衣角、呼吸、眼神等细节只在原文强调或直接影响剧情时使用。
- 当原文事件很短时，优先原样复现该事件；只允许补足不改变情节的可见过程细节、环境压力、道具状态和人物反应。补充内容必须能从原文当前节点直接推导，不能新增原文没有的新事件、新人物关系、新线索、新冲突或新结果。

镜头和分镜选择
- 高度紧张、危险逼近、追逐、对峙、爆发、反转、交易、倒计时等场景：快节奏紧张剪辑，短镜头、高频切换、快速推近、手部/眼神/道具/线索特写，画面可有轻微晃动和压迫感构图。
- 悬疑、潜入、偷听、调查、发现异常等场景：中慢速悬疑推进，缓慢推进、横移、低角度窥视、遮挡式构图、环境细节特写，保留停顿和不安感。
- 抒情、回忆、关系缓和、孤独、失落、告别等场景：慢节奏抒情长镜头，柔和推拉、稳定构图、人物关系镜头、环境空镜和少量关键表情停留。
- 冲突对白、审问、摊牌、威胁、争执等场景：中快节奏对峙正反打，过肩镜头、双人同框关系镜头、必要的面部特写，重点保留问答、打断、沉默、追问和态度转变。
- 动作、打斗、逃跑、灾难、爆炸等场景：快速动作分镜，广角建立空间，短促特写和动态跟拍表现动作瞬间，关键爆点短暂停顿后爆发。
- 信息揭示、证据出现、关键道具、短信、账本、监控画面等场景：短促清晰的道具大特写、屏幕特写和角色反应特写，不要拖长。

对白要求：
- 原文中出现的对白必须尽量保留原句、原说话顺序、原说话对象和原语气功能；不要为了短剧节奏改写、压缩、合并或删除原文对白。
- 如果原文对白太长，仍优先保留原句；只有在视频提示词可读性确实需要时，才可在不改变含义、不减少信息量、不改变人物态度的前提下做轻微口语化整理，不能删掉关键信息、试探、重复确认、寒暄、迟疑或情绪转折。
- 不要把不同场景、不同时间、不同说话对象的对白合并；不要把后文对白提前；不要新增原文没有的解释、反击、摊牌或金句。
- 心理描写必须优先转化为可见的行动选择、对白、沉默或简洁反应；只有原文已经有对应含义或对白暗示时，才可以转化为人物台词，不能凭空添加新台词。
- 如果角色在原文中重复解释同一信息，仍应保留这种重复的剧情功能，例如强调、试探、犹豫、施压或人物性格；不要自行删除。
- 对白必须使用中文双引号“……”包裹，并嵌入动作和表情描述中；角色说第一句对白或主语切换时必须有角色图号主语，例如：图2中的角色盯着图3中的角色，压低声音说“你到底瞒了我什么？”同一角色连续动作和对白可以省略重复图号。

环境与资产引用：
- 为每个不同环境分配 environment_id，从 1 开始递增；第一个片段 environment_changed 必须为 true。
- 如果当前片段环境与前一个片段完全相同，environment_changed 为 false 且必须省略 environment 字段，表示沿用同一个 environment_id 对应的环境图；否则 environment_changed 为 true 且必须输出 environment 字段。
- environment 描述静态空间与稳定氛围，可包含地点、建筑风格、建筑固定结构、地形、空间布局、天气、整体光线、色调、空间纵深、稳定存在的背景物和背景雾气等。
- environment 严禁包含“角色信息”或“道具信息”中任何已有资产的内容：不得出现已有角色的姓名、身份、年龄、外貌、服装、动作或其描述改写，也不得出现已有道具的名称、外形、材质、颜色、纹理、功能、状态或其描述改写。已有角色和已有道具只能写入 video_prompt，并分别通过 character_ids、prop_ids 引用。
- 普通、未登记为已有角色或已有道具的背景元素可以出现在 environment 中，但不得借背景描述变相复述已有角色或已有道具的信息。剧情中会变化或被角色交互的物体状态，例如打开的门、熄灭/燃烧的火、移动物体、血迹、尸体、棺材状态等，仍应写入 video_prompt。
- character_ids 和 prop_ids 都使用 id 列表，不要使用名称；空环境片段 character_ids 为 []，没有关键道具时 prop_ids 为 []。
- 空镜或空环境片段只能用于证据、危险逼近、环境异常或转场钩子，不能只是看风景或停顿。
- 只有画面中实际可见、被角色持有/使用、或作为特写强调的关键道具才写入 prop_ids。
- video_prompt 中必须用“图1、图2、图3...”引用参考图：图1=环境图；图2、图3...=按 character_ids 顺序排列的角色图；角色图之后继续按 prop_ids 顺序排列道具图。例如 character_ids 有2个、prop_ids 有1个时，图1=环境图，图2/图3=角色图，图4=道具图。
- 当 environment_changed=false 且省略 environment 字段时，图1 仍然是当前 environment_id 对应的环境图。
- 人物特写也必须引用图1作为虚化背景，以保持空间、光线和天气连续；空镜只有图1，若空镜强调关键道具，则图2、图3...=按 prop_ids 顺序排列的道具图。
- 角色外貌、服装、年龄感、发型、气质必须严格参考对应角色图；关键道具的形状、材质、颜色、纹理和状态必须严格参考对应道具图，但在 video_prompt 中只能称为“图x中的道具”。

输出要求：
请严格按照以下 JSON 格式输出，不要输出其他内容：

```json
{{
    "storyboards": [
        {{
            "storyboard_id": 1,
            "duration": 15.0,
            "environment_id": 1,
            "reference_environment_id": null,
            "environment": "以导演视角描述的静态场景空间：深夜山间道观的正殿，木梁高耸，青灰砖地向神龛延伸，殿内烛火稀疏，墙面斑驳，门外冷雾贴着石阶流动，整体光线幽暗压抑，具有东方悬疑短剧的电影质感",
            "environment_changed": true,
            "character_ids": [1, 2],
            "prop_ids": [1],
            "rhythm": "快节奏紧张剪辑",
            "continuity": "对应原文中师徒在正殿发现符纸异常并遭遇门外异响的连续情节，承接两人查看线索的状态，结尾推进到外部威胁逼近。",
            "video_prompt": "整体画面符合{style}。在图1的深夜道观正殿中，图2中的角色站在供桌前，图3中的角色半跪在地查看图4中的道具，图4中的道具呈焦黑质感并带有残破纹路。图2中的角色伸手想拿起图4中的道具，图4中的道具边缘突然冒出冷白火星，图3中的角色猛地按住图2中的角色的手腕，压低声音说“这不是普通邪祟留下的印”。图2中的角色停住手追问“那门外是什么？”殿门外冷雾贴着门缝涌入，门环无风自响，图3中的角色起身挡在图2中的角色身前，低声说“先别开门，把它压回供桌上”。图2中的角色立刻把图4中的道具推回供桌边。分镜采用东方悬疑电影式紧张快切、过肩镜头、双人同框、道具特写、远景切换和压迫式构图。"
        }},
        {{
            "storyboard_id": 2,
            "duration": 15.0,
            "environment_id": 1,
            "reference_environment_id": null,
            "environment_changed": false,
            "character_ids": [1, 2],
            "prop_ids": [1],
            "rhythm": "中慢速悬疑推进",
            "continuity": "承接正殿门外异响和符纸状态变化，本片段对应两人围绕是否开门产生分歧的连续情节，结尾推进到角色准备靠近门闩。",
            "video_prompt": "整体画面符合{style}。在图1的深夜道观正殿中，殿门外的冷雾仍贴着门缝涌入，图4中的道具被压在供桌边，火星已经熄灭但暗红纹路仍在表面浮现。图3中的角色挡在图2中的角色身前，沉声说“门外的东西，是冲你来的”；图2中的角色反问“那我躲到什么时候？”图3中的角色向前半步挡住门闩，说“等我先封住这道门”。图2中的角色没有后退，绕过图3中的角色伸手靠近门闩，图3中的角色立刻抓住图2中的角色的手腕，殿门再次震动。镜头语言采用中慢速推进、过肩正反打、双人同框构图、道具特写、固定机位停顿和结尾动作定格。"
        }}
    ]
}}
```

用户输入：
角色信息：
{characters_json}

道具信息：
{props_json}

小说内容：
{novel_text}
"""


class StoryboardGenerator:
    """步骤3：根据小说原文和角色信息，生成分镜稿"""

    def __init__(self, output_dir="output", model="claude-opus-4-6"):
        self.llm = LLMClient(model=model)
        self.model = model
        self.output_dir = output_dir
        self.save_path = os.path.join(output_dir, "storyboards.json")

    def run(self, novel_file_path, characters, props=None, style="写实"):
        print(f"\n[步骤3] 生成视频片段 Prompt（风格: {style}）...")
        with open(novel_file_path, "r", encoding="utf-8") as f:
            novel_text = f.read()

        word_count = len(novel_text)
        segment_stats = self._estimate_storyboard_count(novel_text)
        suggested_storyboards = segment_stats["suggested_storyboards"]
        print(
            f"  小说字数: {word_count}，动作信号: {segment_stats['action_count']}，"
            f"对白字数: {segment_stats['dialogue_chars']}，参考视频片段数: {suggested_storyboards}"
        )

        characters_json = json.dumps(characters, ensure_ascii=False, indent=2)
        props_json = json.dumps(props or [], ensure_ascii=False, indent=2)
        prompt = PROMPT_GENERATE_STORYBOARD.format(
            novel_text=novel_text,
            characters_json=characters_json,
            props_json=props_json,
            style=style,
            word_count=word_count,
            suggested_storyboards=suggested_storyboards,
        )

        response = self.llm.generate(prompt)

        parsed = self._parse_json(response)
        storyboards = parsed.get("storyboards", []) if isinstance(parsed, dict) else []
        storyboards = self._enforce_storyboard_constraints(storyboards)

        print(f"  共生成 {len(storyboards)} 个视频片段 Prompt")
        for sb in storyboards:
            chars = ", ".join(str(c) for c in sb.get("character_ids", []))
            changed = "新环境" if sb.get("environment_changed") else "同上"
            rhythm = sb.get("rhythm", "")
            print(f"    - 片段{sb['storyboard_id']} [{changed}] {sb.get('duration')}秒 {rhythm} 角色: {chars}")

        self.save(storyboards)
        return storyboards

    def save(self, storyboards):
        os.makedirs(self.output_dir, exist_ok=True)
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(storyboards, f, ensure_ascii=False, indent=2)
        print(f"  分镜稿已保存: {self.save_path}")

    def load(self):
        with open(self.save_path, "r", encoding="utf-8") as f:
            storyboards = json.load(f)

        before = json.dumps(storyboards, ensure_ascii=False, sort_keys=True)
        normalized_storyboards = self._enforce_storyboard_constraints(storyboards)
        after = json.dumps(normalized_storyboards, ensure_ascii=False, sort_keys=True)
        if after != before:
            self.save(normalized_storyboards)

        return normalized_storyboards

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

    def _estimate_storyboard_count(self, novel_text):
        """Estimate video prompt count from length, visible actions, and dialogue volume."""
        word_count = len(novel_text)
        dialogue_chars = self._count_dialogue_chars(novel_text)
        action_count = self._count_action_signals(novel_text)

        length_score = word_count / 520
        action_score = action_count / 8
        dialogue_score = dialogue_chars / 420
        estimated = length_score * 0.55 + action_score * 0.25 + dialogue_score * 0.20

        suggested_storyboards = max(4, round(estimated * STORYBOARD_COUNT_MULTIPLIER))
        return {
            "word_count": word_count,
            "action_count": action_count,
            "dialogue_chars": dialogue_chars,
            "suggested_storyboards": suggested_storyboards,
        }

    def _count_dialogue_chars(self, text):
        patterns = [
            r"“([^”]+)”",
            r"\"([^\"]+)\"",
            r"'([^']+)'",
        ]
        total = 0
        for pattern in patterns:
            total += sum(len(match) for match in re.findall(pattern, text))
        return total

    def _count_action_signals(self, text):
        action_keywords = (
            "走", "跑", "冲", "追", "逃", "躲", "扑", "打", "砍", "刺", "抓", "推", "拉",
            "摔", "跪", "站", "坐", "转身", "回头", "抬头", "低头", "伸手", "握住", "拿起",
            "放下", "打开", "关上", "掀开", "敲", "砸", "撞", "踢", "抱", "扶", "递", "扔",
            "盯", "看", "望", "哭", "笑", "喊", "吼", "问", "说", "沉默", "颤抖", "后退",
            "逼近", "出现", "消失", "倒下", "醒来", "发现", "掏出", "点燃", "熄灭",
        )
        keyword_hits = sum(text.count(keyword) for keyword in action_keywords)
        punctuation_hits = len(re.findall(r"[！？!?。；;]", text))
        return keyword_hits + int(punctuation_hits * 0.25)

    def _enforce_storyboard_constraints(self, storyboards):
        """保存前兜底规范新的视频片段 Prompt 结构。"""
        if not isinstance(storyboards, list):
            return []

        normalized_storyboards = []
        previous_env_id = None
        for sb in storyboards:
            if not isinstance(sb, dict):
                continue
            normalized_storyboards.append(sb)

        for index, sb in enumerate(normalized_storyboards, start=1):
            # 分镜 ID 是内部顺序标识，统一重排可避免重复、缺号和非数字值。
            sb["storyboard_id"] = index
            sb["duration"] = self._normalize_duration(sb.get("duration"))
            sb["environment_id"] = self._normalize_positive_int(
                sb.get("environment_id"),
                default=previous_env_id or index,
            )

            # 该字段完全由相邻 environment_id 决定，不信任 LLM 返回值。
            sb["environment_changed"] = (
                True if index == 1 else sb.get("environment_id") != previous_env_id
            )

            reference_env_id = self._normalize_optional_int(sb.get("reference_environment_id"))
            if reference_env_id and reference_env_id != sb.get("environment_id"):
                sb["reference_environment_id"] = reference_env_id
            else:
                sb.pop("reference_environment_id", None)

            sb["character_ids"] = self._normalize_id_list(sb.get("character_ids", []))
            sb["prop_ids"] = self._normalize_id_list(sb.get("prop_ids", []))
            sb.setdefault("rhythm", "中速剧情推进")
            sb.setdefault("continuity", "承接原文相邻情节，并推进到本片段结尾的新状态。")

            video_prompt = sb.get("video_prompt") or ""
            sb["video_prompt"] = str(video_prompt).strip()

            previous_env_id = sb.get("environment_id")

        return normalized_storyboards

    def _normalize_duration(self, duration):
        try:
            duration = float(duration)
        except (TypeError, ValueError):
            duration = DEFAULT_STORYBOARD_DURATION_SECONDS
        if duration <= 0:
            duration = DEFAULT_STORYBOARD_DURATION_SECONDS
        return min(MAX_STORYBOARD_DURATION_SECONDS, max(MIN_STORYBOARD_DURATION_SECONDS, duration))

    def _normalize_int(self, value, default=1):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _normalize_positive_int(self, value, default=1):
        value = self._normalize_int(value, default=default)
        return value if value > 0 else default

    def _normalize_optional_int(self, value):
        if value in (None, "", "null"):
            return None
        try:
            value = int(value)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def _normalize_id_list(self, values):
        if not isinstance(values, list):
            return []
        cleaned = []
        for value in values:
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
            if value not in cleaned:
                cleaned.append(value)
        return cleaned

if __name__ == "__main__":
    import argparse
    from core.project_paths import resolve_chapter_output_dir, resolve_project_path
    from steps.step1_extract_characters import CharacterExtractor
    from steps.step2_extract_props import PropExtractor

    parser = argparse.ArgumentParser(description="步骤3：生成分镜稿")
    parser.add_argument("--story-file", default="story.txt", help="小说章节文本路径")
    parser.add_argument("--output-dir", default="output", help="当前章节输出目录")
    parser.add_argument("--chapter-name", default="chapter_01", help="章节文件夹名；留空则直接使用 output-dir")
    parser.add_argument("--model", default="gemini-3.1-pro-preview", help="LLM 模型")
    parser.add_argument("--not-first-chapter", action="store_true", help="兼容参数；本步骤使用当前章节 characters.json")
    args = parser.parse_args()

    output_dir = resolve_project_path(args.output_dir)
    story_file = resolve_project_path(args.story_file)
    current_output_dir = resolve_chapter_output_dir(output_dir, args.chapter_name)
    char_data = CharacterExtractor(output_dir=current_output_dir, model=args.model).load()
    prop_extractor = PropExtractor(output_dir=current_output_dir, model=args.model)
    prop_data = prop_extractor.load() if os.path.exists(prop_extractor.save_path) else {"props": []}
    StoryboardGenerator(output_dir=current_output_dir, model=args.model).run(
        story_file,
        char_data["characters"],
        props=prop_data.get("props", []),
        style=char_data.get("style", "写实"),
    )
