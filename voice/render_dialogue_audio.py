import argparse
import json
import os
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml
from scipy import signal

VOICE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = VOICE_DIR.parent
COSYVOICE2_MODEL_DIR = "pretrained_models/CosyVoice2-0.5B"
DEFAULT_MODEL = "cosyvoice2"
DEFAULT_PROMPT_PREFIX = ""
TTS_MIX_ADVANCE_SECONDS = 0.5
DEFAULT_PROMPT_TEXT = DEFAULT_PROMPT_PREFIX


def load_project_config():
    config_path = PROJECT_ROOT / "config.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def cosyvoice_config():
    return (load_project_config().get("voice") or {}).get("cosyvoice") or {}


def resolve_cosyvoice_model_dir(model_dir=None):
    value = model_dir or os.environ.get("COSYVOICE_MODEL_DIR") or cosyvoice_config().get("model_dir") or COSYVOICE2_MODEL_DIR
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path)


def register_cosyvoice_model(load_vllm=True):
    if not load_vllm:
        return
    from vllm import ModelRegistry
    from cosyvoice.vllm.cosyvoice2 import CosyVoice2ForCausalLM

    ModelRegistry.register_model("CosyVoice2ForCausalLM", CosyVoice2ForCausalLM)


def load_cosyvoice(model_dir=None):
    config = cosyvoice_config()
    load_vllm = bool(config.get("load_vllm", True))
    register_cosyvoice_model(load_vllm=load_vllm)

    from cosyvoice.cli.cosyvoice import AutoModel

    return AutoModel(
        model_dir=resolve_cosyvoice_model_dir(model_dir),
        load_jit=bool(config.get("load_jit", True)),
        load_trt=bool(config.get("load_trt", False)),
        load_vllm=load_vllm,
        fp16=bool(config.get("fp16", True)),
    )


def clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))


def clone_voice(cosyvoice, text, prompt_wav, prompt_text=DEFAULT_PROMPT_TEXT, seed=0, speed=1.0):
    """Generate one zero-shot cloned speech waveform from a prompt wav."""
    if seed is not None:
        from cosyvoice.utils.common import set_all_random_seed

        set_all_random_seed(seed)

    chunks = []
    for result in cosyvoice.inference_zero_shot(
        text,
        prompt_text,
        prompt_wav,
        stream=False,
        speed=speed,
    ):
        wav = result["tts_speech"].detach().cpu().float()
        if wav.dim() == 2 and wav.shape[0] < wav.shape[1]:
            wav = wav.transpose(0, 1)
        chunks.append(wav.numpy())

    if not chunks:
        raise RuntimeError(f"TTS generated no audio for text: {text}")

    if len(chunks) == 1:
        return chunks[0], int(cosyvoice.sample_rate)

    return np.concatenate(chunks, axis=0), int(cosyvoice.sample_rate)


def clone_voice_to_file(cosyvoice, text, prompt_wav, output_wav,
                        prompt_text=DEFAULT_PROMPT_TEXT, seed=0, speed=1.0):
    wav, sample_rate = clone_voice(cosyvoice, text, prompt_wav, prompt_text, seed, speed=speed)
    os.makedirs(os.path.dirname(output_wav) or ".", exist_ok=True)
    sf.write(output_wav, wav, sample_rate)
    return output_wav


def build_atempo_filter(tempo):
    """Build an ffmpeg atempo filter chain while keeping each segment valid."""
    factors = []
    remaining = tempo
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join(f"atempo={factor:.6f}" for factor in factors)


def find_ffmpeg_bin():
    ffmpeg_bin = os.environ.get("FFMPEG_BIN")
    if ffmpeg_bin:
        return ffmpeg_bin

    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as exc:
        raise RuntimeError(
            "ffmpeg command not found. Install it with `pip install imageio-ffmpeg`, "
            "or set FFMPEG_BIN to the ffmpeg executable path."
        ) from exc


def ffmpeg_atempo(input_wav, output_wav, tempo):
    if tempo == 1.0:
        os.replace(input_wav, output_wav)
        return

    tmp_output = f"{output_wav}.tmp.wav"
    cmd = [
        find_ffmpeg_bin(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        input_wav,
        "-filter:a",
        build_atempo_filter(tempo),
        tmp_output,
    ]
    subprocess.run(cmd, check=True)
    os.replace(tmp_output, output_wav)


def clone_voice_to_file_with_duration_fit(cosyvoice, text, prompt_wav, output_wav,
                                          target_duration, prompt_text=DEFAULT_PROMPT_TEXT,
                                          seed=0, seed_candidates=5,
                                          min_tempo=0.75, max_tempo=1.35):
    os.makedirs(os.path.dirname(output_wav) or ".", exist_ok=True)

    best = None
    candidate_count = max(1, seed_candidates)
    for offset in range(candidate_count):
        candidate_seed = None if seed is None else seed + offset
        wav, sample_rate = clone_voice(
            cosyvoice,
            text,
            prompt_wav,
            prompt_text=prompt_text,
            seed=candidate_seed,
            speed=1.0,
        )
        duration = wav.shape[0] / sample_rate
        diff = abs(duration - target_duration)
        print(
            f"[tts-candidate] seed={candidate_seed} target={target_duration:.3f}s "
            f"actual={duration:.3f}s diff={diff:.3f}s"
        )
        if best is None or diff < best["diff"]:
            best = {
                "seed": candidate_seed,
                "wav": wav,
                "sample_rate": sample_rate,
                "duration": duration,
                "diff": diff,
            }

    raw_path = f"{output_wav}.raw.wav"
    sf.write(raw_path, best["wav"], best["sample_rate"])

    requested_tempo = best["duration"] / target_duration
    tempo = clamp(requested_tempo, min_tempo, max_tempo)
    print(
        f"[tts-fit] selected_seed={best['seed']} target={target_duration:.3f}s "
        f"actual={best['duration']:.3f}s requested_atempo={requested_tempo:.3f} "
        f"atempo={tempo:.3f}"
    )
    try:
        ffmpeg_atempo(raw_path, output_wav, tempo)
    finally:
        if os.path.exists(raw_path):
            os.remove(raw_path)
    return output_wav


def normalize_voice_id(value):
    return re.sub(r"[\s_\-]+", "", str(value or "")).lower()


def load_json_if_exists(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_under_chapter(chapter_dir, value, default_name):
    if value is None:
        return chapter_dir / default_name
    path = Path(value)
    if path.is_absolute():
        return path
    return chapter_dir / path


def default_voice_template_dir(chapter_dir):
    return chapter_dir / "voice_template"


def build_voice_template_map(template_dir):
    voice_map = {}
    for wav_path in template_dir.glob("*.wav"):
        voice_map[wav_path.stem] = wav_path
        voice_map[normalize_voice_id(wav_path.stem)] = wav_path
    return voice_map


def build_voice_alias_map(voice_state_path):
    state = load_json_if_exists(voice_state_path, default={}) or {}
    aliases = {}
    for record in (state.get("characters") or {}).values():
        voice_id = record.get("voice_id")
        if not voice_id:
            continue
        values = {
            voice_id,
            record.get("voice_category"),
            record.get("role_slot"),
        }
        for value in values:
            if value:
                aliases[value] = voice_id
                aliases[normalize_voice_id(value)] = voice_id
    return aliases


def load_voice_prompt_texts(path):
    if not path.exists():
        print(f"[warn] missing voice prompt json: {path}")
        return {}

    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f)

    prompt_map = {}
    for item in items:
        voice_id = item.get("voice_id")
        voice_text = item.get("voice_text")
        if not voice_id or not voice_text:
            continue
        prompt_map[voice_id] = voice_text
        prompt_map[normalize_voice_id(voice_id)] = voice_text
    return prompt_map


def build_prompt_text(voice_id, prompt_map, override_prompt_text=None, prompt_prefix=DEFAULT_PROMPT_PREFIX, fallback_voice_id=None):
    if override_prompt_text is not None:
        return override_prompt_text

    voice_text = None
    for candidate in (voice_id, fallback_voice_id):
        if not candidate:
            continue
        voice_text = prompt_map.get(candidate) or prompt_map.get(normalize_voice_id(candidate))
        if voice_text:
            break
    if voice_text:
        return f"{prompt_prefix}{voice_text}"

    print(f"[warn] no prompt voice_text for voice_id={voice_id!r}; using prompt prefix only")
    return prompt_prefix


def unique_candidates(values):
    candidates = []
    seen = set()
    for value in values:
        if not value:
            continue
        key = normalize_voice_id(value)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(value)
    return candidates


def parse_voice_slot_age(voice_id):
    text = str(voice_id or "").strip()
    role_match = re.search(r"(男主|女主|配角[1-6])", text)
    age_match = re.search(r"(幼年|少年|青年|中年|老年)", text)
    if not role_match:
        return None, None

    role_slot = role_match.group(1)
    age_stage = age_match.group(1) if age_match else None
    if age_stage == "青年":
        age_stage = "中年"
    return role_slot, age_stage


def legacy_voice_candidates(voice_id):
    text = str(voice_id or "").strip()
    role_slot, age_stage = parse_voice_slot_age(text)
    candidates = []

    if role_slot and age_stage:
        base = f"{role_slot}_{age_stage}"
        candidates.extend([
            base,
            f"{base}1",
            f"{base}_1",
            f"{base}-1",
        ])
    elif role_slot:
        candidates.extend([
            role_slot,
            f"{role_slot}1",
            f"{role_slot}_1",
            f"{role_slot}-1",
        ])

    if role_slot == "男主":
        candidates.extend(["男主_1", "男配_1"])
    elif role_slot == "女主":
        candidates.extend(["女主_1", "女配_1"])
    elif role_slot and role_slot.startswith("配角"):
        candidates.extend(["男配_1", "女配_1", "男配_2", "女配_2"])

    if age_stage == "老年" or "老年" in text:
        candidates.extend(["老头_1", "老太_1"])

    return unique_candidates(candidates)


def find_voice_template(voice_id, voice_map, alias_map=None):
    if not voice_id:
        return None
    alias_map = alias_map or {}
    candidates = [
        voice_id,
        alias_map.get(voice_id),
        alias_map.get(normalize_voice_id(voice_id)),
        *legacy_voice_candidates(voice_id),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        match = voice_map.get(candidate) or voice_map.get(normalize_voice_id(candidate))
        if match:
            return match
    return None


def ensure_2d(audio):
    if audio.ndim == 1:
        return audio[:, None]
    return audio


def match_channels(audio, channels):
    audio = ensure_2d(audio)
    if audio.shape[1] == channels:
        return audio
    if audio.shape[1] == 1 and channels == 2:
        return np.repeat(audio, 2, axis=1)
    if audio.shape[1] > channels:
        return audio[:, :channels]
    pad = np.repeat(audio[:, -1:], channels - audio.shape[1], axis=1)
    return np.concatenate([audio, pad], axis=1)


def resample_audio(audio, src_sr, dst_sr):
    if src_sr == dst_sr:
        return audio
    gcd = np.gcd(src_sr, dst_sr)
    up = dst_sr // gcd
    down = src_sr // gcd
    target_len = max(1, round(audio.shape[0] * dst_sr / src_sr))
    return signal.resample_poly(audio, up, down, axis=0)[:target_len]


def mix_at(base, overlay, start_sample):
    if start_sample >= base.shape[0]:
        return base

    end_sample = min(base.shape[0], start_sample + overlay.shape[0])
    use_len = end_sample - start_sample
    base[start_sample:end_sample] += overlay[:use_len]
    return base


def peak_normalize(audio, peak=0.98):
    current_peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if current_peak > peak:
        audio = audio * (peak / current_peak)
    return audio


def load_dialogues(path):
    with open(path, "r", encoding="utf-8") as f:
        dialogues = json.load(f)
    return [
        d for d in dialogues
        if d.get("dialogue") and d.get("voice_id") and d.get("start") is not None and d.get("end") is not None
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Render dialogue TTS from a extract_diaglogues_time.py chapter directory and mix it with storyboard background wavs."
    )
    parser.add_argument("chapter_dir", nargs="?", default=".", help="Chapter output directory, e.g. output/chapter_01")
    parser.add_argument("--dialogues", default=None, help="Defaults to <chapter_dir>/dialogues_with_times.json")
    parser.add_argument("--voice-state", default=None, help="Defaults to <chapter_dir>/global_character_voice.json")
    parser.add_argument("--voice-template-dir", default=None,
                        help="Defaults to <chapter_dir>/voice_template. Configure it manually; use voice/chapter_01/voice_template as a reference.")
    parser.add_argument("--background-dir", default=None, help="Defaults to <chapter_dir>/asr_outputs")
    parser.add_argument("--output-dir", default=None, help="Defaults to <chapter_dir>/mixed_outputs")
    parser.add_argument("--tts-cache-dir", default=None, help="Defaults to <chapter_dir>/tts_outputs")
    parser.add_argument("--prompt-text", default=None,
                        help="Override full prompt text. By default the prompt suffix is read from voice_template/dialogues.json.")
    parser.add_argument("--model-dir", default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--seed-candidates", type=int, default=5,
                        help="Generate this many consecutive seed candidates and keep the one closest to the target duration.")
    parser.add_argument("--atempo-min", type=float, default=0.75,
                        help="Minimum ffmpeg atempo value used when fitting generated speech to the target duration.")
    parser.add_argument("--atempo-max", type=float, default=1.35,
                        help="Maximum ffmpeg atempo value used when fitting generated speech to the target duration.")
    parser.add_argument("--dialogue-gain", type=float, default=1.0)
    parser.add_argument("--background-gain", type=float, default=1.0)
    parser.add_argument("--no-fit-duration", action="store_true",
                        help="Do not use seed search and ffmpeg atempo to fit TTS to each start/end slot.")
    parser.add_argument("--overwrite-tts", action="store_true")
    args = parser.parse_args()
    if args.atempo_min <= 0 or args.atempo_max <= 0:
        parser.error("--atempo-min and --atempo-max must be positive.")
    if args.atempo_min > args.atempo_max:
        parser.error("--atempo-min must be less than or equal to --atempo-max.")

    chapter_dir = Path(args.chapter_dir).resolve()
    dialogues_path = resolve_under_chapter(chapter_dir, args.dialogues, "dialogues_with_times.json")
    voice_state_path = resolve_under_chapter(chapter_dir, args.voice_state, "global_character_voice.json")
    template_dir = Path(args.voice_template_dir).resolve() if args.voice_template_dir else default_voice_template_dir(chapter_dir)
    background_dir = resolve_under_chapter(chapter_dir, args.background_dir, "asr_outputs")
    output_dir = resolve_under_chapter(chapter_dir, args.output_dir, "mixed_outputs")
    tts_cache_dir = resolve_under_chapter(chapter_dir, args.tts_cache_dir, "tts_outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    tts_cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"[config] chapter_dir={chapter_dir}")
    print(f"[config] dialogues={dialogues_path}")
    print(f"[config] voice_state={voice_state_path}")
    print(f"[config] voice_template_dir={template_dir}")
    print(f"[config] background_dir={background_dir}")
    print(f"[config] output_dir={output_dir}")
    print(f"[config] tts_cache_dir={tts_cache_dir}")

    if not template_dir.is_dir():
        raise FileNotFoundError(
            f"voice template directory not found: {template_dir}. "
            "Configure <chapter_dir>/voice_template manually; use voice/chapter_01/voice_template as a reference."
        )

    dialogues = load_dialogues(dialogues_path)
    voice_map = build_voice_template_map(template_dir)
    alias_map = build_voice_alias_map(voice_state_path)
    prompt_map = load_voice_prompt_texts(template_dir / "dialogues.json")
    grouped = defaultdict(list)
    for item in dialogues:
        grouped[item["storyboard_id"]].append(item)

    cosyvoice = load_cosyvoice(args.model_dir)
    prompt_prefix = DEFAULT_PROMPT_PREFIX

    for storyboard_id, items in sorted(grouped.items()):
        background_path = background_dir / f"{storyboard_id}_background.wav"
        if not background_path.exists():
            print(f"[skip] missing background: {background_path}")
            continue

        background, bg_sr = sf.read(background_path, dtype="float32", always_2d=True)
        mix = background * args.background_gain

        for item in sorted(items, key=lambda x: (x["start"], x.get("dialogue_index", 0))):
            voice_template = find_voice_template(item.get("voice_id"), voice_map, alias_map)
            if voice_template is None:
                print(f"[skip] no voice template for voice_id={item.get('voice_id')!r}")
                continue

            cache_name = f"{storyboard_id}_{item.get('dialogue_index', 0)}_{item['voice_id']}.wav"
            tts_path = tts_cache_dir / cache_name
            start = float(item["start"])
            end = float(item["end"])
            if end <= start:
                print(f"[skip] invalid time range: storyboard={storyboard_id}, dialogue={item.get('dialogue_index')}")
                continue
            target_duration = end - start

            if args.overwrite_tts or not tts_path.exists():
                prompt_text = build_prompt_text(
                    item.get("voice_id"),
                    prompt_map,
                    args.prompt_text,
                    prompt_prefix=prompt_prefix,
                    fallback_voice_id=voice_template.stem,
                )
                if args.no_fit_duration:
                    clone_voice_to_file(
                        cosyvoice,
                        item["dialogue"],
                        str(voice_template),
                        str(tts_path),
                        prompt_text=prompt_text,
                        seed=args.seed,
                        speed=1.0,
                    )
                else:
                    clone_voice_to_file_with_duration_fit(
                        cosyvoice,
                        item["dialogue"],
                        str(voice_template),
                        str(tts_path),
                        target_duration,
                        prompt_text=prompt_text,
                        seed=args.seed,
                        seed_candidates=args.seed_candidates,
                        min_tempo=args.atempo_min,
                        max_tempo=args.atempo_max,
                    )

            speech, speech_sr = sf.read(tts_path, dtype="float32", always_2d=True)
            speech = resample_audio(speech, speech_sr, bg_sr)
            speech = match_channels(speech, mix.shape[1])

            mix_start = 0.0 if start <= 0 else max(0.0, start - TTS_MIX_ADVANCE_SECONDS)
            start_sample = round(mix_start * bg_sr)
            mix_at(mix, speech * args.dialogue_gain, start_sample)
            print(f"[mix] storyboard={storyboard_id} dialogue={item.get('dialogue_index')} voice={voice_template.name}")

        output_path = output_dir / f"{storyboard_id}_mixed.wav"
        sf.write(output_path, peak_normalize(mix), bg_sr)
        print(f"[write] {output_path}")


if __name__ == "__main__":
    main()
