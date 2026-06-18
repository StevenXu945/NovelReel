<div align="center">

# NovelReel

### Turn web novels into cinematic videos with LLMs and visual generative models

An open-source pipeline for adapting long-form web fiction into scripts,
consistent characters, visual shots, narration, and finished videos.

<a href="README.md"><img src="https://img.shields.io/badge/English-0969DA?style=for-the-badge" alt="English"></a>
<a href="README_zh-CN.md"><img src="https://img.shields.io/badge/中文-D73A49?style=for-the-badge" alt="中文"></a>

[Introduction](#introduction) · [Workflow](#workflow) · [Characters](#character-showcase) · [Examples](#video-examples)

</div>

## Introduction

**NovelReel** is an AI short-drama production pipeline designed specifically
for web novels. It transforms novels into complete AI short dramas while
maintaining consistent characters (appearance and voice), props, and scenes.
The entire production process requires no manual intervention.

### Core Features

#### 1. Automated Web Novel to AI Short Drama

- Automatically extracts characters, props, and scenes, then generates their
  corresponding reference images
- Preserves character, prop, and scene consistency across chapters
- Automatically structures screenplays and generates videos with narrative
  continuity

#### 2. Intelligent Voice Generation

- Assigns a consistent voice to each character
- Calibrates and preserves character voice consistency across shots


## Workflow

```mermaid
flowchart LR
    A[Web Novel] --> B[Story Analysis]
    B --> C[Screenplay]
    C --> D[Character & World Design]
    D --> E[Storyboard]
    E --> F[Image / Video Generation]
    C --> G[Voice & Audio]
    F --> H[Editing & Subtitles]
    G --> H
    H --> I[Final Movie]
```

1. Parse the novel and extract characters, locations, events, and timelines.
2. Adapt the source text into scenes, dialogue, narration, and camera directions.
3. Generate reusable character references and storyboard frames.
4. Produce video shots while preserving visual consistency.
5. Add voices, music, sound effects, subtitles, and export the final movie.

## Examples

Each example contains two character reference sheets and two consecutive
chapters. Click a chapter button to watch the video with audio.

### 1. The Lost Tomb

<table>
  <tr>
    <td align="center" width="50%"><img src="assets/characters_image/盗墓笔记_1.jpg" width="420" alt="The Lost Tomb character reference 1"><br><b>Character Reference 1</b></td>
    <td align="center" width="50%"><img src="assets/characters_image/盗墓笔记_2.jpg" width="420" alt="The Lost Tomb character reference 2"><br><b>Character Reference 2</b></td>
  </tr>
  <tr>
    <td align="center"><a href="https://youtu.be/ba7dlY-buiY"><img src="https://img.youtube.com/vi/ba7dlY-buiY/hqdefault.jpg" width="420" alt="Watch The Lost Tomb Chapter 1 on YouTube"></a><br><b>Chapter 1</b></td>
    <td align="center"><a href="https://youtu.be/npjA1qq8AhM"><img src="https://img.youtube.com/vi/npjA1qq8AhM/hqdefault.jpg" width="420" alt="Watch The Lost Tomb Chapter 2 on YouTube"></a><br><b>Chapter 2</b></td>
  </tr>
</table>

### 2. Maoshan Ghost Hunter

<table>
  <tr>
    <td align="center" width="50%"><img src="assets/characters_image/茅山捉鬼人_1.jpg" width="420" alt="Maoshan Ghost Hunter character reference 1"><br><b>Character Reference 1</b></td>
    <td align="center" width="50%"><img src="assets/characters_image/茅山捉鬼人_2.jpg" width="420" alt="Maoshan Ghost Hunter character reference 2"><br><b>Character Reference 2</b></td>
  </tr>
  <tr>
    <td align="center"><a href="https://youtu.be/GVt8tebEKvA"><img src="https://img.youtube.com/vi/GVt8tebEKvA/hqdefault.jpg" width="420" alt="Watch Maoshan Ghost Hunter Chapter 1 on YouTube"></a><br><b>Chapter 1</b></td>
    <td align="center"><a href="https://youtu.be/mdMaMKaI8Bc"><img src="https://img.youtube.com/vi/mdMaMKaI8Bc/hqdefault.jpg" width="420" alt="Watch Maoshan Ghost Hunter Chapter 2 on YouTube"></a><br><b>Chapter 2</b></td>
  </tr>
</table>

### 3. Scavenging at the End of the World

<table>
  <tr>
    <td align="center" width="50%"><img src="assets/characters_image/我在末日扫垃圾_1.jpg" width="420" alt="Apocalyptic story character reference 1"><br><b>Character Reference 1</b></td>
    <td align="center" width="50%"><img src="assets/characters_image/我在末日扫垃圾_2.jpg" width="420" alt="Apocalyptic story character reference 2"><br><b>Character Reference 2</b></td>
  </tr>
  <tr>
    <td align="center"><a href="https://youtu.be/9-AosqKD1IE"><img src="https://img.youtube.com/vi/9-AosqKD1IE/hqdefault.jpg" width="420" alt="Watch Scavenging at the End of the World Chapter 1 on YouTube"></a><br><b>Chapter 1</b></td>
    <td align="center"><a href="https://youtu.be/JrzBbX469sA"><img src="https://img.youtube.com/vi/JrzBbX469sA/hqdefault.jpg" width="420" alt="Watch Scavenging at the End of the World Chapter 2 on YouTube"></a><br><b>Chapter 2</b></td>
  </tr>
</table>

### 4. Stellar Transformations

<table>
  <tr>
    <td align="center" width="50%"><img src="assets/characters_image/星辰变_1.jpg" width="420" alt="Stellar Transformations character reference 1"><br><b>Character Reference 1</b></td>
    <td align="center" width="50%"><img src="assets/characters_image/星辰变_2.jpg" width="420" alt="Stellar Transformations character reference 2"><br><b>Character Reference 2</b></td>
  </tr>
  <tr>
    <td align="center"><a href="https://youtu.be/OesS29j5fVw"><img src="https://img.youtube.com/vi/OesS29j5fVw/hqdefault.jpg" width="420" alt="Watch Stellar Transformations Chapter 1 on YouTube"></a><br><b>Chapter 1</b></td>
    <td align="center"><a href="https://youtu.be/AsaULb0MdGM"><img src="https://img.youtube.com/vi/AsaULb0MdGM/hqdefault.jpg" width="420" alt="Watch Stellar Transformations Chapter 2 on YouTube"></a><br><b>Chapter 2</b></td>
  </tr>
</table>
