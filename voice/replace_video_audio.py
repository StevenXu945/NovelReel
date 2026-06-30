import argparse
import shutil
import subprocess
from pathlib import Path


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}


def resolve_under_chapter(chapter_dir, value, default_name):
    if value is None:
        return chapter_dir / default_name
    path = Path(value)
    if path.is_absolute():
        return path
    return chapter_dir / path


def find_bin(name):
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"`{name}` not found. Please install ffmpeg first.")
    return path


def build_audio_map(audio_dir):
    audio_map = {}
    for audio_path in sorted(audio_dir.iterdir()):
        if not audio_path.is_file() or audio_path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        audio_map.setdefault(audio_path.stem, audio_path)
    return audio_map


def get_video_duration(ffprobe_bin, video_path):
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return float(result.stdout.strip())


def replace_audio(ffmpeg_bin, ffprobe_bin, video_path, audio_path, output_path):
    duration = get_video_duration(ffprobe_bin, video_path)
    cmd = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-t",
        f"{duration:.6f}",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)


def copy_video(video_path, output_path):
    shutil.copy2(video_path, output_path)


def process_videos(video_dir, audio_dir, output_dir):
    if not video_dir.exists():
        raise FileNotFoundError(f"Video directory not found: {video_dir}")
    if not audio_dir.exists():
        raise FileNotFoundError(f"Audio directory not found: {audio_dir}")

    ffmpeg_bin = find_bin("ffmpeg")
    ffprobe_bin = find_bin("ffprobe")
    audio_map = build_audio_map(audio_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    replaced = 0
    copied = 0
    for video_path in sorted(video_dir.iterdir()):
        if not video_path.is_file() or video_path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue

        output_path = output_dir / video_path.name
        audio_path = audio_map.get(video_path.stem)
        if audio_path:
            print(f"[replace] {video_path.name} <- {audio_path.name}")
            replace_audio(ffmpeg_bin, ffprobe_bin, video_path, audio_path, output_path)
            replaced += 1
        else:
            print(f"[copy]    {video_path.name} (no matching audio)")
            copy_video(video_path, output_path)
            copied += 1

    print(f"Done. Replaced audio for {replaced} video(s), copied {copied} video(s).")
    print(f"Output directory: {output_dir}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Replace videos' audio using mixed audio files from a chapter output directory."
    )
    parser.add_argument("chapter_dir", nargs="?", default=".", type=Path, help="Chapter output directory, e.g. output/chapter_01")
    parser.add_argument("--video-dir", default=None, type=Path, help="Defaults to <chapter_dir>/videos")
    parser.add_argument("--audio-dir", default=None, type=Path, help="Defaults to <chapter_dir>/mixed_outputs")
    parser.add_argument("--output-dir", default=None, type=Path, help="Defaults to <chapter_dir>/videos_with_mixed_audio")
    return parser.parse_args()


def main():
    args = parse_args()
    chapter_dir = args.chapter_dir.resolve()
    video_dir = resolve_under_chapter(chapter_dir, args.video_dir, "videos")
    audio_dir = resolve_under_chapter(chapter_dir, args.audio_dir, "mixed_outputs")
    output_dir = resolve_under_chapter(chapter_dir, args.output_dir, "videos_with_mixed_audio")

    print(f"[config] chapter_dir={chapter_dir}")
    print(f"[config] video_dir={video_dir}")
    print(f"[config] audio_dir={audio_dir}")
    print(f"[config] output_dir={output_dir}")

    process_videos(video_dir, audio_dir, output_dir)


if __name__ == "__main__":
    main()