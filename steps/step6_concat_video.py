import os
import subprocess


class VideoConcatenator:
    """步骤6：将所有视频片段拼接为完整短剧"""

    def __init__(self, output_dir="output"):
        self.output_dir = output_dir
        self.final_path = os.path.join(output_dir, "final_drama.mp4")

    def run(self, video_clips):
        print("\n[步骤6] 拼接最终短剧...")
        clip_paths = [self._resolve_clip_path(vc) for vc in video_clips]

        # 检查实际存在的视频文件
        existing = [p for p in clip_paths if os.path.exists(p)]
        if not existing:
            print("  没有可拼接的视频片段（视频生成步骤尚未实现）")
            return self.final_path

        list_file = self.final_path + ".filelist.txt"
        with open(list_file, "w") as f:
            for path in existing:
                f.write(f"file '{os.path.abspath(path)}'\n")

        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", self.final_path],
            check=True,
        )
        os.remove(list_file)

        print(f"  最终短剧已生成: {self.final_path}")
        return self.final_path

    def _resolve_clip_path(self, video_clip):
        clip_path = video_clip.get("clip_path", "")
        if clip_path and os.path.exists(clip_path):
            return clip_path

        storyboard_id = video_clip.get("storyboard_id")
        if storyboard_id is None:
            return clip_path

        legacy_path = os.path.join(self.output_dir, "videos", f"{storyboard_id}.mp4")
        if os.path.exists(legacy_path):
            return legacy_path
        return clip_path


if __name__ == "__main__":
    import argparse
    import json

    from core.project_paths import resolve_chapter_output_dir, resolve_project_path

    parser = argparse.ArgumentParser(description="步骤6：拼接最终短剧")
    parser.add_argument("--output-dir", default="output", help="当前章节输出目录")
    parser.add_argument("--chapter-name", default="chapter_01", help="章节文件夹名；留空则直接使用 output-dir")
    args = parser.parse_args()

    output_dir = resolve_project_path(args.output_dir)
    current_output_dir = resolve_chapter_output_dir(output_dir, args.chapter_name)
    video_clips_path = os.path.join(current_output_dir, "video_clips.json")
    with open(video_clips_path, "r", encoding="utf-8") as f:
        clips = json.load(f)
    VideoConcatenator(output_dir=current_output_dir).run(clips)
