<div align="center">

# NovelReel

### 使用 AI 将网络小说转化为电影级视频

一个面向网络小说的开源 AI 影视制作流程，将长篇小说自动转化为剧本、
角色、分镜、配音和完整视频。

<a href="README.md"><img src="https://img.shields.io/badge/English-0969DA?style=for-the-badge" alt="English"></a>
<a href="README_zh-CN.md"><img src="https://img.shields.io/badge/中文-D73A49?style=for-the-badge" alt="中文"></a>

[项目介绍](#项目介绍) · [工作流程](#工作流程) · [角色展示](#角色展示) · [视频案例](#视频案例)

</div>

## 项目介绍

**NovelReel** 是一个专为网络小说设计的AI短剧制作流水线。它可以将小说
转化为完整的AI短剧，能够保持角色（形象 + 音色）和场景和的一致性，整个过程不需要人工介入。

### 核心功能

#### 1. 自动化小说转AI短剧

- 自动化角色、道具和场景提取和配图
- 跨章节角色、道具和场景图一致性保持
- 自动化剧本编排和连续剧情的视频生成

#### 2. 智能配音
- 按角色统一音色，跨境头音色一致性校准

## 工作流程

```mermaid
flowchart LR
    A[网络小说] --> B[故事分析]
    B --> C[影视剧本]
    C --> D[角色与世界观设计]
    D --> E[分镜设计]
    E --> F[图像与视频生成]
    C --> G[配音与音频]
    F --> H[剪辑与字幕]
    G --> H
    H --> I[最终影片]
```

1. 解析小说，提取角色、地点、事件和故事时间线。
2. 将原文改编为场景、对白、旁白和镜头描述。
3. 生成可重复使用的角色设定图和分镜画面。
4. 在保持角色与视觉风格一致的前提下生成视频镜头。
5. 添加配音、音乐、音效和字幕，导出最终影片。

## 角色展示

<table>
  <tr>
    <td align="center"><img src="assets/characters/character-01.jpg" width="240" alt="悬疑角色"><br><b>悬疑冒险</b></td>
    <td align="center"><img src="assets/characters/character-02.jpg" width="240" alt="奇幻角色"><br><b>灵异奇幻</b></td>
  </tr>
  <tr>
    <td align="center"><img src="assets/characters/character-03.jpg" width="240" alt="末日角色"><br><b>末日世界</b></td>
    <td align="center"><img src="assets/characters/character-04.jpg" width="240" alt="修仙角色"><br><b>东方修仙</b></td>
  </tr>
</table>

## 视频案例

点击预览图即可打开带音频的视频。

<table>
  <tr>
    <td align="center">
      <a href="assets/examples/example-01.mp4">
        <img src="assets/characters/character-01.jpg" width="360" alt="悬疑冒险视频案例">
      </a>
      <br><b>悬疑冒险</b>
    </td>
    <td align="center">
      <a href="assets/examples/example-02.mp4">
        <img src="assets/characters/character-02.jpg" width="360" alt="灵异奇幻视频案例">
      </a>
      <br><b>灵异奇幻</b>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="assets/examples/example-03.mp4">
        <img src="assets/characters/character-03.jpg" width="360" alt="末日题材视频案例">
      </a>
      <br><b>末日题材</b>
    </td>
    <td align="center">
      <a href="assets/examples/example-04.mp4">
        <img src="assets/characters/character-04.jpg" width="360" alt="东方修仙视频案例">
      </a>
      <br><b>东方修仙</b>
    </td>
  </tr>
</table>
本项目将采用开源协议发布。使用小说原文、生成素材、人物声音、音乐或
第三方模型进行创作前，请确认你拥有相应的使用权。

