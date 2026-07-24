import json
import os
import re
import sys
from contextlib import redirect_stdout


class TeeOutput:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


class VideoClipGenerator:
    """步骤5：根据环境图 + 角色图 + 分镜描述生成视频片段（Mock版本）

    video_prompt 中的"图N"引用规则：
    - 图1 = 环境图
    - 图2, 图3, ... = 按 character_ids 顺序的角色图
    - 角色图之后继续按 prop_ids 顺序追加道具图

    默认只生成视频片段索引和视频生成描述；传入 use_video_generator=True 时才调用视频生成接口。
    """

    MOTION_DESC_CONSTRAINT = "要求：不要有背景音乐；画面上禁止出现任何文字、字幕、标题、标识或水印。"
    VISUAL_TEXT_PATTERNS = (
        re.compile(r"画面[^，。；,]*(?:出现|浮现|显示|呈现)[^，。；,]*(?:字幕|文字|标题|汉字)[^，。；,]*[，。；,]?"),
        re.compile(r"(?:字幕|文字|标题|汉字)[^，。；,]*(?:出现|浮现|显示|呈现)[^，。；,]*[，。；,]?"),
    )

    def __init__(self, output_dir="output"):
        self.output_dir = output_dir
        self.videos_dir = os.path.join(output_dir, "videos")
        self.save_path = os.path.join(output_dir, "video_clips.json")
        self.print_log_path = os.path.join(output_dir, "step5_prints.txt")

    def _get_env_image_for_storyboard(self, env_images, env_id):
        """获取分镜对应的环境图"""
        env_info = env_images.get(str(env_id), "")
        if isinstance(env_info, dict):
            return env_info.get("path", "")
        return env_info

    def _get_env_image_url_for_storyboard(self, env_images, env_id):
        env_info = env_images.get(str(env_id), "")
        if isinstance(env_info, dict):
            return env_info.get("image_url", "") or env_info.get("url", "")
        return ""

    def _load_asset_urls(self, filename, id_field):
        path = os.path.join(self.output_dir, filename)
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        urls = {}
        items = data.values() if isinstance(data, dict) else data
        for item in items:
            if not isinstance(item, dict):
                continue
            asset_id = item.get(id_field)
            image_url = item.get("image_url", "") or item.get("url", "")
            if asset_id is not None and image_url:
                urls[str(asset_id)] = image_url
        return urls

    def run(
        self,
        storyboards,
        env_images,
        style="动漫",
        use_video_generator=False,
        video_provider=None,
        print_log_path=None,
    ):
        print_log_path = print_log_path if print_log_path is not None else self.print_log_path
        if print_log_path:
            os.makedirs(os.path.dirname(print_log_path), exist_ok=True)
            with open(print_log_path, "w", encoding="utf-8") as log_file:
                with redirect_stdout(TeeOutput(sys.stdout, log_file)):
                    return self._run(
                        storyboards,
                        env_images,
                        style=style,
                        use_video_generator=use_video_generator,
                        video_provider=video_provider,
                    )

        return self._run(
            storyboards,
            env_images,
            style=style,
            use_video_generator=use_video_generator,
            video_provider=video_provider,
        )

    def _run(self, storyboards, env_images, style="写实", use_video_generator=False, video_provider=None):
        style = self._normalize_style(style)
        mode = "生成模式" if use_video_generator else "Mock模式"
        print(f"\n[步骤5] 生成视频片段（{mode}，风格: {style}）...")
        os.makedirs(self.videos_dir, exist_ok=True)

        video_generator = None
        if use_video_generator:
            from provider.video_generator import VideoGeneratorMulti

            video_generator = VideoGeneratorMulti(provider=video_provider)

        character_image_urls = self._load_asset_urls("character_images.json", "char_id")
        prop_image_urls = self._load_asset_urls("prop_images.json", "prop_id")
        video_clips = []

        for sb in storyboards:
            sb_id = sb["storyboard_id"]
            env_id = sb.get("environment_id")
            character_ids = sb.get("character_ids", [])
            prop_ids = sb.get("prop_ids", [])
            scene_desc = sb.get("video_prompt", "")
            rhythm = sb.get("rhythm", "")

            duration = sb.get("duration", 5)
            print(f"\n  ── 分镜 {sb_id} ({duration}秒) ──")

            # 构建参考图列表
            ref_images = []
            ref_image_urls = []
            img_idx = 1

            # 图1：环境图
            has_env_image = False
            env_path = self._get_env_image_for_storyboard(env_images, env_id)
            if env_path:
                ref_images.append((img_idx, os.path.basename(env_path)))
                env_image_url = self._get_env_image_url_for_storyboard(env_images, env_id)
                if env_image_url:
                    ref_image_urls.append(env_image_url)
                print(f"  图{img_idx}: {os.path.basename(env_path)}（环境图）")
                img_idx += 1
                has_env_image = True

            # 图2, 图3, ...：角色图
            for char_id in character_ids:
                char_img = f"character_{char_id}.png"
                char_path = os.path.join(self.output_dir, "characters", char_img)
                if os.path.exists(char_path):
                    ref_images.append((img_idx, char_img))
                    char_image_url = character_image_urls.get(str(char_id), "")
                    if char_image_url:
                        ref_image_urls.append(char_image_url)
                    print(f"  图{img_idx}: {char_img}（角色图）")
                    img_idx += 1

            # 角色图之后：道具图
            for prop_id in prop_ids:
                prop_img = f"prop_{prop_id}.png"
                prop_path = os.path.join(self.output_dir, "props", prop_img)
                if os.path.exists(prop_path):
                    ref_images.append((img_idx, prop_img))
                    prop_image_url = prop_image_urls.get(str(prop_id), "")
                    if prop_image_url:
                        ref_image_urls.append(prop_image_url)
                    print(f"  图{img_idx}: {prop_img}（道具图）")
                    img_idx += 1

            # 打印视频描述
            if sb.get("video_prompt"):
                motion_desc = self._build_video_prompt_desc(scene_desc, rhythm=rhythm)
            else:
                motion_desc = ""

            print(f"  视频描述: {motion_desc}")

            clip_path = os.path.join(self.videos_dir, f"{sb_id}.mp4")
            if use_video_generator:
                if not ref_image_urls:
                    print("  跳过生成: 没有可用的参考图 URL")
                elif os.path.exists(clip_path):
                    print(f"  视频已存在，跳过生成: {clip_path}")
                else:
                    video_generator.generate_video_clip(
                        prompt=motion_desc,
                        output_path=clip_path,
                        reference_image_urls=ref_image_urls,
                        duration=duration,
                        provider=video_provider,
                    )

            video_clips.append({
                "storyboard_id": sb_id,
                "clip_path": clip_path,
                "ref_images": [name for _, name in ref_images],
                "ref_image_urls": ref_image_urls,
                "motion_desc": motion_desc,
            })

        self.save(video_clips)
        return video_clips

    def _build_video_prompt_desc(self, video_prompt, rhythm=""):
        clean_prompt = self._remove_visual_text_instructions(video_prompt)
        rhythm_desc = self._format_rhythm_desc(rhythm)
        # return f"{rhythm_desc}{clean_prompt.rstrip('。')}。{self.MOTION_DESC_CONSTRAINT}"
        return f"{clean_prompt.rstrip('。')}。{self.MOTION_DESC_CONSTRAINT}"

    def _format_rhythm_desc(self, rhythm):
        rhythm = str(rhythm or "").strip()
        return f"镜头节奏：{rhythm}。" if rhythm else ""

    def _normalize_style(self, style):
        style = str(style or "").strip()
        return style or "写实"

    def _normalize_motion_desc(self, motion_desc):
        motion_desc = motion_desc.replace(f"，{self.MOTION_DESC_CONSTRAINT}", "")
        motion_desc = motion_desc.replace(f"。{self.MOTION_DESC_CONSTRAINT}", "")
        motion_desc = self._remove_visual_text_instructions(motion_desc)
        return f"{motion_desc.rstrip('。')}。{self.MOTION_DESC_CONSTRAINT}"

    def _remove_visual_text_instructions(self, text):
        """移除分镜里要求画面显示文字/字幕的正向指令。"""
        for pattern in self.VISUAL_TEXT_PATTERNS:
            text = pattern.sub("", text)
        return text

    def save(self, video_clips):
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(video_clips, f, ensure_ascii=False, indent=2)
        print(f"\n  视频片段索引已保存: {self.save_path}")

    def load(self):
        with open(self.save_path, "r", encoding="utf-8") as f:
            video_clips = json.load(f)

        changed = False
        for clip in video_clips:
            motion_desc = clip.get("motion_desc", "")
            normalized = self._normalize_motion_desc(motion_desc)
            if normalized != motion_desc:
                clip["motion_desc"] = normalized
                changed = True

        if changed:
            self.save(video_clips)

        return video_clips


if __name__ == "__main__":
    import argparse
    from core.project_paths import resolve_chapter_output_dir, resolve_project_path

    def load_json(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    parser = argparse.ArgumentParser(description="步骤5：生成视频片段索引")
    parser.add_argument("--output-dir", default="output", help="当前章节输出目录")
    parser.add_argument("--chapter-name", default="chapter_01", help="章节文件夹名；留空则直接使用 output-dir")
    parser.add_argument("--model", default="gemini-3.1-pro-preview", help="兼容参数；本步骤不直接调用 LLM")
    parser.add_argument("--not-first-chapter", action="store_true", help="兼容参数；本步骤读取当前章节资产")
    parser.add_argument("--use-video-generator", action="store_true", help="实际调用 provider.video_generator 生成视频；默认只打印并保存 JSON")
    parser.add_argument("--video-provider", choices=["ark", "zenmux"], default=None, help="视频生成后端；默认读取 config.yaml")
    args = parser.parse_args()

    output_dir = resolve_project_path(args.output_dir)
    current_output_dir = resolve_chapter_output_dir(output_dir, args.chapter_name)
    sbs = load_json(os.path.join(current_output_dir, "storyboards.json"))
    env_imgs = load_json(os.path.join(current_output_dir, "env_images.json"))
    VideoClipGenerator(output_dir=current_output_dir).run(
        sbs,
        env_imgs,
        use_video_generator=args.use_video_generator,
        video_provider=args.video_provider,
    )
