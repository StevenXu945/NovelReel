---
name: video-prompt-full-reference-images
description: >
  Rewrite a video prompt in full-reference mode using one or more image assets whose
  contents are supplied as trusted text descriptions. Tracks referenced subjects and
  picture anchors across six structured output sections. Video and audio reference
  assets are intentionally unsupported.
---

# Full-Reference Image Rewrite Output Format Guide

Use only image references. The image contents are supplied through trusted textual
descriptions; do not claim to have opened, inspected, or directly observed an image.
Treat each supplied description as the authoritative description of that asset, but do
not infer identity, history, personality, voice, or other facts beyond it.

Write all six sections in English. Preserve the original language only for dialogue and
lyrics inside `<d>`. Visible text would retain its original language, but this workflow
forbids visible text, subtitles, titles, logos, signs, and watermarks in the generated
video.

Make `detailed_description` detailed and explicit. For every shot, establish composition,
subject appearance and position, environment and lighting, actions and state changes,
camera movement, current sound, and where referenced content appears or takes effect.
Do not reduce it to a plot summary or a reference-relationship list.

## 1. Overall Structure

Output exactly six sections in this order:

| Section | Purpose |
| --- | --- |
| `subject_definitions` | Defines referenced visible content and picture anchors |
| `summary` | Summarizes the task type, target video, and main image relationships |
| `retention_analysis` | Describes how referenced content is preserved or transferred |
| `detailed_description` | Describes visuals, actions, shots, sound, and dialogue in playback order |
| `overall_soundscape` | Summarizes ambience and physical sounds |
| `non_diegetic_music` | Must be `N/A` in this workflow |

## 2. Reference Labels (`subject_definitions`)

Use only these two label types:

| Label | Meaning |
| --- | --- |
| `<Subject N>` | Visible content abstracted from an image description and reused or modified in the target video |
| `<Picture N>` | A reference image used as a concrete target frame, storyboard, or composition anchor |

Once assigned, a label must retain the same meaning in all six sections.

### 2.1 `<Subject N>`

Use `<Subject N>` for visible reusable content, including people, animals, objects,
environments, clothing, props, interfaces, visual effects, visual styles, expressions,
and poses. It represents a content unit rather than an image file.

```text
<Subject 1> is the young woman described by <Picture 2>, with long dark hair, a blue cardigan, and a thin silver necklace.
```

One subject may be defined by several pictures. State what each picture contributes:

```text
<Subject 1> is the woman whose facial appearance is described by <Picture 1> and whose full outfit and body proportions are described by <Picture 2>.
```

The supplied asset description is trusted. Use facts present in that description, even
when they include an asset role or identity label, but do not add unsupported facts.

### 2.2 `<Picture N>`

Create a standalone `<Picture N>` entry only when the image itself is a first frame,
keyframe, last frame, edited keyframe, storyboard, or composition anchor:

```text
<Picture 1> is the composition anchor for [Shot 1], defining the environment layout, viewpoint, and subject placement.
```

If an image only defines a character, environment, costume, prop, or style, cite it in
the relevant `<Subject N>` definition without creating a standalone picture entry.

Do not claim that a static image supplies motion, timing, sound, voice, or temporal
structure.

## 3. `summary`

Write one short English paragraph beginning with one of these task-type prefixes:

| Task type | Use |
| --- | --- |
| `keyframe completion` | An image is a concrete first frame, keyframe, last frame, or composition anchor |
| `reference generation` | An image guides a subject, environment, style, pose, composition, or storyboard without serving as a concrete frame |

Combine both when appropriate:

```text
[keyframe completion + reference generation] ...
```

Otherwise use `[keyframe completion]` or `[reference generation]`. Refer only to labels
already defined in `subject_definitions`.

## 4. `retention_analysis`

Write one English line for every `<Subject N>` and every standalone `<Picture N>`. Use
only these fixed relationship markers:

| Marker | Meaning |
| --- | --- |
| `fully_preserved` | The defined visible identity, appearance, composition, or frame-anchor role is retained |
| `partially_preserved` | The reference remains in use, but only part of its defined characteristics is retained |
| `attribute_transfer` | Referenced characteristics are transferred to another identifiable target subject |
| `weak_reference` | Only broad style, category, composition, or atmosphere is retained |

```text
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - its defined appearance and clothing remain consistent.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - the opening viewpoint and principal subject placement are retained.
```

New target-video actions, backgrounds, and plot events do not automatically reduce
reference fidelity.

## 5. `detailed_description`

Describe the target video shot by shot in playback order.

### 5.1 Basic Format

- Write the body in English.
- `[Shot 1]` marks the opening shot and has no timestamp.
- Later shots use `[Shot N] At MM:SS.mmm, ...` to mark cut times.
- Choose the number of shots according to the source `video_prompt`'s complexity, including
  its action beats, speaker changes, composition changes, camera coverage, and pacing.
  Do not force every storyboard into the same shot count. A 15-second storyboard must
  contain at least 3 shots.
- Describe camera movement naturally, including type, amplitude, and speed when useful.
- Assign stable `(S1)`, `(S2)`, and later IDs in the order of actual vocal events.
- Put complete dialogue and lyrics only inside `<d>[Language] ...</d>`.
- Use `<scenetrans>` and `<cutoff>` only when dialogue crosses a cut or is truncated by the ending.

Before `[Shot 1]`, use one or two English sentences to establish the overall visual
style. For generation tasks, normally write 350-500 English words. Dialogue-dense
content prioritizes fitting the spoken timeline rather than mechanically reaching the
word count.

### 5.2 Using Reference Labels

At the first clear appearance of an important `<Subject N>`, state its referenced
features, frame position, and current action. Continue using the same label later without
redefining it.

For concrete frame anchors, use natural phrasing:

```text
the shot begins from <Picture 1>
the shot's keyframe corresponds to <Picture 2>
the shot ends on <Picture 3>
```

Motion, timing, sound, and camera behavior must come from the source `video_prompt` or
reasonable target-video design, never from an image description.

### 5.3 Speakers and Dialogue

When a referenced subject speaks, retain both its visual label and speaker ID:

```text
<Subject 2> (S1) turns toward the other person and says, <d>[Chinese] 我们该走了。</d>
```

Keep the same `(Sx)` when that subject speaks off-screen. For narration or another vocal
source without a corresponding subject, use a stable English source description followed
by `(Sx)`. Do not infer voice timbre, accent, or delivery from visual descriptions.

Preserve supplied dialogue, its language, speaker order, and meaning. Do not invent
dialogue unless a short line is necessary to express an event already present in the
source prompt.

### 5.4 Mandatory Generation Constraints

State the following requirements naturally at the beginning of `detailed_description`:

- Follow the project visual style supplied by the caller and do not mix incompatible styles.
- Do not directly show exposed organs, penetration wounds, dismemberment, torn flesh,
  eye injury, or substantial blood or bodily-fluid spray.
- Preserve the plot outcome of violent events through occlusion, silhouette, off-screen
  action, brief cutaways, sound, environmental reactions, and character reactions.
- Do not show any visible text, subtitles, captions, titles, logos, signs, or watermarks.

## 6. Target-Video Sound

`overall_soundscape` describes only ambience and physical sounds generated for the target
video. Do not claim that sound comes from an image:

```text
overall_soundscape:
Quiet indoor room tone, distant movement, and subtle object-handling sounds continue throughout the scene.
```

This workflow does not generate audience-only background music:

```text
non_diegetic_music:
N/A
```

## 7. Complete Example

The original full-reference example is retained below, adapted only so that every visible
subject comes from an image reference and no video or audio reference labels are used.

```text
subject_definitions:
<Subject 1> is the coffee-shop environment in <Picture 1>, featuring an exposed brick wall, an orange tufted sofa with patterned pillows, an unlettered neon wall light, and a wooden coffee table.
<Subject 2> is the fluffy white Samoyed in <Picture 2> and <Picture 3>, with thick white fur, pointed ears, a dark nose, and a curved tail.
<Subject 3> is the young blonde woman in <Picture 4>, with long blonde hair and a light-pink button-down shirt with rolled-up sleeves.
<Subject 4> is the young man in <Picture 5>, with short wavy brown hair and a dark-grey hoodie with drawstrings.

summary:
[reference generation] The target video shows <Subject 3> eating a cookie in <Subject 1>. <Subject 4> enters with <Subject 2>, which lunges toward the cookie. The three-shot exchange preserves the defining visual features of all four subjects and ends with a canned audience laugh.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - the exposed brick wall, orange tufted sofa, patterned pillows, unlettered neon wall light, and wooden coffee table are retained.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - the Samoyed's thick white fur, pointed ears, dark nose, and curved tail are retained.
<Subject 3> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - the blonde woman's identity, long hair, and light-pink shirt are retained.
<Subject 4> (appears in [Shot 1], [Shot 2]): fully_preserved - the young man's short wavy brown hair and dark-grey hoodie are retained.

detailed_description:
The target video uses a realistic multi-camera sitcom style with warm indoor lighting. It contains no visible text, subtitles, captions, titles, logos, signs, or watermarks.
[Shot 1] A medium shot establishes <Subject 1>, the coffee shop with its exposed brick wall, orange tufted sofa, patterned pillows, unlettered neon wall light, and wooden coffee table. <Subject 3> (S1), the young woman with long blonde hair and a light-pink button-down shirt with rolled-up sleeves, sits on the sofa holding a chocolate-chip cookie. From the left, <Subject 4>, the young man with short wavy brown hair and a dark-grey hoodie with drawstrings, enters holding the leash of <Subject 2>, the thick-furred white Samoyed with pointed ears, a dark nose, and a curved tail. The dog lunges toward the cookie and pulls the leash taut. <Subject 3> (S1) jerks her hand back and exclaims with light annoyance, <d>[English] Hey! Watch your dog!</d> She closes her lips and guards the cookie while <Subject 4> pulls the dog back.
[Shot 2] At 00:03.000, the shot cuts to a close-up of <Subject 4> (S2), the young man in the dark-grey hoodie from Shot 1, sitting beside <Subject 3> on the sofa and holding <Subject 2> securely in his arms. <Subject 4> (S2) speaks with a playful tone and an easy conversational pace, <d>[English] He just likes cookies more than me.</d> He closes his mouth into an apologetic smile and strokes the dog's thick white fur.
[Shot 3] At 00:05.000, the shot cuts to a close-up of <Subject 3> (S1), the blonde woman in the light-pink shirt from Shot 1. Her annoyance softens as she looks toward the Samoyed. <Subject 3> (S1) replies with an amused cadence, <d>[English] Well, he has good taste at least.</d> She smiles and raises the cookie in a small toast-like gesture. A classic canned audience laugh begins immediately after the line and continues through the final frame.

overall_soundscape:
Soft indoor coffee-shop room tone continues throughout the scene. The leash pulling taut, clothing movement, quiet dog movement, and the canned audience laugh are audible at their corresponding moments.

non_diegetic_music:
N/A
```
