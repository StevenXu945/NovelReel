<div align="center">

# NovelReel

### Turn web novels into consistent, cinematic AI short dramas

An open-source, end-to-end production pipeline powered by LLMs and visual
generative models.

<p>
  <img src="https://img.shields.io/badge/status-work_in_progress-F59E0B?style=flat-square" alt="Status: work in progress">
  <img src="https://img.shields.io/badge/pipeline-fully_automated-2EA44F?style=flat-square" alt="Fully automated pipeline">
  <img src="https://img.shields.io/badge/consistency-visual_%2B_voice-8250DF?style=flat-square" alt="Visual and voice consistency">
  <img src="https://img.shields.io/badge/content-web_novels-0969DA?style=flat-square" alt="Designed for web novels">
</p>

<p>
  <a href="README.md"><img src="https://img.shields.io/badge/English-0969DA?style=for-the-badge" alt="English"></a>
  <a href="README_zh-CN.md"><img src="https://img.shields.io/badge/中文-D73A49?style=for-the-badge" alt="中文"></a>
</p>

[Introduction](#introduction) · [Workflow](#workflow) · [Examples](#examples) · [Voice Comparison](#character-voice-consistency-comparison)

</div>

---

## Introduction

**NovelReel** is an AI short-drama production pipeline designed specifically
for web novels. It transforms novels into complete AI short dramas while
maintaining consistent characters (appearance and voice), props, and scenes.
The entire production process requires no manual intervention.

### Highlights

<table>
  <tr>
    <td width="50%"><b>Automated Adaptation</b><br>Extracts story elements, structures screenplays, and generates continuous short-drama episodes.</td>
    <td width="50%"><b>Visual Consistency</b><br>Maintains character appearance, props, and scene identity across chapters and shots.</td>
  </tr>
  <tr>
    <td width="50%"><b>Character Voice Consistency</b><br>Assigns and calibrates a stable voice for every character across the full story.</td>
    <td width="50%"><b>End-to-End Production</b><br>Connects story analysis, reference generation, storyboarding, video generation, and final audio.</td>
  </tr>
</table>

## Workflow

<div align="center">
  <img src="assets/method.jpg" width="100%" alt="NovelReel video generation and voice consistency pipeline">
  <br>
  <sub>NovelReel video generation and character voice consistency pipeline.</sub>
</div>

<br>

1. Parse the novel and extract characters, locations, events, and timelines.
2. Build global character and prop references shared across chapters.
3. Adapt the source text into screenplays, storyboards, and camera directions.
4. Generate video shots while preserving character, prop, and scene consistency.
5. Separate dialogue, align speakers, unify character voices, and produce final audio.

---

## Examples

Each example contains two character reference sheets and two consecutive
chapters. Click a video thumbnail to watch the generated chapter with audio.

### 1. The Lost Tomb

<table>
  <tr>
    <th></th>
    <th align="center">Chapter 1</th>
    <th align="center">Chapter 2</th>
  </tr>
  <tr>
    <th align="center">Character Design</th>
    <td align="center"><img src="assets/characters_image/盗墓笔记_1.jpg" width="360" alt="The Lost Tomb Chapter 1 character design"></td>
    <td align="center"><img src="assets/characters_image/盗墓笔记_2.jpg" width="360" alt="The Lost Tomb Chapter 2 character design"></td>
  </tr>
  <tr>
    <th align="center">Generated Video Clip</th>
    <td align="center"><a href="https://youtu.be/ba7dlY-buiY"><img src="assets/youtube_thumbnails/ba7dlY-buiY.jpg" width="360" alt="Watch The Lost Tomb Chapter 1 on YouTube"></a></td>
    <td align="center"><a href="https://youtu.be/npjA1qq8AhM"><img src="assets/youtube_thumbnails/npjA1qq8AhM.jpg" width="360" alt="Watch The Lost Tomb Chapter 2 on YouTube"></a></td>
  </tr>
</table>

### 2. Maoshan Ghost Hunter

<table>
  <tr>
    <th></th>
    <th align="center">Chapter 1</th>
    <th align="center">Chapter 2</th>
  </tr>
  <tr>
    <th align="center">Character Design</th>
    <td align="center"><img src="assets/characters_image/茅山捉鬼人_1.jpg" width="360" alt="Maoshan Ghost Hunter Chapter 1 character design"></td>
    <td align="center"><img src="assets/characters_image/茅山捉鬼人_2.jpg" width="360" alt="Maoshan Ghost Hunter Chapter 2 character design"></td>
  </tr>
  <tr>
    <th align="center">Generated Video Clip</th>
    <td align="center"><a href="https://youtu.be/GVt8tebEKvA"><img src="assets/youtube_thumbnails/GVt8tebEKvA.jpg" width="360" alt="Watch Maoshan Ghost Hunter Chapter 1 on YouTube"></a></td>
    <td align="center"><a href="https://youtu.be/mdMaMKaI8Bc"><img src="assets/youtube_thumbnails/mdMaMKaI8Bc.jpg" width="360" alt="Watch Maoshan Ghost Hunter Chapter 2 on YouTube"></a></td>
  </tr>
</table>

### 3. Scavenging at the End of the World

<table>
  <tr>
    <th></th>
    <th align="center">Chapter 1</th>
    <th align="center">Chapter 2</th>
  </tr>
  <tr>
    <th align="center">Character Design</th>
    <td align="center"><img src="assets/characters_image/我在末日扫垃圾_1.jpg" width="360" alt="Scavenging at the End of the World Chapter 1 character design"></td>
    <td align="center"><img src="assets/characters_image/我在末日扫垃圾_2.jpg" width="360" alt="Scavenging at the End of the World Chapter 2 character design"></td>
  </tr>
  <tr>
    <th align="center">Generated Video Clip</th>
    <td align="center"><a href="https://youtu.be/9-AosqKD1IE"><img src="assets/youtube_thumbnails/9-AosqKD1IE.jpg" width="360" alt="Watch Scavenging at the End of the World Chapter 1 on YouTube"></a></td>
    <td align="center"><a href="https://youtu.be/JrzBbX469sA"><img src="assets/youtube_thumbnails/JrzBbX469sA.jpg" width="360" alt="Watch Scavenging at the End of the World Chapter 2 on YouTube"></a></td>
  </tr>
</table>

### 4. Stellar Transformations

<table>
  <tr>
    <th></th>
    <th align="center">Chapter 1</th>
    <th align="center">Chapter 2</th>
  </tr>
  <tr>
    <th align="center">Character Design</th>
    <td align="center"><img src="assets/characters_image/星辰变_1.jpg" width="360" alt="Stellar Transformations Chapter 1 character design"></td>
    <td align="center"><img src="assets/characters_image/星辰变_2.jpg" width="360" alt="Stellar Transformations Chapter 2 character design"></td>
  </tr>
  <tr>
    <th align="center">Generated Video Clip</th>
    <td align="center"><a href="https://youtu.be/OesS29j5fVw"><img src="assets/youtube_thumbnails/OesS29j5fVw.jpg" width="360" alt="Watch Stellar Transformations Chapter 1 on YouTube"></a></td>
    <td align="center"><a href="https://youtu.be/AsaULb0MdGM"><img src="assets/youtube_thumbnails/AsaULb0MdGM.jpg" width="360" alt="Watch Stellar Transformations Chapter 2 on YouTube"></a></td>
  </tr>
</table>

---

## Character Voice Consistency Comparison

NovelReel calibrates each character's voice across shots and chapters, keeping
the voice consistent throughout a continuous storyline. Click a thumbnail to
compare the complete videos before and after voice consistency processing.

### Comparison 1

<table>
  <tr>
    <th align="center">Before Voice Consistency</th>
    <th align="center">After Voice Consistency</th>
  </tr>
  <tr>
    <td align="center"><a href="https://youtu.be/LO2K_PX2f_s"><img src="assets/youtube_thumbnails/LO2K_PX2f_s.jpg" width="420" alt="Watch the video before character voice consistency"></a></td>
    <td align="center"><a href="https://youtu.be/9-AosqKD1IE"><img src="assets/youtube_thumbnails/9-AosqKD1IE.jpg" width="420" alt="Watch the video after character voice consistency"></a></td>
  </tr>
</table>

### Comparison 2

<table>
  <tr>
    <th align="center">Before Voice Consistency</th>
    <th align="center">After Voice Consistency</th>
  </tr>
  <tr>
    <td align="center"><a href="https://youtu.be/nrP3PAaMTfA"><img src="assets/youtube_thumbnails/nrP3PAaMTfA.jpg" width="420" alt="Watch the video before character voice consistency"></a></td>
    <td align="center"><a href="https://youtu.be/mdMaMKaI8Bc"><img src="assets/youtube_thumbnails/mdMaMKaI8Bc.jpg" width="420" alt="Watch the video after character voice consistency"></a></td>
  </tr>
</table>

## Setup

Use Python 3.10 or newer.

```bash
pip install -r requirement.txt
```

Install `ffmpeg` separately because Step 6 and the voice tools call it from the command line.

```bash
sudo apt update
sudo apt install -y ffmpeg
```

On macOS, use `brew install ffmpeg` instead.

Configure API keys and model providers in `config.yaml`.

## Run The Full Pipeline

First chapter:

```bash
python pipeline.py --chapter-name chapter_01 --story-file story.txt --style 动漫
```

Later chapter:

```bash
python pipeline.py --not-first-chapter --global-output-dir output --chapter-name chapter_02 --story-file story_2.txt --style 动漫
```

By default, Step 5 is mock mode: it prints video prompts and writes `video_clips.json`, but does not call the video generation API. To actually generate video clips:

```bash
python pipeline.py --chapter-name chapter_01 --story-file story.txt --style 动漫 --use-video-generator --video-provider zenmux
```

## Run Steps Manually

First chapter:

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

Later chapter:

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


## Voice

The voice pipeline extracts dialogue timing from generated clips, assigns each speaker a reusable `voice_id`, generates cloned dialogue audio with CosyVoice, and mixes the dialogue back onto each storyboard background audio.

Install CosyVoice, download the CosyVoice2 model, and configure optional vLLM strictly according to the official GitHub README: https://github.com/FunAudioLLM/CosyVoice

After Step 5 has produced `video_clips.json` and `videos/*.mp4`, run the voice pipeline in three steps.

Step 1: extract dialogue text and timing:

```bash
python voice/extract_dialogue_time.py output/chapter_01 --model gemini-3.1-pro-preview --asr-model voice/faster-whisper-large --device cpu --compute-type int8
```

Prepare voice templates under the chapter directory:

```text
output/chapter_01/
  voice_template/
    dialogues.json
    男主_少年.wav
    女主_中年.wav
```

`voice_template/dialogues.json` should map each template wav stem to the prompt text spoken in that wav:

```json
[
  {
    "voice_id": "男主_少年",
    "voice_text": "这里填写这段声音模板里真实说出的文字。"
  }
]
```

Step 2: render CosyVoice dialogue audio and mix it with each storyboard background audio:

```bash
python voice/render_dialogue_audio.py output/chapter_01
```

Step 3: replace each generated video's original audio with the mixed dialogue audio:

```bash
python voice/replace_video_audio.py output/chapter_01
```
