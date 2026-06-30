<div align="center">

# NovelReel

### 将网络小说转化为角色一致、电影级的 AI 短剧

一个由 LLM 和视觉生成模型驱动的端到端开源制作流水线。

<p>
  <img src="https://img.shields.io/badge/状态-开发中-F59E0B?style=flat-square" alt="状态：开发中">
  <img src="https://img.shields.io/badge/流程-全自动-2EA44F?style=flat-square" alt="全自动制作流程">
  <img src="https://img.shields.io/badge/一致性-视觉_%2B_音色-8250DF?style=flat-square" alt="视觉和音色一致性">
  <img src="https://img.shields.io/badge/内容-网络小说-0969DA?style=flat-square" alt="面向网络小说">
</p>

<p>
  <a href="README.md"><img src="https://img.shields.io/badge/English-0969DA?style=for-the-badge" alt="English"></a>
  <a href="README_zh-CN.md"><img src="https://img.shields.io/badge/中文-D73A49?style=for-the-badge" alt="中文"></a>
</p>

[项目介绍](#项目介绍) · [工作流程](#工作流程) · [案例展示](#案例展示) · [音色对比](#角色音色一致性对比)

</div>

---

## 项目介绍

**NovelReel** 是一个专为网络小说设计的 AI 短剧制作流水线。它可以将小说
转化为完整的 AI 短剧，并保持角色（形象与音色）、道具和场景的一致性。
整个制作过程无需人工介入。

### 核心能力

<table>
  <tr>
    <td width="50%"><b>自动化小说改编</b><br>提取故事元素、编排剧本，并生成剧情连续的 AI 短剧。</td>
    <td width="50%"><b>视觉一致性</b><br>保持角色形象、道具和场景在跨章节、跨镜头时的一致性。</td>
  </tr>
  <tr>
    <td width="50%"><b>角色音色一致性</b><br>为每个角色分配并校准稳定音色，贯穿完整故事。</td>
    <td width="50%"><b>端到端制作</b><br>串联故事分析、参考图、分镜、视频生成和最终音频制作。</td>
  </tr>
</table>

## 工作流程

<div align="center">
  <img src="assets/method.jpg" width="100%" alt="NovelReel 视频生成与角色音色一致性流水线">
  <br>
  <sub>NovelReel 视频生成与角色音色一致性流水线。</sub>
</div>

<br>

1. 解析小说，提取角色、地点、事件和故事时间线。
2. 建立跨章节共享的全局角色与道具参考。
3. 将原文改编为剧本、分镜和镜头描述。
4. 在保持角色、道具和场景一致的前提下生成视频镜头。
5. 分离对白、对齐说话角色、统一角色音色并生成最终音频。

---

## 案例展示

每个案例包含两张角色设定图和两个连续章节。

### 1. 盗墓笔记

<table>
  <tr>
    <th></th>
    <th align="center">第一章</th>
    <th align="center">第二章</th>
  </tr>
  <tr>
    <th align="center">角色设定图</th>
    <td align="center"><img src="assets/characters_image/盗墓笔记_1.jpg" width="360" alt="盗墓笔记第一章角色设定图"></td>
    <td align="center"><img src="assets/characters_image/盗墓笔记_2.jpg" width="360" alt="盗墓笔记第二章角色设定图"></td>
  </tr>
  <tr>
    <th align="center">生成视频片段</th>
    <td align="center"><a href="https://youtu.be/ba7dlY-buiY"><img src="assets/youtube_thumbnails/ba7dlY-buiY.jpg" width="360" alt="在 YouTube 观看盗墓笔记第一章"></a></td>
    <td align="center"><a href="https://youtu.be/npjA1qq8AhM"><img src="assets/youtube_thumbnails/npjA1qq8AhM.jpg" width="360" alt="在 YouTube 观看盗墓笔记第二章"></a></td>
  </tr>
</table>

### 2. 茅山捉鬼人

<table>
  <tr>
    <th></th>
    <th align="center">第一章</th>
    <th align="center">第二章</th>
  </tr>
  <tr>
    <th align="center">角色设定图</th>
    <td align="center"><img src="assets/characters_image/茅山捉鬼人_1.jpg" width="360" alt="茅山捉鬼人第一章角色设定图"></td>
    <td align="center"><img src="assets/characters_image/茅山捉鬼人_2.jpg" width="360" alt="茅山捉鬼人第二章角色设定图"></td>
  </tr>
  <tr>
    <th align="center">生成视频片段</th>
    <td align="center"><a href="https://youtu.be/GVt8tebEKvA"><img src="assets/youtube_thumbnails/GVt8tebEKvA.jpg" width="360" alt="在 YouTube 观看茅山捉鬼人第一章"></a></td>
    <td align="center"><a href="https://youtu.be/mdMaMKaI8Bc"><img src="assets/youtube_thumbnails/mdMaMKaI8Bc.jpg" width="360" alt="在 YouTube 观看茅山捉鬼人第二章"></a></td>
  </tr>
</table>

### 3. 我在末日扫垃圾

<table>
  <tr>
    <th></th>
    <th align="center">第一章</th>
    <th align="center">第二章</th>
  </tr>
  <tr>
    <th align="center">角色设定图</th>
    <td align="center"><img src="assets/characters_image/我在末日扫垃圾_1.jpg" width="360" alt="我在末日扫垃圾第一章角色设定图"></td>
    <td align="center"><img src="assets/characters_image/我在末日扫垃圾_2.jpg" width="360" alt="我在末日扫垃圾第二章角色设定图"></td>
  </tr>
  <tr>
    <th align="center">生成视频片段</th>
    <td align="center"><a href="https://youtu.be/9-AosqKD1IE"><img src="assets/youtube_thumbnails/9-AosqKD1IE.jpg" width="360" alt="在 YouTube 观看我在末日扫垃圾第一章"></a></td>
    <td align="center"><a href="https://youtu.be/JrzBbX469sA"><img src="assets/youtube_thumbnails/JrzBbX469sA.jpg" width="360" alt="在 YouTube 观看我在末日扫垃圾第二章"></a></td>
  </tr>
</table>

### 4. 星辰变

<table>
  <tr>
    <th></th>
    <th align="center">第一章</th>
    <th align="center">第二章</th>
  </tr>
  <tr>
    <th align="center">角色设定图</th>
    <td align="center"><img src="assets/characters_image/星辰变_1.jpg" width="360" alt="星辰变第一章角色设定图"></td>
    <td align="center"><img src="assets/characters_image/星辰变_2.jpg" width="360" alt="星辰变第二章角色设定图"></td>
  </tr>
  <tr>
    <th align="center">生成视频片段</th>
    <td align="center"><a href="https://youtu.be/OesS29j5fVw"><img src="assets/youtube_thumbnails/OesS29j5fVw.jpg" width="360" alt="在 YouTube 观看星辰变第一章"></a></td>
    <td align="center"><a href="https://youtu.be/AsaULb0MdGM"><img src="assets/youtube_thumbnails/AsaULb0MdGM.jpg" width="360" alt="在 YouTube 观看星辰变第二章"></a></td>
  </tr>
</table>

---

## 角色音色一致性对比

对同一角色跨镜头、跨章节的音色进行校准，使角色声音在连续剧情中保持一致。

### 对比例子 1

<table>
  <tr>
    <th align="center">音色一致化前</th>
    <th align="center">音色一致化后</th>
  </tr>
  <tr>
    <td align="center"><a href="https://youtu.be/LO2K_PX2f_s"><img src="assets/youtube_thumbnails/LO2K_PX2f_s.jpg" width="420" alt="观看角色音色一致化前的视频"></a></td>
    <td align="center"><a href="https://youtu.be/9-AosqKD1IE"><img src="assets/youtube_thumbnails/9-AosqKD1IE.jpg" width="420" alt="观看角色音色一致化后的视频"></a></td>
  </tr>
</table>

### 对比例子 2

<table>
  <tr>
    <th align="center">音色一致化前</th>
    <th align="center">音色一致化后</th>
  </tr>
  <tr>
    <td align="center"><a href="https://youtu.be/nrP3PAaMTfA"><img src="assets/youtube_thumbnails/nrP3PAaMTfA.jpg" width="420" alt="观看角色音色一致化前的视频"></a></td>
    <td align="center"><a href="https://youtu.be/mdMaMKaI8Bc"><img src="assets/youtube_thumbnails/mdMaMKaI8Bc.jpg" width="420" alt="观看角色音色一致化后的视频"></a></td>
  </tr>
</table>


## 环境准备

使用 Python 3.10 或更高版本。

```bash
pip install -r requirement.txt
```

需要单独安装 `ffmpeg`，因为 Step 6 和语音工具会从命令行调用它。

```bash
sudo apt update
sudo apt install -y ffmpeg
```

如果使用 macOS，可以改用：

```bash
brew install ffmpeg
```

在 `config.yaml` 中配置 API Key 和模型服务商。

## 运行完整流水线

第一章：

```bash
python pipeline.py --chapter-name chapter_01 --story-file story.txt --style 动漫
```

后续章节：

```bash
python pipeline.py --not-first-chapter --global-output-dir output --chapter-name chapter_02 --story-file story_2.txt --style 动漫
```

默认情况下，Step 5 是 Mock 模式：它只会打印视频提示词并写入 `video_clips.json`，不会调用视频生成 API。要实际生成视频片段，需要加上：

```bash
python pipeline.py --chapter-name chapter_01 --story-file story.txt --style 动漫 --use-video-generator --video-provider zenmux
```

## 手动分步运行

第一章：

```bash
python -m steps.step1_extract_characters --chapter-name chapter_01 --story-file story.txt --style 动漫
python -m steps.step1b_generate_char_images --chapter-name chapter_01
python -m steps.step2_extract_props --chapter-name chapter_01 --story-file story.txt
python -m steps.step2b_generate_prop_images --chapter-name chapter_01
python -m steps.step3_generate_storyboard --chapter-name chapter_01 --story-file story.txt
python -m steps.step3b_audit_storyboard_assets --chapter-name chapter_01
python -m steps.step4_generate_env_images --chapter-name chapter_01
python -m steps.step5_generate_videos --chapter-name chapter_01 --use-video-generator --video-provider zenmux
python -m steps.step6_concat_video --chapter-name chapter_01
```

后续章节：

```bash
python -m steps.step1_extract_characters --not-first-chapter --global-output-dir output --chapter-name chapter_02 --story-file story_2.txt --style 动漫
python -m steps.step1b_generate_char_images --not-first-chapter --global-output-dir output --chapter-name chapter_02
python -m steps.step2_extract_props --not-first-chapter --global-output-dir output --chapter-name chapter_02 --story-file story_2.txt
python -m steps.step2b_generate_prop_images --not-first-chapter --global-output-dir output --chapter-name chapter_02
python -m steps.step3_generate_storyboard --not-first-chapter --chapter-name chapter_02 --story-file story_2.txt
python -m steps.step3b_audit_storyboard_assets --not-first-chapter --chapter-name chapter_02
python -m steps.step4_generate_env_images --not-first-chapter --global-output-dir output --chapter-name chapter_02
python -m steps.step5_generate_videos --not-first-chapter --chapter-name chapter_02 --use-video-generator --video-provider zenmux
python -m steps.step6_concat_video --chapter-name chapter_02
```

## 语音流程

语音流水线会从生成的视频片段中提取对白时间轴，为每个说话人分配可复用的 `voice_id`，使用 CosyVoice 生成克隆对白音频，并将对白混入每个分镜对应的背景音频中。

请按照 CosyVoice 官方 GitHub README 安装 CosyVoice、下载 CosyVoice2 模型，并按需配置 vLLM：https://github.com/FunAudioLLM/CosyVoice

Step 5 生成 `video_clips.json` 和 `videos/*.mp4` 后，可以按以下三步运行语音流程。

Step 1：提取对白文本和时间轴：

```bash
python voice/extract_dialogue_time.py output/chapter_01 --model gemini-3.1-pro-preview --asr-model voice/faster-whisper-large --device cpu --compute-type int8
```

在章节目录下准备声音模板：

```text
output/chapter_01/
  voice_template/
    dialogues.json
    男主_少年.wav
    女主_中年.wav
```

`voice_template/dialogues.json` 需要把每个模板 wav 文件名映射到该音频中真实说出的提示文本：

```json
[
  {
    "voice_id": "男主_少年",
    "voice_text": "这里填写这段声音模板里真实说出的文字。"
  }
]
```

Step 2：生成 CosyVoice 对白音频，并和每个分镜的背景音频混合：

```bash
python voice/render_dialogue_audio.py output/chapter_01
```

Step 3：用混合后的对白音频替换每个生成视频的原始音频：

```bash
python voice/replace_video_audio.py output/chapter_01
```
