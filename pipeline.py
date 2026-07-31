import os
from core.global_asset_index import GlobalAssetIndex
from steps.step1_extract_characters import CharacterExtractor
from steps.step1b_generate_char_images import CharacterImageGenerator
from steps.step2_extract_props import PropExtractor
from steps.step2b_generate_prop_images import PropImageGenerator
from steps.step3_generate_storyboard import StoryboardGenerator
from steps.step3b_audit_storyboard_assets import StoryboardAssetAuditor
from steps.step4_generate_env_images import EnvironmentImageGenerator
from steps.step5_generate_videos import VideoClipGenerator
from steps.step6_concat_video import VideoConcatenator


class Pipeline:
    """小说转AI短剧的完整Pipeline，支持断点续跑

    每个步骤的结果都保存为JSON，如果中间结果已存在则跳过该步骤。
    流程：提取角色 → 生成角色图 → 生成分镜稿 → 检查分镜资产引用 → 生成环境图 → 生成视频片段 → 拼接最终视频
    """

    STEP_NAMES = {
        1: "提取角色",
        2: "生成角色图",
        2.5: "提取并生成道具图",
        3: "生成分镜稿",
        "3b": "检查分镜资产引用",
        4: "生成环境图",
        5: "生成视频片段",
        6: "拼接最终视频",
    }

    def __init__(self, model=None, output_dir="output", style="动漫",
                 is_first_chapter=True, chapter_name=None, global_output_dir=None,
                 use_video_generator=False, video_provider=None,
                 on_step_start=None, on_step_end=None, on_log=None):
        """
        Args:
            on_step_start: callback(step_num, step_name) — 步骤开始前调用
            on_step_end: callback(step_num, step_name, result, elapsed_seconds) — 步骤完成后调用
            on_log: callback(step_num, message) — 步骤执行中的日志
        """
        self.style = self._normalize_style(style)
        self.base_output_dir = output_dir
        self.is_first_chapter = is_first_chapter
        self.global_output_dir = global_output_dir or output_dir
        self.use_video_generator = use_video_generator
        self.video_provider = video_provider
        self.chapter_name = self._default_chapter_name(chapter_name, is_first_chapter)
        self.output_dir = self._resolve_output_dir(output_dir, self.chapter_name)
        self.global_assets = GlobalAssetIndex(self.global_output_dir)
        output_dir = self.output_dir
        self.on_step_start = on_step_start
        self.on_step_end = on_step_end
        self.on_log = on_log
        os.makedirs(output_dir, exist_ok=True)

        self.step1 = CharacterExtractor(output_dir=output_dir, model=model)
        self.model = self.step1.model
        self.step2 = CharacterImageGenerator(output_dir=output_dir)
        self.step2b = PropExtractor(output_dir=output_dir, model=self.model)
        self.step2c = PropImageGenerator(output_dir=output_dir)
        self.step3 = StoryboardGenerator(output_dir=output_dir, model=self.model)
        self.step3b = StoryboardAssetAuditor(output_dir=output_dir, model=self.model)
        self.step4 = EnvironmentImageGenerator(output_dir=output_dir)
        self.step5 = VideoClipGenerator(output_dir=output_dir)
        self.step6 = VideoConcatenator(output_dir=output_dir)

    def _default_chapter_name(self, chapter_name, is_first_chapter):
        if chapter_name:
            return chapter_name
        if is_first_chapter:
            return "chapter_01"
        max_chapter = 1
        if os.path.isdir(self.global_output_dir):
            for entry in os.listdir(self.global_output_dir):
                if not entry.startswith("chapter_"):
                    continue
                suffix = entry.replace("chapter_", "", 1)
                if suffix.isdigit():
                    max_chapter = max(max_chapter, int(suffix))
        return f"chapter_{max_chapter + 1:02d}"

    def _resolve_output_dir(self, output_dir, chapter_name):
        if not chapter_name:
            return output_dir
        safe_name = str(chapter_name).strip().strip("/\\")
        if not safe_name:
            return output_dir
        if os.path.basename(os.path.normpath(output_dir)) == safe_name:
            return output_dir
        return os.path.join(output_dir, safe_name)

    def _normalize_style(self, style):
        style = str(style or "").strip()
        return style or "写实"

    def _apply_manual_style(self, char_data):
        if not isinstance(char_data, dict):
            char_data = {"characters": char_data or []}
        char_data["style"] = self.style
        return char_data

    def _notify_start(self, step_num):
        name = self.STEP_NAMES[step_num]
        print(f"\n[步骤{step_num}] {name}...")
        if self.on_step_start:
            self.on_step_start(step_num, name)

    def _notify_end(self, step_num, result, elapsed):
        name = self.STEP_NAMES[step_num]
        if self.on_step_end:
            self.on_step_end(step_num, name, result, elapsed)

    def _notify_log(self, step_num, message):
        print(f"  {message}")
        if self.on_log:
            self.on_log(step_num, message)

    def run(self, novel_file_path):
        import time
        print("=" * 60)
        print("AI短剧生成Pipeline启动")
        print(f"章节类型: {'第一章节' if self.is_first_chapter else '后续章节'}")
        print(f"画面风格: {self.style}")
        if self.chapter_name:
            print(f"章节目录: {self.output_dir}")
        if not self.is_first_chapter:
            print(f"全局资产目录: {self.global_output_dir}")
        print("=" * 60)

        # 步骤1：提取角色
        self._notify_start(1)
        t0 = time.time()
        if os.path.exists(self.step1.save_path):
            self._notify_log(1, "角色信息已存在，跳过提取")
            char_data = self.step1.load()
        elif self.is_first_chapter:
            char_data = self.step1.run(novel_file_path, style=self.style)
        else:
            global_characters = self.global_assets.load_characters()
            char_data = self.step1.run_with_previous(
                novel_file_path,
                None,
                previous_data=global_characters,
                style=self.style,
            )
        saved_style = char_data.get("style") if isinstance(char_data, dict) else None
        char_data = self._apply_manual_style(char_data)
        if saved_style != self.style:
            self.step1.save(char_data)
        characters = char_data["characters"]
        self.global_assets.save_characters_from_chapter(char_data, self.chapter_name)
        self._notify_end(1, char_data, time.time() - t0)

        # 步骤2：生成角色图
        self._notify_start(2)
        t0 = time.time()
        if self.is_first_chapter:
            character_images = self.step2.run(char_data)
        else:
            global_character_images = self.global_assets.load_character_images()
            character_images = self.step2.run_with_previous(
                char_data,
                None,
                previous_images=global_character_images,
            )
        self.global_assets.save_character_images_from_chapter(character_images)
        self._notify_end(2, character_images, time.time() - t0)

        # 步骤2.5：提取关键道具并生成道具图
        self._notify_start(2.5)
        t0 = time.time()
        if os.path.exists(self.step2b.save_path):
            self._notify_log(2.5, "道具信息已存在，跳过提取")
            prop_data = self.step2b.load()
        elif self.is_first_chapter:
            prop_data = self.step2b.run(novel_file_path)
        else:
            global_props = self.global_assets.load_props()
            prop_data = self.step2b.run_with_previous(
                novel_file_path,
                previous_data=global_props,
            )
        props = prop_data.get("props", [])
        self.global_assets.save_props_from_chapter(prop_data, self.chapter_name)
        if self.is_first_chapter:
            prop_images = self.step2c.run(prop_data, style=char_data.get("style", "写实"))
        else:
            global_prop_images = self.global_assets.load_prop_images()
            prop_images = self.step2c.run_with_previous(
                prop_data,
                previous_images=global_prop_images,
                style=char_data.get("style", "写实"),
            )
        self.global_assets.save_prop_images_from_chapter(prop_images)
        self._notify_end(2.5, {"props": prop_data, "prop_images": prop_images}, time.time() - t0)

        # 步骤3：生成分镜稿
        self._notify_start(3)
        t0 = time.time()
        if os.path.exists(self.step3.save_path):
            self._notify_log(3, "分镜稿已存在，跳过生成")
            storyboards = self.step3.load()
        else:
            storyboards = self.step3.run(novel_file_path, characters, props=props, style=char_data.get("style", "写实"))
        self._notify_end(3, storyboards, time.time() - t0)

        # 步骤3b：检查并修正分镜中的资产引用
        self._notify_start("3b")
        t0 = time.time()
        storyboards = self.step3b.run(characters=characters, props=props)
        self._notify_end("3b", storyboards, time.time() - t0)

        # 步骤4：生成环境图
        self._notify_start(4)
        t0 = time.time()
        if os.path.exists(self.step4.save_path):
            self._notify_log(4, "环境图已存在，跳过生成")
            env_images = self.step4.load()
        elif self.is_first_chapter:
            env_images = self.step4.run(storyboards, style=char_data.get("style", "写实"))
        else:
            global_envs = self.global_assets.load_environments()
            env_images = self.step4.run_with_previous(
                storyboards,
                style=char_data.get("style", "写实"),
                previous_output_dir=None,
                model=self.model,
                previous_envs=global_envs,
            )
        self.global_assets.save_environments_from_chapter(env_images, self.chapter_name)
        self._notify_end(4, env_images, time.time() - t0)

        # 步骤5：生成视频片段（环境图+角色描述+分镜 → 视频）
        self._notify_start(5)
        t0 = time.time()
        if os.path.exists(self.step5.save_path):
            self._notify_log(5, "视频片段已存在，跳过生成")
            video_clips = self.step5.load()
        else:
            video_clips = self.step5.run(
                storyboards,
                env_images,
                style=char_data.get("style", "写实"),
                use_video_generator=self.use_video_generator,
                video_provider=self.video_provider,
            )
        self._notify_end(5, video_clips, time.time() - t0)

        # 步骤6：拼接最终视频
        self._notify_start(6)
        t0 = time.time()
        final_path = self.step6.final_path
        if os.path.exists(final_path):
            self._notify_log(6, "最终视频已存在，跳过拼接")
        else:
            final_path = self.step6.run(video_clips)
        self._notify_end(6, final_path, time.time() - t0)

        print("\n" + "=" * 60)
        print("AI短剧生成完成!")
        print(f"输出目录: {self.output_dir}")
        print(f"最终视频: {final_path}")
        print("=" * 60)

        return final_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="小说转AI短剧完整Pipeline")
    parser.add_argument("--story-file", default="", help="小说章节文本路径；默认第一章 story.txt，后续章节 story_2.txt")
    parser.add_argument("--output-dir", default="output", help="当前章节输出根目录")
    parser.add_argument("--chapter-name", default="", help="章节文件夹名；默认第一章 chapter_01，后续章节 chapter_02")
    parser.add_argument("--model", default=None, help="LLM 模型；不传时读取 config.yaml")
    parser.add_argument("--style", default="动漫", help="人工指定的整体画面风格")
    parser.add_argument("--not-first-chapter", action="store_true", help="标记当前章节不是第一章节")
    parser.add_argument("--global-output-dir", default="output", help="全局资产索引目录")
    parser.add_argument("--use-video-generator", action="store_true", help="步骤5实际调用 provider.video_generator 生成视频；默认只打印并保存 JSON")
    parser.add_argument("--video-provider", choices=["ark", "zenmux"], default=None, help="视频生成后端；默认读取 config.yaml")
    args = parser.parse_args()

    is_first_chapter = not args.not_first_chapter
    story_file = args.story_file or ("story.txt" if is_first_chapter else "story_2.txt")
    chapter_name = args.chapter_name or ("chapter_01" if is_first_chapter else "chapter_02")

    pipeline = Pipeline(
        model=args.model,
        output_dir=args.output_dir,
        style=args.style,
        is_first_chapter=is_first_chapter,
        chapter_name=chapter_name,
        global_output_dir=args.global_output_dir,
        use_video_generator=args.use_video_generator,
        video_provider=args.video_provider,
    )
    pipeline.run(story_file)
