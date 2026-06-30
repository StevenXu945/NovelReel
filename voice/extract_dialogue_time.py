import argparse
import glob
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


VOICE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = VOICE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CHARACTER_IMAGE_RE = re.compile(r"character_(\d+)", re.IGNORECASE)
PARENTHETICAL_RE = re.compile(r"[（(].*?[）)]")
VOICE_AGE_STAGES = ("幼年", "少年", "中年", "老年")
ROLE_SLOTS = ("男主", "女主", "配角1", "配角2", "配角3", "配角4", "配角5", "配角6")
VOICE_POOLS = {
    f"{role_slot}_{age_stage}": [f"{role_slot}_{age_stage}"]
    for role_slot in ROLE_SLOTS
    for age_stage in VOICE_AGE_STAGES
}


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extract_json_from_response(response):
    text = str(response or "").strip()
    if not text:
        raise ValueError("empty LLM response")

    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = min(
            [position for position in (text.find("{"), text.find("[")) if position != -1],
            default=-1,
        )
        if start == -1:
            raise
        end = max(text.rfind("}"), text.rfind("]"))
        if end <= start:
            raise
        return json.loads(text[start : end + 1])


def require_file(path, label):
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def require_dir(path, label):
    if not path.is_dir():
        raise FileNotFoundError(f"{label} not found: {path}")


def require_command(name):
    if shutil.which(name) is None:
        raise RuntimeError(f"Required command not found: {name}")


def resolve_project_path(path):
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (PROJECT_ROOT / path).resolve()


def resolve_model_path_or_name(value):
    if not value:
        return VOICE_DIR / "faster-whisper-large"
    path = Path(value)
    if path.is_absolute() or "/" in str(value) or path.exists():
        return resolve_project_path(path)
    return value


def run_command(command):
    print("+ " + " ".join(map(str, command)))
    subprocess.run(command, check=True)


def normalize_age_stage(age):
    age = str(age or "")
    if "幼年" in age or "童年" in age:
        return "幼年"
    if "少年" in age:
        return "少年"
    if "老年" in age or "晚年" in age:
        return "老年"
    if "青年" in age or "成年" in age or "中年" in age:
        return "中年"

    match = re.search(r"(\d+)", age)
    if not match:
        return "中年"

    value = int(match.group(1))
    if value < 13:
        return "幼年"
    if value < 25:
        return "少年"
    if value < 60:
        return "中年"
    return "老年"


def normalize_character_name(name):
    return PARENTHETICAL_RE.sub("", str(name or "")).strip()


def character_identity_name(character):
    previous_name = str(character.get("previous_name") or "").strip()
    if previous_name:
        return normalize_character_name(previous_name)
    return normalize_character_name(character.get("name")) or f"角色{character['id']}"


def build_character_lookup(characters_data):
    characters = characters_data.get("characters", characters_data)
    by_id = {}
    canonical_by_identity = {}

    for character in characters:
        character_id = int(character["id"])
        identity_name = character_identity_name(character)
        age_stage = normalize_age_stage(character.get("age"))
        identity_key = (identity_name, age_stage)
        previous_id = canonical_by_identity.get(identity_key)
        if previous_id is None or character_id < previous_id:
            canonical_by_identity[identity_key] = character_id

    for character in characters:
        character_id = int(character["id"])
        name = character.get("name") or f"角色{character_id}"
        identity_name = character_identity_name(character)
        age_stage = normalize_age_stage(character.get("age"))
        canonical_id = canonical_by_identity[(identity_name, age_stage)]
        by_id[character_id] = {
            "id": character_id,
            "canonical_id": canonical_id,
            "name": name,
            "identity_name": identity_name,
            "gender": character.get("gender", ""),
            "age_stage": age_stage,
            "brief_description": character.get("brief_description", ""),
        }

    return by_id


def canonicalize_speaker_id(speaker_id, character_lookup):
    if speaker_id in (None, "", "unknown", "null"):
        return None
    try:
        speaker_id = int(speaker_id)
    except (TypeError, ValueError):
        return None
    character = character_lookup.get(speaker_id)
    if character:
        return character["canonical_id"]
    return speaker_id


def character_name(character_lookup, speaker_id):
    if speaker_id is None:
        return "未知角色"
    character = character_lookup.get(int(speaker_id))
    if character:
        return character.get("name", f"角色{speaker_id}")
    return f"角色{speaker_id}"


def canonical_characters(character_lookup):
    characters = {}
    for character in character_lookup.values():
        canonical_id = character["canonical_id"]
        existing = characters.get(canonical_id)
        if existing is None or character["id"] == canonical_id:
            characters[canonical_id] = {
                "id": canonical_id,
                "name": character.get("identity_name") or character.get("name") or f"角色{canonical_id}",
                "display_name": character.get("name") or f"角色{canonical_id}",
                "identity_name": character.get("identity_name") or character.get("name") or f"角色{canonical_id}",
                "gender": character.get("gender", ""),
                "age_stage": character.get("age_stage", ""),
                "brief_description": character.get("brief_description", ""),
            }
    return characters


def image_character_id(ref_image):
    match = CHARACTER_IMAGE_RE.search(str(ref_image))
    if not match:
        return None
    return int(match.group(1))


def build_figure_map(clip, character_lookup):
    figure_map = {}
    for index, ref_image in enumerate(clip.get("ref_images", []), start=1):
        character_id = image_character_id(ref_image)
        if character_id is None:
            continue
        character = character_lookup.get(character_id)
        if character is None:
            figure_map[index] = {
                "id": character_id,
                "canonical_id": character_id,
                "name": f"角色{character_id}",
            }
        else:
            figure_map[index] = character
    return figure_map


def compact_clip(clip, character_lookup):
    figure_map = build_figure_map(clip, character_lookup)
    figures = []
    for figure_index, character in sorted(figure_map.items()):
        figures.append(
            {
                "figure": f"图{figure_index}",
                "character_id": character["canonical_id"],
                "name": character["name"],
                "age_stage": character.get("age_stage", ""),
            }
        )

    return {
        "storyboard_id": clip.get("storyboard_id"),
        "ref_images": clip.get("ref_images", []),
        "figures": figures,
        "motion_desc": clip.get("motion_desc", ""),
    }


def role_taxonomy():
    return [
        {
            "role_slot": role_slot,
            "age_stages": list(VOICE_AGE_STAGES),
            "voice_categories": [f"{role_slot}_{age_stage}" for age_stage in VOICE_AGE_STAGES],
        }
        for role_slot in ROLE_SLOTS
    ]


def normalize_role_slot(value):
    value = str(value or "").strip()
    if value in ROLE_SLOTS:
        return value
    if value in ("男主角", "男性主角", "男主人公"):
        return "男主"
    if value in ("女主角", "女性主角", "女主人公"):
        return "女主"
    match = re.search(r"配角\s*([1-6])", value)
    if match:
        return f"配角{match.group(1)}"
    return ""


def normalize_voice_category(role_slot, age_stage):
    role_slot = normalize_role_slot(role_slot)
    age_stage = normalize_age_stage(age_stage)
    if role_slot not in ROLE_SLOTS:
        return None
    return f"{role_slot}_{age_stage}"


def build_dialogue_prompt(video_clips, characters_data, character_lookup, include_screen_text=False):
    compact_clips = [compact_clip(clip, character_lookup) for clip in video_clips]
    characters = characters_data.get("characters", characters_data)

    return f"""你是一个短剧对白归属和角色类型映射助手。请直接根据 video_clips 中每个镜头的 motion_desc、ref_images 图号映射、characters 角色表，以及相邻镜头上下文，提取所有人声对白，判断每句对白是谁说的，并给说话角色映射到固定角色类型。

输出要求：
1. 只提取人声对白，也就是中文引号“”里的角色说话内容；屏幕文字、网页文字、邮件文字、标题字幕不是人声对白，默认不要输出。
2. 但如果 include_screen_text=true，则屏幕文字也输出，speaker_id 填 null。
3. motion_desc 中图号映射来自 ref_images：图1通常是环境，后续 character_x.png 对应角色 id x。当前镜头没有出现说话人时，可以参考相邻镜头推断，例如“门外传来喊声”，后续镜头门外站着某角色并继续同一场对话，则可归属给该角色。
4. 输出 speaker_id 使用角色 id。若同一角色只是换装或同年龄阶段不同造型，使用最早的角色 id；若是少年/中年/老年等成长阶段不同，则使用对应阶段的不同角色 id。
5. 如果无法合理判断说话人，speaker_id 填 null，speaker_name 填“未知角色”。
6. 不要改写对白内容，不要删减引号内文字。
7. 为每句对白判断当前语气，tone 用简短中文描述，例如“平静”“焦急”“愤怒”“疑惑”“讽刺”“哀求”等。
8. role_slot 只能从固定角色槽位中选择：男主、女主、配角1、配角2、配角3、配角4、配角5、配角6。
9. age_stage 只能从固定年龄阶段中选择：幼年、少年、中年、老年。童年归为幼年；小于25岁归为少年；25到59岁归为中年；晚年归为老年。
10. voice_category 必须等于 role_slot + "_" + age_stage，例如“男主_中年”“配角3_老年”。
11. 同一个真实角色在全文里必须保持同一个 role_slot；同一个真实角色的不同年龄阶段只改变 age_stage，不改变 role_slot。
12. 男主、女主只用于真正的主角。其他重要人物按首次重要出场或叙事重要性分配到配角1到配角6，最多 6 个配角槽位。
13. 如果 speaker_id 为 null，role_slot、age_stage、voice_category 也填 null。

请严格只输出 JSON 数组，不要输出解释。数组元素格式：
[
  {{
    "storyboard_id": 1,
    "dialogue_index": 1,
    "speaker_id": 2,
    "speaker_name": "角色名",
    "dialogue": "对白原文",
    "role_slot": "配角1",
    "age_stage": "中年",
    "voice_category": "配角1_中年",
    "tone": "当前语气",
    "reason": "一句话说明归属依据"
  }}
]

include_screen_text={str(include_screen_text).lower()}

characters:
{json.dumps(characters, ensure_ascii=False, indent=2)}

role_taxonomy:
{json.dumps(role_taxonomy(), ensure_ascii=False, indent=2)}

video_clips:
{json.dumps(compact_clips, ensure_ascii=False, indent=2)}
"""


def llm_generate(prompt, model):
    from provider.llm_provider import LLMClient

    client = LLMClient()
    if model:
        client.model = model
    return client.generate(prompt)


def extract_dialogues_with_llm(video_clips, characters_data, character_lookup, model, include_screen_text=False):
    prompt = build_dialogue_prompt(
        video_clips,
        characters_data,
        character_lookup,
        include_screen_text=include_screen_text,
    )
    response = llm_generate(prompt, model)
    if not response:
        raise RuntimeError("LLM request failed")

    data = extract_json_from_response(response)
    if isinstance(data, dict):
        data = data.get("dialogues") or data.get("items") or data.get("result")
    if not isinstance(data, list):
        raise ValueError("LLM response JSON is not a list")

    rows = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue
        speaker_id = canonicalize_speaker_id(item.get("speaker_id"), character_lookup)
        character = character_lookup.get(speaker_id) if speaker_id is not None else None
        role_slot = normalize_role_slot(item.get("role_slot"))
        age_stage = normalize_age_stage(item.get("age_stage") or (character or {}).get("age_stage"))
        voice_category = normalize_voice_category(role_slot, age_stage)
        rows.append(
            {
                "storyboard_id": item.get("storyboard_id"),
                "dialogue_index": item.get("dialogue_index", index),
                "speaker_id": speaker_id,
                "speaker_name": item.get("speaker_name") or character_name(character_lookup, speaker_id),
                "dialogue": item.get("dialogue", ""),
                "role_slot": role_slot or None,
                "age_stage": age_stage if speaker_id is not None else None,
                "voice_category": voice_category,
                "tone": item.get("tone", ""),
                "attribution": "llm",
                "reason": item.get("reason", ""),
            }
        )
    return rows


def load_voice_state(path):
    path = Path(path)
    if not path.exists():
        return {"voice_pools": VOICE_POOLS, "characters": {}}

    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    voice_pools = data.setdefault("voice_pools", {})
    for category, pool in VOICE_POOLS.items():
        voice_pools.setdefault(category, pool)
    data.setdefault("characters", {})
    return data


def voice_identity_key(character):
    return f'{character["identity_name"]}|{character.get("age_stage", "")}'


def choose_voice_id(state, category):
    pool = state.get("voice_pools", {}).get(category) or VOICE_POOLS[category]
    usage = {voice_id: 0 for voice_id in pool}
    for item in state["characters"].values():
        voice_id = item.get("voice_id")
        if voice_id in usage:
            usage[voice_id] += 1
    return min(pool, key=lambda voice_id: (usage[voice_id], pool.index(voice_id)))


def row_role_info(row, character):
    role_slot = normalize_role_slot(row.get("role_slot"))
    age_stage = normalize_age_stage(row.get("age_stage") or character.get("age_stage"))
    voice_category = normalize_voice_category(role_slot, age_stage)
    return role_slot, age_stage, voice_category


def assign_character_voices(rows, character_lookup, state):
    assignments_by_id = {}
    characters = canonical_characters(character_lookup)

    for row in rows:
        speaker_id = row.get("speaker_id")
        if speaker_id is None:
            continue

        character_id = int(speaker_id)
        character = characters.get(character_id) or character_lookup.get(character_id)
        if character is None:
            continue

        identity_key = voice_identity_key(character)
        role_slot, age_stage, voice_category = row_role_info(row, character)
        if not voice_category:
            continue

        record = state["characters"].get(identity_key)
        if record is None:
            record = {
                "character_id": character_id,
                "character_ids": [character_id],
                "name": character["name"],
                "display_name": character["display_name"],
                "gender": character.get("gender", ""),
                "age_stage": age_stage,
                "role_slot": role_slot,
                "voice_category": voice_category,
                "voice_id": choose_voice_id(state, voice_category),
            }
            state["characters"][identity_key] = record
        else:
            record.setdefault("character_ids", [])
            if character_id not in record["character_ids"]:
                record["character_ids"].append(character_id)
                record["character_ids"].sort()
            record.setdefault("name", character["name"])
            record.setdefault("display_name", character["display_name"])
            record.setdefault("gender", character.get("gender", ""))
            record["age_stage"] = age_stage
            record["role_slot"] = role_slot
            record["voice_category"] = voice_category
            if not record.get("voice_id") or record["voice_id"] not in state.get("voice_pools", {}).get(voice_category, []):
                record["voice_id"] = choose_voice_id(state, voice_category)

        assignments_by_id[character_id] = record

    for original_id, character in character_lookup.items():
        record = assignments_by_id.get(character["canonical_id"])
        assignments_by_id[original_id] = record
        if record is not None and original_id not in record["character_ids"]:
            record["character_ids"].append(original_id)
            record["character_ids"].sort()

    return assignments_by_id


def attach_voices(rows, voice_assignments):
    for row in rows:
        speaker_id = row.get("speaker_id")
        assignment = voice_assignments.get(speaker_id) if speaker_id is not None else None
        row["voice_id"] = assignment.get("voice_id") if assignment else None
        row["voice_category"] = assignment.get("voice_category") if assignment else None
    return rows


def extract_dialogues_step(clips_path, characters_path, dialogues_path, voice_state_path, model, include_screen_text=False):
    video_clips = load_json(clips_path)
    characters_data = load_json(characters_path)
    character_lookup = build_character_lookup(characters_data)
    voice_state = load_voice_state(voice_state_path)

    rows = extract_dialogues_with_llm(
        video_clips,
        characters_data,
        character_lookup,
        model,
        include_screen_text=include_screen_text,
    )

    voice_assignments = assign_character_voices(rows, character_lookup, voice_state)
    rows = attach_voices(rows, voice_assignments)
    write_json(voice_state, voice_state_path)
    write_json(rows, dialogues_path)

    for row in rows:
        speaker = row["speaker_id"] if row["speaker_id"] is not None else "unknown"
        print(f'{speaker}：{row["dialogue"]}')
    print(f"saved {dialogues_path}")
    print(f"saved {voice_state_path}")


def extract_wav_from_mp4(mp4_path, wav_path, sample_rate=44100):
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(mp4_path),
            "-vn",
            "-ac",
            "2",
            "-ar",
            str(sample_rate),
            "-c:a",
            "pcm_s16le",
            str(wav_path),
        ]
    )


def separate_vocals_with_demucs(wav_path, demucs_out_dir):
    demucs_out_dir.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "demucs",
            "--two-stems=vocals",
            "-d",
            "cpu",
            "-o",
            str(demucs_out_dir),
            str(wav_path),
        ]
    )

    candidates = sorted(demucs_out_dir.glob(f"*/{wav_path.stem}/vocals.wav"))
    if not candidates:
        raise FileNotFoundError(f"Could not find Demucs vocals.wav under {demucs_out_dir}")

    background_candidates = sorted(demucs_out_dir.glob(f"*/{wav_path.stem}/no_vocals.wav"))
    if not background_candidates:
        raise FileNotFoundError(f"Could not find Demucs no_vocals.wav under {demucs_out_dir}")

    return candidates[-1], background_candidates[-1]


def split_word_tokens(text):
    return [char for char in str(text or "").strip() if not char.isspace()]


def build_word_tokens(word_item, start_token_index):
    text_tokens = split_word_tokens(word_item["text"])
    if not text_tokens:
        return [], start_token_index

    start = float(word_item["start"])
    end = float(word_item["end"])
    duration = max(0.0, end - start)
    token_count = len(text_tokens)
    tokens = []
    for offset, text in enumerate(text_tokens):
        token_start = start + duration * offset / token_count
        token_end = start + duration * (offset + 1) / token_count
        tokens.append(
            {
                "token_index": start_token_index + offset,
                "word_index": word_item["word_index"],
                "sentence_index": word_item["sentence_index"],
                "start": round(token_start, 3),
                "end": round(token_end, 3),
                "text": text,
            }
        )
    return tokens, start_token_index + token_count


def transcribe_audio(model, audio_path, language="zh", beam_size=5, vad_filter=True, word_timestamps=True):
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        beam_size=beam_size,
        vad_filter=vad_filter,
        word_timestamps=word_timestamps,
    )

    items = []
    all_words = []
    all_tokens = []
    word_index = 1
    token_index = 1
    for index, segment in enumerate(segments, start=1):
        words = []
        sentence_tokens = []
        for word in segment.words or []:
            word_item = {
                "word_index": word_index,
                "sentence_index": index,
                "start": round(float(word.start), 3),
                "end": round(float(word.end), 3),
                "text": word.word.strip(),
                "probability": round(float(word.probability), 4),
            }
            words.append(word_item)
            all_words.append(word_item)
            word_tokens, token_index = build_word_tokens(word_item, token_index)
            sentence_tokens.extend(word_tokens)
            all_tokens.extend(word_tokens)
            word_index += 1

        items.append(
            {
                "index": index,
                "start": round(float(segment.start), 2),
                "end": round(float(segment.end), 2),
                "text": segment.text.strip(),
                "words": words,
                "tokens": sentence_tokens,
            }
        )

    return {
        "audio_path": str(audio_path),
        "language": info.language,
        "language_probability": round(float(info.language_probability), 4),
        "duration": round(float(info.duration), 2),
        "sentences": items,
        "words": all_words,
        "tokens": all_tokens,
    }


def re_split_numbers(text):
    return re.split(r"(\d+)", text)


def natural_sort_key(path):
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re_split_numbers(Path(path).name)
    ]


def find_mp4_paths(input_path):
    if input_path.is_file():
        if input_path.suffix.lower() != ".mp4":
            raise ValueError(f"Input file must be .mp4: {input_path}")
        return [input_path]

    if not input_path.is_dir():
        raise FileNotFoundError(input_path)

    mp4_paths = sorted(
        [path for path in input_path.iterdir() if path.is_file() and path.suffix.lower() == ".mp4"],
        key=natural_sort_key,
    )
    if not mp4_paths:
        raise FileNotFoundError(f"No MP4 files found in {input_path}")
    return mp4_paths


def process_video_asr(mp4_path, work_dir, model, args):
    print(f"\nProcessing {mp4_path}")

    source_wav = work_dir / f"{mp4_path.stem}_original.wav"
    speech_wav = work_dir / f"{mp4_path.stem}_speech.wav"
    background_wav = work_dir / f"{mp4_path.stem}_background.wav"
    demucs_out_dir = work_dir / "_demucs_tmp" / mp4_path.stem
    timeline_out = work_dir / f"asr_timeline_{mp4_path.stem}.json"

    try:
        extract_wav_from_mp4(mp4_path, source_wav, sample_rate=args.sample_rate)
        vocals_wav, no_vocals_wav = separate_vocals_with_demucs(source_wav, demucs_out_dir)
        shutil.copy2(vocals_wav, speech_wav)
        shutil.copy2(no_vocals_wav, background_wav)
    finally:
        if not args.keep_demucs and demucs_out_dir.exists():
            shutil.rmtree(demucs_out_dir)

    asr_result = transcribe_audio(
        model,
        speech_wav,
        language=args.language,
        beam_size=args.beam_size,
        vad_filter=not args.no_vad_filter,
        word_timestamps=not args.no_word_timestamps,
    )
    write_json(asr_result, timeline_out)

    for sentence in asr_result["sentences"]:
        print(f'[{sentence["start"]:.2f}s -> {sentence["end"]:.2f}s] {sentence["text"]}')

    print(f"saved {source_wav}")
    print(f"saved {speech_wav}")
    print(f"saved {background_wav}")
    print(f"saved {timeline_out}")
    if args.keep_demucs:
        print(f"kept {demucs_out_dir}")


def extract_asr_timelines_step(videos_dir, asr_dir, asr_model, args):
    from faster_whisper import WhisperModel

    require_command("ffmpeg")
    require_command("demucs")

    mp4_paths = find_mp4_paths(videos_dir)
    asr_dir.mkdir(parents=True, exist_ok=True)

    model = WhisperModel(
        str(asr_model),
        device=args.device,
        compute_type=args.compute_type,
    )

    for mp4_path in mp4_paths:
        process_video_asr(mp4_path, asr_dir, model, args)

    print(f"\nProcessed {len(mp4_paths)} video(s). Output directory: {asr_dir}")


def group_dialogues_by_storyboard(dialogues):
    grouped = {}
    for row in dialogues:
        storyboard_id = row.get("storyboard_id")
        if storyboard_id is None:
            continue
        grouped.setdefault(int(storyboard_id), []).append(row)

    for rows in grouped.values():
        rows.sort(key=lambda item: item.get("dialogue_index", 0))

    return grouped


def storyboard_id_from_asr_path(path):
    match = re.search(r"asr_timeline_(\d+)\.json$", Path(path).name)
    if not match:
        return None
    return int(match.group(1))


def build_asr_path_map(asr_glob):
    paths = sorted(Path(path).resolve() for path in glob.glob(asr_glob))
    asr_paths = {}
    for path in paths:
        storyboard_id = storyboard_id_from_asr_path(path)
        if storyboard_id is None:
            continue
        asr_paths[storyboard_id] = path
    return asr_paths


def build_alignment_prompt(storyboard_id, dialogue_rows, asr_data):
    compact_dialogues = [
        {
            "dialogue_index": row.get("dialogue_index"),
            "speaker_name": row.get("speaker_name"),
            "dialogue": row.get("dialogue", ""),
        }
        for row in dialogue_rows
    ]
    sentences = asr_data.get("sentences", [])
    words = asr_data.get("words", [])
    tokens = asr_data.get("tokens", [])

    return f"""你是对白时间轴对齐助手。请根据正确对白列表 dialogues、ASR sentences、ASR words 和 ASR tokens，为每句对白找到音频中的 start 和 end。

重要规则：
1. dialogues 是绝对正确的，不能新增、删除、拆分、合并或改写其中任何对白。
2. ASR sentences 可能有噪声、错字、漏标点、空格变化、同音字错误，不能用 ASR 文本覆盖 dialogues。
3. 优先使用 ASR tokens 中已有的 start/end 作为时间依据。ASR tokens 是从 word 时间戳细分出的字/标点级时间轴。
4. 如果一个 ASR sentence 合并了两个人的对白，例如“房租, 多少?”，必须用 ASR tokens 把它拆开：第一句对白取“房租”对应 tokens 的起止时间，第二句对白取“多少？”对应 tokens 的起止时间，不能让两句对白使用完全相同的 start/end。
5. 只有当 ASR tokens 缺失或明显无法匹配时，才退回使用 ASR words；再不行才使用 ASR sentences 的 start/end。
6. 一句正确对白可能对应一个或多个连续 ASR token；如果对应多个，start 取第一个 token 的 start，end 取最后一个 token 的 end。
7. 如果 ASR 中有多余噪声，忽略它。
8. 如果找不到合理匹配，start 和 end 填 null。
9. 同一个镜头内，对白顺序必须和 dialogues 的 dialogue_index 顺序一致，时间段也必须按顺序排列，不能重叠。

请严格只输出 JSON 数组，不要输出解释。数组元素格式：
[
  {{
    "storyboard_id": {storyboard_id},
    "dialogue_index": 1,
    "start": 0.0,
    "end": 1.5,
    "matched_asr_indices": [1],
    "matched_asr_word_indices": [1, 2],
    "matched_asr_token_indices": [1, 2, 3]
  }}
]

storyboard_id:
{storyboard_id}

dialogues:
{json.dumps(compact_dialogues, ensure_ascii=False, indent=2)}

asr_sentences:
{json.dumps(sentences, ensure_ascii=False, indent=2)}

asr_words:
{json.dumps(words, ensure_ascii=False, indent=2)}

asr_tokens:
{json.dumps(tokens, ensure_ascii=False, indent=2)}
"""


def align_storyboard_with_llm(storyboard_id, dialogue_rows, asr_data, model):
    prompt = build_alignment_prompt(storyboard_id, dialogue_rows, asr_data)
    response = llm_generate(prompt, model)
    if not response:
        raise RuntimeError(f"LLM request failed for storyboard {storyboard_id}")

    data = extract_json_from_response(response)
    if isinstance(data, dict):
        data = data.get("alignments") or data.get("items") or data.get("result")
    if not isinstance(data, list):
        raise ValueError(f"LLM response for storyboard {storyboard_id} is not a list")

    alignments = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        dialogue_index = item.get("dialogue_index")
        if dialogue_index is None:
            continue
        alignments[int(dialogue_index)] = {
            "start": item.get("start"),
            "end": item.get("end"),
            "matched_asr_indices": item.get("matched_asr_indices", []),
            "matched_asr_word_indices": item.get("matched_asr_word_indices", []),
            "matched_asr_token_indices": item.get("matched_asr_token_indices", [])
        }

    return alignments


def attach_dialogue_times(dialogues, asr_paths, model, strict_missing_asr=False):
    grouped = group_dialogues_by_storyboard(dialogues)
    all_alignments = {}

    for storyboard_id, dialogue_rows in sorted(grouped.items()):
        asr_path = asr_paths.get(storyboard_id)
        if asr_path is None or not asr_path.exists():
            if strict_missing_asr:
                raise FileNotFoundError(f"ASR timeline not found for storyboard {storyboard_id}")
            all_alignments[storyboard_id] = {}
            continue

        asr_data = load_json(asr_path)
        all_alignments[storyboard_id] = align_storyboard_with_llm(
            storyboard_id,
            dialogue_rows,
            asr_data,
            model,
        )

    output = []
    for row in dialogues:
        item = dict(row)
        storyboard_id = item.get("storyboard_id")
        dialogue_index = item.get("dialogue_index")
        alignment = {}
        if storyboard_id is not None and dialogue_index is not None:
            alignment = all_alignments.get(int(storyboard_id), {}).get(int(dialogue_index), {})

        item["start"] = alignment.get("start")
        item["end"] = alignment.get("end")
        item["matched_asr_indices"] = alignment.get("matched_asr_indices", [])
        item["matched_asr_word_indices"] = alignment.get("matched_asr_word_indices", [])
        item["matched_asr_token_indices"] = alignment.get("matched_asr_token_indices", [])
        output.append(item)

    return output


def align_dialogue_times_step(dialogues_path, asr_dir, output_path, model, strict_missing_asr=False):
    dialogues = load_json(dialogues_path)
    if not isinstance(dialogues, list):
        raise ValueError(f"{dialogues_path} must contain a JSON array")

    asr_paths = build_asr_path_map(str(asr_dir / "asr_timeline_*.json"))
    rows = attach_dialogue_times(
        dialogues,
        asr_paths,
        model,
        strict_missing_asr=strict_missing_asr,
    )
    write_json(rows, output_path)
    print(f"saved {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the voice dialogue timing pipeline for one chapter directory."
    )
    parser.add_argument(
        "chapter_dir",
        type=Path,
        help="Chapter directory relative to the project root, for example output/chapter_01.",
    )
    parser.add_argument(
        "--voice-state",
        type=Path,
        default=None,
        help="Character voice assignment JSON. Defaults to <chapter_dir>/global_character_voice.json.",
    )
    parser.add_argument("--model", default="gemini-3.1-pro-preview", help="Glink model name")
    parser.add_argument(
        "--asr-model",
        default=None,
        help="faster-whisper model path/name. Defaults to voice/faster-whisper-large.",
    )
    parser.add_argument("--device", default="cpu", help="faster-whisper device")
    parser.add_argument("--compute-type", default="int8", help="faster-whisper compute type")
    parser.add_argument("--sample-rate", type=int, default=44100, help="Extracted WAV sample rate")
    parser.add_argument("--language", default="zh", help="Transcription language")
    parser.add_argument("--beam-size", type=int, default=5, help="ASR beam size")
    parser.add_argument("--no-vad-filter", action="store_true", help="Disable faster-whisper built-in VAD filter")
    parser.add_argument(
        "--no-word-timestamps",
        action="store_true",
        help="Disable faster-whisper word/token timestamps in ASR timeline JSON.",
    )
    parser.add_argument("--skip-dialogues", action="store_true", help="Skip extracting dialogues.json")
    parser.add_argument("--skip-asr", action="store_true", help="Skip ASR timeline generation")
    parser.add_argument("--skip-align", action="store_true", help="Skip dialogue time alignment")
    parser.add_argument(
        "--keep-demucs",
        action="store_true",
        help="Keep Demucs intermediate output under chapter asr_outputs/_demucs_tmp.",
    )
    parser.add_argument(
        "--no-llm-dialogues",
        action="store_true",
        help="Deprecated; dialogue extraction always uses LLM.",
    )
    parser.add_argument(
        "--strict-missing-asr",
        action="store_true",
        help="Fail if any storyboard ASR timeline is missing during alignment.",
    )
    parser.add_argument(
        "--include-screen-text",
        action="store_true",
        help="Also include quoted on-screen text that is not spoken by a character.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned steps without running them")
    return parser.parse_args()


def print_step(title):
    print(f"\n== {title} ==")


def main():
    args = parse_args()
    chapter_dir = resolve_project_path(args.chapter_dir)
    voice_state = resolve_project_path(args.voice_state) if args.voice_state else chapter_dir / "global_character_voice.json"
    asr_model = resolve_model_path_or_name(args.asr_model)

    clips_path = chapter_dir / "video_clips.json"
    characters_path = chapter_dir / "characters.json"
    videos_dir = chapter_dir / "videos"
    asr_dir = chapter_dir / "asr_outputs"
    dialogues_path = chapter_dir / "dialogues.json"
    output_path = chapter_dir / "dialogues_with_times.json"

    require_dir(chapter_dir, "chapter directory")
    require_file(clips_path, "video_clips.json")
    require_file(characters_path, "characters.json")
    require_dir(videos_dir, "videos directory")

    if not args.skip_dialogues:
        print_step("Extract dialogues")
        if args.dry_run:
            print(f"would read {clips_path}")
            print(f"would read {characters_path}")
            print(f"would write {dialogues_path}")
            print(f"would write {voice_state}")
        else:
            extract_dialogues_step(
                clips_path,
                characters_path,
                dialogues_path,
                voice_state,
                args.model,
                include_screen_text=args.include_screen_text,
            )

    if not args.dry_run or args.skip_dialogues:
        require_file(dialogues_path, "dialogues.json")

    if not args.skip_asr:
        print_step("Extract ASR timelines")
        if args.dry_run:
            print(f"would read MP4 files from {videos_dir}")
            print(f"would write ASR outputs to {asr_dir}")
            print(f"would use ASR model {asr_model}")
        else:
            extract_asr_timelines_step(videos_dir, asr_dir, asr_model, args)

    if not args.skip_align:
        print_step("Align dialogue times")
        if args.dry_run:
            print(f"would read {dialogues_path}")
            print(f"would read ASR timelines from {asr_dir}")
            print(f"would write {output_path}")
        else:
            align_dialogue_times_step(
                dialogues_path,
                asr_dir,
                output_path,
                args.model,
                strict_missing_asr=args.strict_missing_asr,
            )

    print(f"\nDone. Final output: {output_path}")


if __name__ == "__main__":
    main()
