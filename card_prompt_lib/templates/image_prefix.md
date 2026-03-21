# Image Prefix 模板

> 图片生成模型前缀指令，强制简体中文 + 内容主题锚定

## 模板

```
CRITICAL INSTRUCTIONS (MUST FOLLOW):
1. TOPIC: This is a {subject} educational knowledge card about "{card_title}".
2. TEXT RULES: ALL visible text MUST be Simplified Chinese (简体中文). 
   Use LARGE, BOLD, thick-stroke rounded/gothic sans-serif font. 
   Maximum 60 Chinese characters total in the entire image. 
   Each text block must be ≤10 characters. Make text as large as possible.
3. TEXT QUALITY: Render each Chinese character clearly with no distortion. 
   Use simple, common characters. Thick bold strokes. High contrast against background. 
   Do NOT use thin/serif/cursive fonts. Do NOT cram many characters in small space.
4. The main title should be "{card_title}" in extra-large bold font.
```

## 变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `{subject}` | 学科 | 数学 |
| `{card_title}` | 卡片标题（知识点名称） | 商末尾有0的除法 |

## 要点

- 这段前缀会拼接在 Step 1 生成的英文 prompt **前面**
- 目的是确保图片模型：
  1. 理解主题内容
  2. 用简体中文渲染文字
  3. 文字大、粗、清晰
  4. 标题正确
