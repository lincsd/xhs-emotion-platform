# 🎴 小红书图文卡片模板规格文档

> XiaoHongShu Image-Text Card Template Specifications
> Canvas: 1080×1440px (3:4 ratio) · HTML Canvas API rendering

---

## 概述

本文档定义 8 种小红书主流图文卡片模板风格的完整设计规格，可直接用于 Canvas 渲染函数的编码实现。每个模板包含封面卡（Cover）、内容卡（Content）和结尾卡（Ending）三种子页面类型。

---

## 模板一览

| # | ID | 名称 | 英文名 | 主色 | 适用赛道 |
|---|-----|------|--------|------|----------|
| 1 | `minimalist_literary` | 简约文艺 | Minimalist Literary | `#2c2c2c` | 情感、成长、读书 |
| 2 | `fresh_cute` | 清新可爱 | Fresh & Cute | `#ff85a2` | 日常、美食、手帐 |
| 3 | `premium_business` | 高级感商务 | Premium Business | `#1a1a2e` | 职场、科技、理财 |
| 4 | `ins_aesthetic` | INS风 | Instagram Aesthetic | `#f5e6d3` | 穿搭、生活、旅行 |
| 5 | `warm_healing` | 暖色治愈 | Warm Healing | `#ff6b35` | 情感治愈、心理、正能量 |
| 6 | `dark_cool` | 暗黑酷炫 | Dark Cool | `#0f0f0f` | 摄影、音乐、潮流 |
| 7 | `chinese_retro` | 国潮复古 | Chinese Retro | `#c41e3a` | 国风、传统文化、汉服 |
| 8 | `study_knowledge` | 学习干货 | Study/Knowledge | `#4a90d9` | 学习、考试、干货分享 |

---

## JSON 规格定义

```json
{
  "cardTemplates": [
    {
      "id": "minimalist_literary",
      "name": "简约文艺",
      "nameEn": "Minimalist Literary",
      "icon": "📖",
      "bestFor": ["情感语录", "读书笔记", "人生感悟", "文艺日常", "成长日记"],
      "mood": "安静、克制、有留白感，像一页手写信笺",
      "canvas": { "width": 1080, "height": 1440 },

      "colorPalette": {
        "primary": "#2c2c2c",
        "secondary": "#8a7f72",
        "accent": "#c4a882",
        "background": "#f7f3ee",
        "backgroundAlt": "#eee8df",
        "text": "#2c2c2c",
        "textLight": "#6b6560",
        "textMuted": "#a09890",
        "border": "#d8d0c4",
        "highlight": "#e8dcc8"
      },

      "background": {
        "type": "solid_with_texture",
        "color": "#f7f3ee",
        "texture": "paper_grain",
        "textureDescription": "用 Canvas noise 在背景上叠加极淡的纸纹质感（alpha 0.02~0.04 随机灰点）",
        "implementation": [
          "ctx.fillStyle = '#f7f3ee'",
          "ctx.fillRect(0, 0, 1080, 1440)",
          "// 叠加纸纹噪点",
          "for (let i = 0; i < 8000; i++) {",
          "  ctx.fillStyle = `rgba(${120+Math.random()*40}, ${110+Math.random()*40}, ${100+Math.random()*40}, ${Math.random()*0.04})`",
          "  ctx.fillRect(Math.random()*1080, Math.random()*1440, 1, 1)",
          "}"
        ]
      },

      "cover": {
        "layout": "center_vertical",
        "padding": { "top": 280, "left": 120, "right": 120, "bottom": 200 },
        "decorLine": {
          "description": "标题上方一条细装饰线",
          "x": 480, "y": 320, "width": 120, "height": 1.5,
          "color": "#c4a882"
        },
        "title": {
          "font": "bold 52px 'Noto Serif SC', 'Source Han Serif CN', 'SimSun', serif",
          "fallbackFont": "bold 52px serif",
          "color": "#2c2c2c",
          "align": "center",
          "y": 580,
          "lineHeight": 78,
          "maxWidth": 840,
          "letterSpacing": 4
        },
        "subtitle": {
          "font": "300 28px 'Noto Sans SC', 'Microsoft YaHei', sans-serif",
          "fallbackFont": "300 28px sans-serif",
          "color": "#8a7f72",
          "align": "center",
          "y": 750,
          "maxWidth": 700
        },
        "authorTag": {
          "font": "24px 'Noto Sans SC', sans-serif",
          "color": "#a09890",
          "align": "center",
          "y": 1250,
          "prefix": "✦ ",
          "suffix": " ✦"
        },
        "bottomBorder": {
          "description": "底部装饰细线",
          "y": 1320, "xStart": 440, "xEnd": 640,
          "strokeWidth": 1, "color": "#d8d0c4"
        }
      },

      "content": {
        "layout": "top_aligned",
        "padding": { "top": 100, "left": 100, "right": 100, "bottom": 120 },
        "pageIndicator": {
          "font": "italic 22px 'Noto Serif SC', serif",
          "color": "#c4a882",
          "position": { "x": 540, "y": 60 },
          "format": "— {n} —"
        },
        "body": {
          "font": "28px 'Noto Sans SC', 'Microsoft YaHei', sans-serif",
          "fallbackFont": "28px sans-serif",
          "color": "#2c2c2c",
          "lineHeight": 52,
          "paragraphSpacing": 32,
          "maxWidth": 880,
          "textIndent": 56,
          "startY": 160
        },
        "quoteBlock": {
          "description": "用于突出显示引用语句",
          "leftBorderX": 90,
          "leftBorderWidth": 3,
          "leftBorderColor": "#c4a882",
          "textIndent": 30,
          "font": "italic 26px 'Noto Serif SC', serif",
          "color": "#6b6560"
        },
        "footerLine": {
          "y": 1380,
          "xStart": 100, "xEnd": 980,
          "strokeWidth": 0.5, "color": "#d8d0c4"
        }
      },

      "ending": {
        "layout": "center_vertical",
        "endingText": "感谢阅读",
        "endingTextEn": "Thanks for reading",
        "endingEmoji": "🤍",
        "title": {
          "font": "bold 44px 'Noto Serif SC', serif",
          "color": "#2c2c2c",
          "y": 600
        },
        "subtitle": {
          "font": "24px 'Noto Sans SC', sans-serif",
          "color": "#8a7f72",
          "y": 680
        },
        "cta": {
          "text": "点赞 ❤️ 收藏 ⭐ 关注我",
          "font": "26px 'Noto Sans SC', sans-serif",
          "color": "#c4a882",
          "y": 780,
          "boxPadding": { "h": 20, "v": 14 },
          "boxRadius": 30,
          "boxBorder": { "width": 1.5, "color": "#c4a882" }
        },
        "accountInfo": {
          "font": "22px 'Noto Sans SC', sans-serif",
          "color": "#a09890",
          "y": 900
        }
      }
    },

    {
      "id": "fresh_cute",
      "name": "清新可爱",
      "nameEn": "Fresh & Cute",
      "icon": "🌸",
      "bestFor": ["日常分享", "美食探店", "手帐", "少女心", "萌宠", "好物推荐"],
      "mood": "甜甜的、粉嫩的、有活力，像一块草莓蛋糕",
      "canvas": { "width": 1080, "height": 1440 },

      "colorPalette": {
        "primary": "#ff85a2",
        "secondary": "#ffc3d4",
        "accent": "#ffb347",
        "background": "#fff5f7",
        "backgroundAlt": "#ffeef2",
        "text": "#4a3540",
        "textLight": "#8b6f7f",
        "textMuted": "#c4a0b0",
        "border": "#ffd6e0",
        "highlight": "#fff0b3",
        "green": "#7ecba1",
        "blue": "#87ceeb",
        "purple": "#c9a0dc"
      },

      "background": {
        "type": "gradient_with_shapes",
        "gradient": {
          "type": "linear",
          "direction": "top_to_bottom",
          "stops": [
            { "offset": 0, "color": "#fff5f7" },
            { "offset": 0.5, "color": "#ffeef2" },
            { "offset": 1, "color": "#fff0e6" }
          ]
        },
        "decorations": [
          {
            "type": "circle",
            "description": "右上角大圆形装饰",
            "x": 980, "y": -60, "radius": 200,
            "fillColor": "rgba(255,179,71,0.08)"
          },
          {
            "type": "circle",
            "description": "左下角圆形装饰",
            "x": 50, "y": 1380, "radius": 160,
            "fillColor": "rgba(255,133,162,0.06)"
          },
          {
            "type": "dots_pattern",
            "description": "随机小圆点装饰",
            "count": 15,
            "radiusRange": [3, 8],
            "colors": ["rgba(255,133,162,0.12)", "rgba(255,179,71,0.12)", "rgba(126,203,161,0.12)"],
            "region": { "x": 0, "y": 0, "width": 1080, "height": 1440 }
          }
        ]
      },

      "cover": {
        "layout": "center_with_frame",
        "padding": { "top": 180, "left": 80, "right": 80, "bottom": 160 },
        "frame": {
          "description": "圆角矩形白色卡片框",
          "x": 60, "y": 160, "width": 960, "height": 1120,
          "radius": 32,
          "fillColor": "rgba(255,255,255,0.85)",
          "shadow": { "color": "rgba(255,133,162,0.15)", "blur": 30, "offsetY": 8 }
        },
        "topEmoji": {
          "description": "标题上方大 emoji",
          "font": "72px sans-serif",
          "y": 350,
          "align": "center"
        },
        "title": {
          "font": "bold 48px 'Noto Sans SC', 'Microsoft YaHei', sans-serif",
          "fallbackFont": "bold 48px sans-serif",
          "color": "#ff85a2",
          "align": "center",
          "y": 540,
          "lineHeight": 72,
          "maxWidth": 800,
          "letterSpacing": 2
        },
        "subtitle": {
          "font": "26px 'Noto Sans SC', sans-serif",
          "color": "#8b6f7f",
          "align": "center",
          "y": 720,
          "maxWidth": 700
        },
        "tagPills": {
          "description": "标签胶囊按钮排列",
          "y": 860,
          "font": "22px 'Noto Sans SC', sans-serif",
          "textColor": "#ff85a2",
          "bgColor": "rgba(255,133,162,0.1)",
          "borderColor": "rgba(255,133,162,0.3)",
          "borderRadius": 20,
          "padding": { "h": 18, "v": 8 },
          "gap": 12
        },
        "bottomDecor": {
          "description": "底部波浪线装饰",
          "type": "wavy_line",
          "y": 1200,
          "color": "#ffd6e0",
          "amplitude": 8,
          "wavelength": 60,
          "strokeWidth": 2
        }
      },

      "content": {
        "layout": "card_in_card",
        "padding": { "top": 80, "left": 80, "right": 80, "bottom": 100 },
        "innerCard": {
          "x": 50, "y": 50, "width": 980, "height": 1340,
          "radius": 24,
          "fillColor": "rgba(255,255,255,0.9)",
          "shadow": { "color": "rgba(255,133,162,0.1)", "blur": 20, "offsetY": 4 }
        },
        "sectionTitle": {
          "font": "bold 32px 'Noto Sans SC', sans-serif",
          "color": "#ff85a2",
          "underline": { "color": "rgba(255,179,71,0.3)", "height": 10, "offsetY": 4 }
        },
        "body": {
          "font": "27px 'Noto Sans SC', 'Microsoft YaHei', sans-serif",
          "fallbackFont": "27px sans-serif",
          "color": "#4a3540",
          "lineHeight": 50,
          "paragraphSpacing": 28,
          "maxWidth": 860,
          "startY": 140
        },
        "bulletStyle": {
          "type": "emoji_bullet",
          "emojis": ["🌸", "✨", "💕", "🎀", "🍰"],
          "indent": 40
        },
        "numberBadge": {
          "description": "用于列表编号的圆形徽章",
          "radius": 18,
          "bgColor": "#ff85a2",
          "textColor": "#ffffff",
          "font": "bold 20px sans-serif"
        }
      },

      "ending": {
        "layout": "center_cute",
        "endingText": "看到这里的都是小可爱",
        "endingEmoji": "💕",
        "title": {
          "font": "bold 42px 'Noto Sans SC', sans-serif",
          "color": "#ff85a2",
          "y": 550
        },
        "divider": {
          "type": "emoji_row",
          "emojis": "🌸✨💕✨🌸",
          "font": "32px sans-serif",
          "y": 650
        },
        "cta": {
          "text": "喜欢就点赞收藏吧 ～",
          "font": "28px 'Noto Sans SC', sans-serif",
          "color": "#ffffff",
          "y": 760,
          "bgColor": "#ff85a2",
          "bgRadius": 30,
          "bgPadding": { "h": 36, "v": 16 },
          "shadow": { "color": "rgba(255,133,162,0.3)", "blur": 12, "offsetY": 4 }
        },
        "socialIcons": {
          "y": 880,
          "items": [
            { "emoji": "❤️", "label": "点赞", "color": "#ff85a2" },
            { "emoji": "⭐", "label": "收藏", "color": "#ffb347" },
            { "emoji": "💬", "label": "评论", "color": "#7ecba1" },
            { "emoji": "➕", "label": "关注", "color": "#87ceeb" }
          ],
          "gap": 100,
          "font": "20px 'Noto Sans SC', sans-serif"
        }
      }
    },

    {
      "id": "premium_business",
      "name": "高级感商务",
      "nameEn": "Premium Business",
      "icon": "💎",
      "bestFor": ["职场干货", "商业分析", "理财投资", "科技资讯", "行业报告", "副业攻略"],
      "mood": "专业、有质感、克制的奢华感，像一份精致的企业年报",
      "canvas": { "width": 1080, "height": 1440 },

      "colorPalette": {
        "primary": "#1a1a2e",
        "secondary": "#16213e",
        "accent": "#c9a96e",
        "accentLight": "#dfc08a",
        "background": "#1a1a2e",
        "backgroundAlt": "#16213e",
        "text": "#f0ece4",
        "textLight": "#b8b0a0",
        "textMuted": "#7a7468",
        "border": "#c9a96e",
        "surface": "rgba(255,255,255,0.05)",
        "surfaceHover": "rgba(255,255,255,0.08)"
      },

      "background": {
        "type": "dark_gradient_with_accents",
        "gradient": {
          "type": "linear",
          "direction": "top_left_to_bottom_right",
          "stops": [
            { "offset": 0, "color": "#1a1a2e" },
            { "offset": 0.4, "color": "#16213e" },
            { "offset": 1, "color": "#0f0f1e" }
          ]
        },
        "decorations": [
          {
            "type": "corner_accent",
            "description": "左上角 L 型金色装饰线",
            "lines": [
              { "x1": 60, "y1": 60, "x2": 200, "y2": 60, "strokeWidth": 2, "color": "#c9a96e" },
              { "x1": 60, "y1": 60, "x2": 60, "y2": 200, "strokeWidth": 2, "color": "#c9a96e" }
            ]
          },
          {
            "type": "corner_accent",
            "description": "右下角 L 型金色装饰线",
            "lines": [
              { "x1": 880, "y1": 1380, "x2": 1020, "y2": 1380, "strokeWidth": 2, "color": "#c9a96e" },
              { "x1": 1020, "y1": 1240, "x2": 1020, "y2": 1380, "strokeWidth": 2, "color": "#c9a96e" }
            ]
          },
          {
            "type": "subtle_grid",
            "description": "极低透明度网格线，增加质感",
            "spacing": 80,
            "strokeWidth": 0.3,
            "color": "rgba(201,169,110,0.06)"
          }
        ]
      },

      "cover": {
        "layout": "left_aligned_premium",
        "padding": { "top": 200, "left": 100, "right": 100, "bottom": 200 },
        "topLabel": {
          "description": "顶部金色分类标签",
          "font": "500 22px 'Noto Sans SC', sans-serif",
          "color": "#c9a96e",
          "y": 280,
          "x": 100,
          "letterSpacing": 6,
          "text": "BUSINESS INSIGHT"
        },
        "goldLine": {
          "x": 100, "y": 340, "width": 60, "height": 3,
          "color": "#c9a96e"
        },
        "title": {
          "font": "bold 50px 'Noto Sans SC', 'Microsoft YaHei', sans-serif",
          "fallbackFont": "bold 50px sans-serif",
          "color": "#f0ece4",
          "align": "left",
          "x": 100,
          "y": 440,
          "lineHeight": 75,
          "maxWidth": 880,
          "letterSpacing": 3
        },
        "subtitle": {
          "font": "300 26px 'Noto Sans SC', sans-serif",
          "color": "#b8b0a0",
          "align": "left",
          "x": 100,
          "y": 680,
          "maxWidth": 750
        },
        "bottomBar": {
          "description": "底部金色信息条",
          "y": 1280,
          "x": 100,
          "font": "20px 'Noto Sans SC', sans-serif",
          "color": "#7a7468",
          "separatorColor": "#c9a96e",
          "items": ["作者名", "日期", "分类"]
        }
      },

      "content": {
        "layout": "structured_dark",
        "padding": { "top": 80, "left": 100, "right": 100, "bottom": 100 },
        "sectionTitle": {
          "font": "bold 30px 'Noto Sans SC', sans-serif",
          "color": "#c9a96e",
          "leftBar": { "width": 4, "height": 28, "color": "#c9a96e", "marginRight": 16 }
        },
        "body": {
          "font": "26px 'Noto Sans SC', 'Microsoft YaHei', sans-serif",
          "fallbackFont": "26px sans-serif",
          "color": "#f0ece4",
          "lineHeight": 48,
          "paragraphSpacing": 30,
          "maxWidth": 880,
          "startY": 140
        },
        "keyPoint": {
          "description": "重点卡片（深色半透明背景）",
          "bgColor": "rgba(201,169,110,0.08)",
          "borderLeft": { "width": 3, "color": "#c9a96e" },
          "borderRadius": 8,
          "padding": { "h": 24, "v": 20 },
          "font": "26px 'Noto Sans SC', sans-serif",
          "color": "#dfc08a"
        },
        "divider": {
          "type": "gold_dots",
          "description": "三个金色小圆点分隔符",
          "dotRadius": 3,
          "dotColor": "#c9a96e",
          "dotGap": 20,
          "y": "dynamic"
        },
        "dataCard": {
          "description": "数据展示卡片（用于数字、百分比等）",
          "bgColor": "rgba(255,255,255,0.04)",
          "borderRadius": 12,
          "border": { "width": 1, "color": "rgba(201,169,110,0.2)" },
          "numberFont": "bold 40px 'Noto Sans SC', sans-serif",
          "numberColor": "#c9a96e",
          "labelFont": "20px 'Noto Sans SC', sans-serif",
          "labelColor": "#b8b0a0"
        }
      },

      "ending": {
        "layout": "minimal_premium",
        "endingText": "感谢阅读",
        "endingTextEn": "THANKS FOR READING",
        "title": {
          "font": "300 40px 'Noto Sans SC', sans-serif",
          "color": "#f0ece4",
          "y": 580,
          "letterSpacing": 8
        },
        "enTitle": {
          "font": "300 18px sans-serif",
          "color": "#7a7468",
          "y": 640,
          "letterSpacing": 6
        },
        "goldLine": {
          "x": 460, "y": 700, "width": 160, "height": 1.5,
          "color": "#c9a96e"
        },
        "cta": {
          "text": "关注获取更多干货",
          "font": "24px 'Noto Sans SC', sans-serif",
          "color": "#c9a96e",
          "y": 770,
          "boxPadding": { "h": 32, "v": 14 },
          "boxRadius": 4,
          "boxBorder": { "width": 1, "color": "#c9a96e" }
        }
      }
    },

    {
      "id": "ins_aesthetic",
      "name": "INS风",
      "nameEn": "Instagram Aesthetic",
      "icon": "📷",
      "bestFor": ["穿搭OOTD", "生活方式", "旅行日记", "咖啡下午茶", "家居美学", "vlog文案"],
      "mood": "慵懒、高级感、大片留白，像一杯拿铁的午后时光",
      "canvas": { "width": 1080, "height": 1440 },

      "colorPalette": {
        "primary": "#3d3d3d",
        "secondary": "#7c7c7c",
        "accent": "#c2a278",
        "background": "#f5e6d3",
        "backgroundAlt": "#ede0d0",
        "text": "#3d3d3d",
        "textLight": "#7c7c7c",
        "textMuted": "#aaa094",
        "border": "#d4c4ae",
        "cream": "#faf4ec",
        "sage": "#b5c4a8",
        "dustyRose": "#d4a0a0"
      },

      "background": {
        "type": "warm_gradient",
        "gradient": {
          "type": "linear",
          "direction": "top_to_bottom",
          "stops": [
            { "offset": 0, "color": "#f5e6d3" },
            { "offset": 0.6, "color": "#ede0d0" },
            { "offset": 1, "color": "#e8d8c4" }
          ]
        },
        "decorations": [
          {
            "type": "film_border",
            "description": "仿胶片边框效果（上下两条细线）",
            "topY": 40, "bottomY": 1400,
            "xStart": 60, "xEnd": 1020,
            "strokeWidth": 0.5, "color": "#d4c4ae"
          },
          {
            "type": "grain_overlay",
            "description": "胶片颗粒感叠加（随机半透明点）",
            "density": 5000,
            "alphaRange": [0.01, 0.03],
            "colorBase": [180, 160, 140]
          }
        ]
      },

      "cover": {
        "layout": "centered_minimal",
        "padding": { "top": 300, "left": 140, "right": 140, "bottom": 250 },
        "topDate": {
          "description": "顶部日期/期刊风格文字",
          "font": "italic 20px 'Georgia', serif",
          "fallbackFont": "italic 20px serif",
          "color": "#aaa094",
          "y": 200,
          "align": "center",
          "format": "Vol.{n} · {date}"
        },
        "title": {
          "font": "300 46px 'Noto Serif SC', 'SimSun', serif",
          "fallbackFont": "300 46px serif",
          "color": "#3d3d3d",
          "align": "center",
          "y": 580,
          "lineHeight": 70,
          "maxWidth": 800,
          "letterSpacing": 6
        },
        "dividerDot": {
          "description": "标题下方单个装饰圆点",
          "x": 540, "y": 720,
          "radius": 4, "color": "#c2a278"
        },
        "subtitle": {
          "font": "italic 24px 'Georgia', serif",
          "fallbackFont": "italic 24px serif",
          "color": "#7c7c7c",
          "align": "center",
          "y": 790,
          "maxWidth": 650
        },
        "bottomTag": {
          "font": "18px 'Noto Sans SC', sans-serif",
          "color": "#aaa094",
          "y": 1280,
          "align": "center",
          "letterSpacing": 4
        }
      },

      "content": {
        "layout": "editorial_clean",
        "padding": { "top": 100, "left": 120, "right": 120, "bottom": 120 },
        "dropCap": {
          "description": "段落首字母大写装饰（内容卡第一段可选）",
          "font": "italic 80px 'Georgia', serif",
          "color": "#c2a278",
          "lineOffset": -10
        },
        "body": {
          "font": "26px 'Noto Sans SC', 'Microsoft YaHei', sans-serif",
          "fallbackFont": "26px sans-serif",
          "color": "#3d3d3d",
          "lineHeight": 50,
          "paragraphSpacing": 36,
          "maxWidth": 840,
          "startY": 140
        },
        "pullQuote": {
          "description": "居中突出引述",
          "font": "italic 30px 'Noto Serif SC', serif",
          "color": "#7c7c7c",
          "align": "center",
          "topLine": { "width": 40, "color": "#c2a278" },
          "bottomLine": { "width": 40, "color": "#c2a278" },
          "marginTop": 40, "marginBottom": 40
        },
        "imageFrame": {
          "description": "图片区域占位框（模拟胶片照片）",
          "borderWidth": 1,
          "borderColor": "#d4c4ae",
          "padding": 8,
          "shadow": false,
          "captionFont": "italic 18px serif",
          "captionColor": "#aaa094"
        }
      },

      "ending": {
        "layout": "film_ending",
        "endingText": "ᐟ",
        "title": {
          "font": "300 36px 'Noto Serif SC', serif",
          "color": "#3d3d3d",
          "y": 600,
          "letterSpacing": 4
        },
        "filmStrip": {
          "description": "仿胶片底部穿孔装饰",
          "y": 700,
          "holeCount": 12,
          "holeWidth": 28, "holeHeight": 20,
          "holeRadius": 4,
          "holeColor": "rgba(0,0,0,0.04)",
          "gap": 56
        },
        "cta": {
          "text": "follow for more",
          "font": "italic 22px 'Georgia', serif",
          "color": "#7c7c7c",
          "y": 800
        },
        "signature": {
          "description": "底部手写签名风格",
          "font": "italic 28px 'Georgia', serif",
          "color": "#c2a278",
          "y": 900
        }
      }
    },

    {
      "id": "warm_healing",
      "name": "暖色治愈",
      "nameEn": "Warm Healing",
      "icon": "🌅",
      "bestFor": ["情感治愈", "心理疏导", "正能量语录", "晚安问候", "自我关怀", "冥想心灵"],
      "mood": "温暖的、柔软的、被拥抱的感觉，像冬日暖阳洒在脸上",
      "canvas": { "width": 1080, "height": 1440 },

      "colorPalette": {
        "primary": "#ff6b35",
        "secondary": "#ff9a5c",
        "accent": "#ffd166",
        "background": "#fff8f0",
        "backgroundAlt": "#fff0e0",
        "text": "#5c3d2e",
        "textLight": "#8b6754",
        "textMuted": "#c49a82",
        "border": "#ffd6b8",
        "warmWhite": "#fffaf5",
        "peach": "#ffb89a",
        "coral": "#ff8a80"
      },

      "background": {
        "type": "warm_radial_gradient",
        "gradient": {
          "type": "radial",
          "centerX": 540, "centerY": 720,
          "radius": 900,
          "stops": [
            { "offset": 0, "color": "#fff8f0" },
            { "offset": 0.4, "color": "#fff0e0" },
            { "offset": 0.8, "color": "#ffe8d0" },
            { "offset": 1, "color": "#ffddc0" }
          ]
        },
        "decorations": [
          {
            "type": "glow_circles",
            "description": "多个暖色光圈装饰",
            "circles": [
              { "x": 200, "y": 200, "radius": 300, "color": "rgba(255,209,102,0.06)" },
              { "x": 900, "y": 400, "radius": 250, "color": "rgba(255,107,53,0.04)" },
              { "x": 400, "y": 1200, "radius": 350, "color": "rgba(255,154,92,0.05)" }
            ]
          },
          {
            "type": "soft_stars",
            "description": "柔和小星星装饰",
            "count": 8,
            "sizeRange": [4, 10],
            "color": "rgba(255,209,102,0.2)",
            "region": { "x": 0, "y": 0, "width": 1080, "height": 1440 }
          }
        ]
      },

      "cover": {
        "layout": "warm_center",
        "padding": { "top": 250, "left": 100, "right": 100, "bottom": 200 },
        "sunIcon": {
          "description": "顶部太阳/光芒装饰",
          "emoji": "☀️",
          "font": "64px sans-serif",
          "y": 300,
          "align": "center"
        },
        "title": {
          "font": "bold 48px 'Noto Sans SC', 'Microsoft YaHei', sans-serif",
          "fallbackFont": "bold 48px sans-serif",
          "color": "#5c3d2e",
          "align": "center",
          "y": 540,
          "lineHeight": 72,
          "maxWidth": 840,
          "letterSpacing": 2
        },
        "warmLine": {
          "description": "标题下方渐变装饰线",
          "y": 700,
          "xStart": 380, "xEnd": 700,
          "gradient": {
            "stops": [
              { "offset": 0, "color": "transparent" },
              { "offset": 0.3, "color": "#ff9a5c" },
              { "offset": 0.7, "color": "#ffd166" },
              { "offset": 1, "color": "transparent" }
            ]
          },
          "height": 3
        },
        "subtitle": {
          "font": "26px 'Noto Sans SC', sans-serif",
          "color": "#8b6754",
          "align": "center",
          "y": 770,
          "maxWidth": 700
        },
        "bottomWarm": {
          "description": "底部暖色渐变半透明条",
          "y": 1200,
          "height": 240,
          "gradient": {
            "stops": [
              { "offset": 0, "color": "rgba(255,221,192,0)" },
              { "offset": 1, "color": "rgba(255,221,192,0.3)" }
            ]
          }
        }
      },

      "content": {
        "layout": "warm_flowing",
        "padding": { "top": 80, "left": 90, "right": 90, "bottom": 100 },
        "body": {
          "font": "28px 'Noto Sans SC', 'Microsoft YaHei', sans-serif",
          "fallbackFont": "28px sans-serif",
          "color": "#5c3d2e",
          "lineHeight": 52,
          "paragraphSpacing": 32,
          "maxWidth": 900,
          "startY": 120
        },
        "warmQuote": {
          "description": "治愈语录高亮卡片",
          "bgGradient": {
            "stops": [
              { "offset": 0, "color": "rgba(255,209,102,0.12)" },
              { "offset": 1, "color": "rgba(255,154,92,0.08)" }
            ]
          },
          "borderRadius": 16,
          "padding": { "h": 28, "v": 24 },
          "leftEmoji": "🧡",
          "font": "italic 27px 'Noto Serif SC', serif",
          "color": "#5c3d2e"
        },
        "divider": {
          "type": "gradient_line",
          "colors": ["transparent", "#ffd166", "#ff9a5c", "transparent"],
          "height": 1.5
        },
        "heartBullet": {
          "description": "爱心符号列表",
          "symbol": "🧡",
          "indent": 40,
          "symbolSize": "24px"
        }
      },

      "ending": {
        "layout": "warm_hug",
        "endingText": "愿你被世界温柔以待",
        "endingEmoji": "🌅",
        "title": {
          "font": "bold 40px 'Noto Sans SC', sans-serif",
          "color": "#5c3d2e",
          "y": 560
        },
        "subtitle": {
          "font": "26px 'Noto Sans SC', sans-serif",
          "color": "#8b6754",
          "y": 640,
          "text": "每天一点暖，治愈每一天"
        },
        "cta": {
          "text": "点赞传递温暖 🧡",
          "font": "26px 'Noto Sans SC', sans-serif",
          "color": "#ffffff",
          "y": 760,
          "bgGradient": {
            "type": "linear",
            "stops": [
              { "offset": 0, "color": "#ff9a5c" },
              { "offset": 1, "color": "#ff6b35" }
            ]
          },
          "bgRadius": 30,
          "bgPadding": { "h": 36, "v": 16 },
          "shadow": { "color": "rgba(255,107,53,0.3)", "blur": 16, "offsetY": 6 }
        }
      }
    },

    {
      "id": "dark_cool",
      "name": "暗黑酷炫",
      "nameEn": "Dark Cool",
      "icon": "🖤",
      "bestFor": ["摄影作品", "音乐推荐", "潮流文化", "电影推荐", "深夜电台", "个性语录"],
      "mood": "冷酷、神秘、有态度，像深夜城市的霓虹灯光",
      "canvas": { "width": 1080, "height": 1440 },

      "colorPalette": {
        "primary": "#0f0f0f",
        "secondary": "#1a1a1a",
        "accent": "#00d4ff",
        "accentAlt": "#b44dff",
        "accentWarm": "#ff3366",
        "background": "#0f0f0f",
        "backgroundAlt": "#1a1a1a",
        "text": "#e8e8e8",
        "textLight": "#999999",
        "textMuted": "#555555",
        "border": "#333333",
        "neon": "#00d4ff",
        "neonPurple": "#b44dff",
        "neonPink": "#ff3366"
      },

      "background": {
        "type": "dark_with_neon_glow",
        "color": "#0f0f0f",
        "decorations": [
          {
            "type": "gradient_overlay",
            "description": "左上角紫色辉光",
            "gradient": {
              "type": "radial",
              "centerX": 0, "centerY": 0, "radius": 600,
              "stops": [
                { "offset": 0, "color": "rgba(180,77,255,0.08)" },
                { "offset": 1, "color": "transparent" }
              ]
            }
          },
          {
            "type": "gradient_overlay",
            "description": "右下角蓝色辉光",
            "gradient": {
              "type": "radial",
              "centerX": 1080, "centerY": 1440, "radius": 600,
              "stops": [
                { "offset": 0, "color": "rgba(0,212,255,0.06)" },
                { "offset": 1, "color": "transparent" }
              ]
            }
          },
          {
            "type": "scanlines",
            "description": "CRT 扫描线效果",
            "lineSpacing": 4,
            "lineColor": "rgba(255,255,255,0.01)",
            "lineHeight": 1
          },
          {
            "type": "noise_overlay",
            "description": "暗色噪点叠加",
            "density": 6000,
            "alphaRange": [0.02, 0.05],
            "colorBase": [20, 20, 30]
          }
        ]
      },

      "cover": {
        "layout": "bold_dark",
        "padding": { "top": 200, "left": 80, "right": 80, "bottom": 200 },
        "glitchLine": {
          "description": "标题上方故障艺术装饰线（RGB 偏移效果）",
          "y": 360,
          "x": 80, "width": 200,
          "layers": [
            { "color": "#ff3366", "offsetX": -2, "offsetY": -1 },
            { "color": "#00d4ff", "offsetX": 2, "offsetY": 1 },
            { "color": "#ffffff", "offsetX": 0, "offsetY": 0 }
          ],
          "height": 3
        },
        "title": {
          "font": "900 56px 'Noto Sans SC', 'Microsoft YaHei', sans-serif",
          "fallbackFont": "900 56px sans-serif",
          "color": "#ffffff",
          "align": "left",
          "x": 80,
          "y": 500,
          "lineHeight": 80,
          "maxWidth": 920,
          "letterSpacing": 2,
          "shadow": [
            { "color": "rgba(0,212,255,0.5)", "offsetX": 0, "offsetY": 0, "blur": 20 },
            { "color": "rgba(180,77,255,0.3)", "offsetX": 2, "offsetY": 2, "blur": 10 }
          ]
        },
        "subtitle": {
          "font": "300 24px 'Noto Sans SC', sans-serif",
          "color": "#999999",
          "align": "left",
          "x": 80,
          "y": 720,
          "maxWidth": 700
        },
        "neonTag": {
          "description": "霓虹发光标签",
          "font": "bold 20px 'Noto Sans SC', sans-serif",
          "color": "#00d4ff",
          "y": 850,
          "x": 80,
          "bgColor": "rgba(0,212,255,0.1)",
          "borderColor": "#00d4ff",
          "borderRadius": 4,
          "padding": { "h": 16, "v": 8 },
          "glow": { "color": "rgba(0,212,255,0.3)", "blur": 10 }
        },
        "bottomLine": {
          "y": 1340,
          "xStart": 80, "xEnd": 1000,
          "gradient": {
            "stops": [
              { "offset": 0, "color": "#ff3366" },
              { "offset": 0.5, "color": "#b44dff" },
              { "offset": 1, "color": "#00d4ff" }
            ]
          },
          "height": 2
        }
      },

      "content": {
        "layout": "dark_structured",
        "padding": { "top": 80, "left": 80, "right": 80, "bottom": 100 },
        "sectionTitle": {
          "font": "bold 30px 'Noto Sans SC', sans-serif",
          "color": "#00d4ff",
          "glow": { "color": "rgba(0,212,255,0.4)", "blur": 8 }
        },
        "body": {
          "font": "26px 'Noto Sans SC', 'Microsoft YaHei', sans-serif",
          "fallbackFont": "26px sans-serif",
          "color": "#e8e8e8",
          "lineHeight": 48,
          "paragraphSpacing": 28,
          "maxWidth": 920,
          "startY": 130
        },
        "codeBlock": {
          "description": "代码/技术内容展示块",
          "bgColor": "rgba(255,255,255,0.04)",
          "borderLeft": { "width": 3, "color": "#00d4ff" },
          "borderRadius": 4,
          "padding": { "h": 20, "v": 16 },
          "font": "24px 'Consolas', 'Courier New', monospace",
          "color": "#00d4ff"
        },
        "highlightText": {
          "description": "文字高亮效果",
          "bgColor": "rgba(180,77,255,0.15)",
          "padding": { "h": 6, "v": 2 },
          "borderRadius": 3
        },
        "bulletStyle": {
          "type": "neon_dash",
          "symbol": "▸",
          "color": "#00d4ff",
          "indent": 36
        }
      },

      "ending": {
        "layout": "neon_ending",
        "endingText": "THE END",
        "title": {
          "font": "900 48px sans-serif",
          "color": "#ffffff",
          "y": 580,
          "letterSpacing": 12,
          "shadow": [
            { "color": "rgba(0,212,255,0.6)", "offsetX": 0, "offsetY": 0, "blur": 30 },
            { "color": "rgba(180,77,255,0.4)", "offsetX": 0, "offsetY": 0, "blur": 60 }
          ]
        },
        "neonLine": {
          "y": 680,
          "xStart": 340, "xEnd": 740,
          "gradient": {
            "stops": [
              { "offset": 0, "color": "#ff3366" },
              { "offset": 0.5, "color": "#b44dff" },
              { "offset": 1, "color": "#00d4ff" }
            ]
          },
          "height": 2,
          "glow": { "blur": 8 }
        },
        "cta": {
          "text": "FOLLOW ME",
          "font": "bold 22px sans-serif",
          "color": "#00d4ff",
          "y": 760,
          "letterSpacing": 6,
          "boxBorder": { "width": 1, "color": "#00d4ff" },
          "boxRadius": 0,
          "boxPadding": { "h": 32, "v": 12 },
          "glow": { "color": "rgba(0,212,255,0.3)", "blur": 10 }
        }
      }
    },

    {
      "id": "chinese_retro",
      "name": "国潮复古",
      "nameEn": "Chinese Retro",
      "icon": "🏮",
      "bestFor": ["国风文化", "传统节日", "汉服", "书法", "茶道", "诗词", "历史故事"],
      "mood": "古典韵味、文化自信、浓烈但不庸俗，像一幅水墨画遇上波普",
      "canvas": { "width": 1080, "height": 1440 },

      "colorPalette": {
        "primary": "#c41e3a",
        "secondary": "#8b0000",
        "accent": "#d4a840",
        "background": "#f5f0e8",
        "backgroundAlt": "#ece5d8",
        "text": "#2d1810",
        "textLight": "#5a4030",
        "textMuted": "#8b7355",
        "border": "#c41e3a",
        "gold": "#d4a840",
        "cream": "#f5f0e8",
        "inkBlack": "#1a1008",
        "vermillion": "#e54d42"
      },

      "background": {
        "type": "paper_with_border",
        "color": "#f5f0e8",
        "decorations": [
          {
            "type": "outer_border",
            "description": "红色外边框（双线）",
            "outerRect": { "x": 30, "y": 30, "width": 1020, "height": 1380, "strokeWidth": 3, "color": "#c41e3a" },
            "innerRect": { "x": 40, "y": 40, "width": 1000, "height": 1360, "strokeWidth": 1, "color": "#c41e3a" }
          },
          {
            "type": "corner_ornaments",
            "description": "四角回纹装饰（简化几何形式）",
            "size": 40,
            "color": "#c41e3a",
            "corners": ["topLeft", "topRight", "bottomLeft", "bottomRight"],
            "implementation": "绘制小型回字纹（由嵌套矩形线条组成）"
          },
          {
            "type": "paper_texture",
            "description": "宣纸纹理效果",
            "density": 10000,
            "alphaRange": [0.01, 0.03],
            "colorBase": [200, 185, 160]
          }
        ]
      },

      "cover": {
        "layout": "vertical_chinese",
        "padding": { "top": 180, "left": 100, "right": 100, "bottom": 160 },
        "topSeal": {
          "description": "顶部红色印章/方印装饰",
          "type": "square_seal",
          "x": 480, "y": 200,
          "size": 120,
          "bgColor": "#c41e3a",
          "text": "语",
          "textFont": "bold 60px 'SimSun', serif",
          "textColor": "#f5f0e8",
          "rotation": -0.05
        },
        "title": {
          "font": "bold 54px 'Noto Serif SC', 'SimSun', serif",
          "fallbackFont": "bold 54px serif",
          "color": "#2d1810",
          "align": "center",
          "y": 550,
          "lineHeight": 82,
          "maxWidth": 800,
          "letterSpacing": 6
        },
        "verticalText": {
          "description": "右侧竖排小字（可选装饰，用于诗词等）",
          "font": "24px 'Noto Serif SC', serif",
          "color": "#8b7355",
          "x": 960,
          "startY": 400,
          "charSpacing": 36
        },
        "goldDivider": {
          "description": "金色分隔线",
          "y": 740,
          "xStart": 400, "xEnd": 680,
          "height": 2,
          "color": "#d4a840"
        },
        "subtitle": {
          "font": "26px 'Noto Serif SC', serif",
          "color": "#5a4030",
          "align": "center",
          "y": 810,
          "maxWidth": 650
        },
        "bottomSeal": {
          "description": "底部小印章装饰（椭圆形）",
          "type": "oval_seal",
          "x": 490, "y": 1200,
          "width": 100, "height": 50,
          "bgColor": "#c41e3a",
          "text": "品读",
          "textFont": "20px 'SimSun', serif",
          "textColor": "#f5f0e8"
        }
      },

      "content": {
        "layout": "classical_page",
        "padding": { "top": 100, "left": 100, "right": 100, "bottom": 120 },
        "sectionTitle": {
          "font": "bold 32px 'Noto Serif SC', serif",
          "color": "#c41e3a",
          "leftSeal": {
            "description": "标题左侧小红色方块",
            "size": 24, "color": "#c41e3a", "marginRight": 12
          }
        },
        "body": {
          "font": "27px 'Noto Serif SC', 'SimSun', serif",
          "fallbackFont": "27px serif",
          "color": "#2d1810",
          "lineHeight": 52,
          "paragraphSpacing": 32,
          "maxWidth": 860,
          "textIndent": 54,
          "startY": 160
        },
        "poemBlock": {
          "description": "诗词排版区块",
          "font": "30px 'Noto Serif SC', serif",
          "color": "#2d1810",
          "align": "center",
          "lineHeight": 56,
          "bgColor": "rgba(212,168,64,0.06)",
          "borderRadius": 8,
          "padding": { "h": 40, "v": 30 }
        },
        "redDot": {
          "description": "段落间红色圆点分隔",
          "radius": 5,
          "color": "#c41e3a",
          "align": "center"
        }
      },

      "ending": {
        "layout": "seal_ending",
        "endingText": "完",
        "title": {
          "font": "bold 80px 'Noto Serif SC', serif",
          "color": "#c41e3a",
          "y": 600,
          "border": {
            "type": "circle",
            "radius": 70,
            "strokeWidth": 3,
            "color": "#c41e3a"
          }
        },
        "subtitle": {
          "font": "24px 'Noto Serif SC', serif",
          "color": "#5a4030",
          "y": 740,
          "text": "- 品读经典 · 传承文化 -"
        },
        "cta": {
          "text": "关注 · 收藏 · 转发",
          "font": "24px 'Noto Serif SC', serif",
          "color": "#c41e3a",
          "y": 840,
          "letterSpacing": 4
        },
        "bottomOrnament": {
          "description": "底部云纹装饰（简化）",
          "type": "cloud_pattern",
          "y": 1200,
          "color": "rgba(196,30,58,0.1)",
          "count": 3,
          "implementation": "使用 bezierCurveTo 绘制简化的如意云纹"
        }
      }
    },

    {
      "id": "study_knowledge",
      "name": "学习干货",
      "nameEn": "Study/Knowledge",
      "icon": "📚",
      "bestFor": ["学习方法", "考试攻略", "知识科普", "效率工具", "读书笔记", "技能分享"],
      "mood": "清晰、有条理、实用至上，像一个精心排版的笔记本",
      "canvas": { "width": 1080, "height": 1440 },

      "colorPalette": {
        "primary": "#4a90d9",
        "secondary": "#2c6fbd",
        "accent": "#ff6b6b",
        "accentYellow": "#ffd93d",
        "accentGreen": "#6bcb77",
        "background": "#f8f9fc",
        "backgroundAlt": "#eef2f9",
        "text": "#2d3748",
        "textLight": "#5a6577",
        "textMuted": "#8e99a4",
        "border": "#d0dae8",
        "surface": "#ffffff",
        "surfaceAlt": "#f0f4fa"
      },

      "background": {
        "type": "notebook_style",
        "color": "#f8f9fc",
        "decorations": [
          {
            "type": "grid_lines",
            "description": "仿笔记本格线（水平线）",
            "startY": 0,
            "spacing": 48,
            "strokeWidth": 0.3,
            "color": "rgba(74,144,217,0.08)"
          },
          {
            "type": "margin_line",
            "description": "左侧红色竖线（仿笔记本装订线）",
            "x": 70,
            "strokeWidth": 1.5,
            "color": "rgba(255,107,107,0.15)"
          },
          {
            "type": "holes",
            "description": "左侧装订孔",
            "x": 35,
            "positions": [200, 500, 800, 1100],
            "radius": 10,
            "strokeWidth": 1.5,
            "strokeColor": "#d0dae8",
            "fillColor": "#f0f4fa"
          }
        ]
      },

      "cover": {
        "layout": "notebook_cover",
        "padding": { "top": 200, "left": 100, "right": 80, "bottom": 180 },
        "topBadge": {
          "description": "顶部分类徽章",
          "font": "bold 22px 'Noto Sans SC', sans-serif",
          "color": "#ffffff",
          "bgColor": "#4a90d9",
          "y": 260,
          "x": 540,
          "padding": { "h": 24, "v": 10 },
          "borderRadius": 20
        },
        "title": {
          "font": "bold 48px 'Noto Sans SC', 'Microsoft YaHei', sans-serif",
          "fallbackFont": "bold 48px sans-serif",
          "color": "#2d3748",
          "align": "center",
          "y": 500,
          "lineHeight": 72,
          "maxWidth": 860,
          "letterSpacing": 2
        },
        "highlightUnderline": {
          "description": "标题下方黄色高亮条",
          "color": "rgba(255,217,61,0.4)",
          "height": 14,
          "offsetY": -8
        },
        "subtitle": {
          "font": "26px 'Noto Sans SC', sans-serif",
          "color": "#5a6577",
          "align": "center",
          "y": 700,
          "maxWidth": 700
        },
        "keyPoints": {
          "description": "封面要点预览（3-4 个小标签）",
          "y": 860,
          "font": "22px 'Noto Sans SC', sans-serif",
          "items": [
            { "emoji": "📌", "bgColor": "rgba(255,107,107,0.1)", "textColor": "#ff6b6b" },
            { "emoji": "💡", "bgColor": "rgba(255,217,61,0.15)", "textColor": "#d4a800" },
            { "emoji": "✅", "bgColor": "rgba(107,203,119,0.1)", "textColor": "#6bcb77" }
          ],
          "borderRadius": 12,
          "padding": { "h": 16, "v": 8 },
          "gap": 16
        },
        "bottomInfo": {
          "font": "20px 'Noto Sans SC', sans-serif",
          "color": "#8e99a4",
          "y": 1260,
          "items": ["📖 干货分享", "⏱ 5分钟阅读", "💾 建议收藏"]
        }
      },

      "content": {
        "layout": "structured_notes",
        "padding": { "top": 60, "left": 90, "right": 80, "bottom": 80 },
        "sectionTitle": {
          "font": "bold 30px 'Noto Sans SC', sans-serif",
          "color": "#2d3748",
          "numberBadge": {
            "description": "编号圆形徽章",
            "radius": 20,
            "bgColor": "#4a90d9",
            "textColor": "#ffffff",
            "font": "bold 22px sans-serif",
            "marginRight": 14
          },
          "underline": { "color": "rgba(74,144,217,0.2)", "height": 8, "offsetY": 2 }
        },
        "body": {
          "font": "26px 'Noto Sans SC', 'Microsoft YaHei', sans-serif",
          "fallbackFont": "26px sans-serif",
          "color": "#2d3748",
          "lineHeight": 48,
          "paragraphSpacing": 24,
          "maxWidth": 880,
          "startY": 120
        },
        "tipBox": {
          "description": "提示框/重点框",
          "variants": {
            "important": {
              "bgColor": "rgba(255,107,107,0.08)",
              "borderLeft": { "width": 4, "color": "#ff6b6b" },
              "icon": "🔴",
              "titleColor": "#ff6b6b"
            },
            "tip": {
              "bgColor": "rgba(74,144,217,0.08)",
              "borderLeft": { "width": 4, "color": "#4a90d9" },
              "icon": "💡",
              "titleColor": "#4a90d9"
            },
            "success": {
              "bgColor": "rgba(107,203,119,0.08)",
              "borderLeft": { "width": 4, "color": "#6bcb77" },
              "icon": "✅",
              "titleColor": "#6bcb77"
            },
            "warning": {
              "bgColor": "rgba(255,217,61,0.1)",
              "borderLeft": { "width": 4, "color": "#ffd93d" },
              "icon": "⚠️",
              "titleColor": "#d4a800"
            }
          },
          "borderRadius": 8,
          "padding": { "h": 20, "v": 16 },
          "font": "25px 'Noto Sans SC', sans-serif"
        },
        "checkList": {
          "description": "勾选列表",
          "checkedSymbol": "☑",
          "uncheckedSymbol": "☐",
          "checkedColor": "#6bcb77",
          "uncheckedColor": "#8e99a4",
          "font": "25px 'Noto Sans SC', sans-serif",
          "indent": 40,
          "lineSpacing": 44
        },
        "codeInline": {
          "description": "内联代码样式",
          "bgColor": "rgba(74,144,217,0.08)",
          "textColor": "#2c6fbd",
          "font": "24px 'Consolas', 'Courier New', monospace",
          "padding": { "h": 8, "v": 3 },
          "borderRadius": 4
        },
        "stepFlow": {
          "description": "步骤流程图",
          "circleRadius": 16,
          "circleColor": "#4a90d9",
          "lineColor": "#d0dae8",
          "lineWidth": 2,
          "numberFont": "bold 18px sans-serif",
          "numberColor": "#ffffff",
          "labelFont": "24px 'Noto Sans SC', sans-serif",
          "labelColor": "#2d3748"
        },
        "progressBar": {
          "description": "进度条（用于展示掌握程度等）",
          "height": 12,
          "bgColor": "#eef2f9",
          "fillColor": "#4a90d9",
          "borderRadius": 6,
          "labelFont": "20px 'Noto Sans SC', sans-serif"
        }
      },

      "ending": {
        "layout": "summary_ending",
        "endingText": "全文总结",
        "title": {
          "font": "bold 38px 'Noto Sans SC', sans-serif",
          "color": "#2d3748",
          "y": 300
        },
        "summaryBox": {
          "description": "总结要点框",
          "x": 80, "y": 380, "width": 920,
          "bgColor": "#ffffff",
          "borderRadius": 16,
          "border": { "width": 2, "color": "#4a90d9" },
          "shadow": { "color": "rgba(74,144,217,0.15)", "blur": 20, "offsetY": 6 },
          "padding": { "h": 32, "v": 28 },
          "itemFont": "25px 'Noto Sans SC', sans-serif",
          "itemColor": "#2d3748",
          "itemBullet": "✅",
          "itemSpacing": 40
        },
        "cta": {
          "text": "💾 收藏备用 · ❤️ 点赞支持",
          "font": "26px 'Noto Sans SC', sans-serif",
          "color": "#ffffff",
          "bgColor": "#4a90d9",
          "y": 1000,
          "bgRadius": 28,
          "bgPadding": { "h": 36, "v": 14 },
          "shadow": { "color": "rgba(74,144,217,0.3)", "blur": 12, "offsetY": 4 }
        },
        "bottomNote": {
          "font": "20px 'Noto Sans SC', sans-serif",
          "color": "#8e99a4",
          "y": 1100,
          "text": "关注我，获取更多干货笔记 📚"
        }
      }
    }
  ],

  "sharedConfig": {
    "canvas": {
      "width": 1080,
      "height": 1440,
      "ratio": "3:4",
      "exportFormat": "image/png",
      "exportQuality": 1.0
    },
    "fonts": {
      "primary_serif": {
        "name": "Noto Serif SC",
        "fallback": "SimSun, STSong, serif",
        "source": "Google Fonts",
        "weights": [300, 400, 700],
        "use": "标题、引用、传统风格正文"
      },
      "primary_sans": {
        "name": "Noto Sans SC",
        "fallback": "Microsoft YaHei, PingFang SC, sans-serif",
        "source": "Google Fonts / System",
        "weights": [300, 400, 500, 700, 900],
        "use": "正文、标签、按钮、现代风格标题"
      },
      "decorative_serif": {
        "name": "Georgia",
        "fallback": "Times New Roman, serif",
        "source": "System",
        "weights": [400],
        "use": "INS风英文装饰文字"
      },
      "monospace": {
        "name": "Consolas",
        "fallback": "Courier New, monospace",
        "source": "System",
        "weights": [400],
        "use": "代码块"
      }
    },
    "textRendering": {
      "wrapText": {
        "description": "自动换行算法 — 按字符宽度计算，支持中英文混排",
        "method": "measureText + 逐字符换行",
        "rules": [
          "中文标点不能出现在行首: 。，、！？；：）》」』】",
          "中文标点不能出现在行尾的开头标点: （《「『【",
          "英文单词不拆分（空格为断点）",
          "长英文单词超过行宽时强制断开"
        ]
      },
      "antiAlias": true,
      "textBaseline": "top",
      "defaultLetterSpacing": 0
    },
    "cardTypes": {
      "cover": "封面卡 — 标题 + 副标题 + 装饰元素",
      "content": "内容卡 — 正文排版 + 段落 + 列表 + 引用",
      "ending": "结尾卡 — 感谢 + CTA + 账号信息"
    },
    "maxContentPerCard": {
      "description": "每张内容卡最大文字量（超出自动分页）",
      "chineseChars": 280,
      "estimatedLines": 18,
      "splitRule": "按段落拆分，不拆断段落中间"
    },
    "commonDecorations": {
      "roundedRect": {
        "description": "圆角矩形绘制函数",
        "implementation": "ctx.roundRect(x, y, w, h, radius) 或 beginPath + arcTo"
      },
      "shadowSetup": {
        "description": "阴影设置",
        "implementation": "ctx.shadowColor, ctx.shadowBlur, ctx.shadowOffsetX, ctx.shadowOffsetY"
      },
      "gradientLine": {
        "description": "渐变线条",
        "implementation": "createLinearGradient → addColorStop → strokeStyle"
      }
    }
  }
}
```

---

## 模板风格对照表

| 特性 | 简约文艺 | 清新可爱 | 高级商务 | INS风 | 暖色治愈 | 暗黑酷炫 | 国潮复古 | 学习干货 |
|------|---------|---------|---------|-------|---------|---------|---------|---------|
| 底色 | 米白 | 粉渐变 | 深蓝黑 | 暖杏 | 暖橙白 | 纯黑 | 宣纸色 | 蓝灰白 |
| 标题字重 | bold | bold | bold | light | bold | black | bold | bold |
| 标题对齐 | 居中 | 居中 | 左对齐 | 居中 | 居中 | 左对齐 | 居中 | 居中 |
| 正文字号 | 28px | 27px | 26px | 26px | 28px | 26px | 27px | 26px |
| 行高 | 52px | 50px | 48px | 50px | 52px | 48px | 52px | 48px |
| 装饰风格 | 细线+点 | 圆+波浪 | 金色线角 | 胶片 | 光圈+星 | 霓虹发光 | 印章+纹 | 笔记本线 |
| 色彩数量 | 3色 | 5色+ | 3色 | 3色 | 4色 | 4色(霓虹) | 4色 | 5色+ |
| 情绪 | 安静 | 活泼 | 专业 | 慵懒 | 温暖 | 冷酷 | 古典 | 清晰 |

---

## Canvas 渲染注意事项

### 1. 字体加载
```javascript
// 预加载 Google Fonts（如果在浏览器环境）
const fontPromise = document.fonts.load('400 48px "Noto Sans SC"');
// 使用 FontFace API 或 @font-face 预加载
// 渲染前 await 字体加载完成
```

### 2. 高 DPI 支持
```javascript
const dpr = window.devicePixelRatio || 1;
canvas.width = 1080 * dpr;
canvas.height = 1440 * dpr;
canvas.style.width = '1080px';
canvas.style.height = '1440px';
ctx.scale(dpr, dpr);
```

### 3. 中文文本换行
```javascript
function wrapText(ctx, text, x, y, maxWidth, lineHeight) {
  const chars = text.split('');
  let line = '';
  let currentY = y;
  const noBreasBefore = '。，、！？；：）》」』】…—～·';
  
  for (let i = 0; i < chars.length; i++) {
    const testLine = line + chars[i];
    const metrics = ctx.measureText(testLine);
    
    if (metrics.width > maxWidth && line.length > 0) {
      // 检查标点禁则
      if (noBreasBefore.includes(chars[i])) {
        // 将最后一个字符移到下一行
        ctx.fillText(line, x, currentY);
        currentY += lineHeight;
        line = chars[i];
      } else {
        ctx.fillText(line, x, currentY);
        currentY += lineHeight;
        line = chars[i];
      }
    } else {
      line = testLine;
    }
  }
  if (line) ctx.fillText(line, x, currentY);
  return currentY + lineHeight; // 返回下一行 Y 位置
}
```

### 4. 圆角矩形
```javascript
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
}
```

### 5. 噪点/纸纹生成
```javascript
function addPaperTexture(ctx, w, h, density, alphaMax) {
  for (let i = 0; i < density; i++) {
    const x = Math.random() * w;
    const y = Math.random() * h;
    const alpha = Math.random() * alphaMax;
    const gray = 100 + Math.random() * 80;
    ctx.fillStyle = `rgba(${gray},${gray},${gray},${alpha})`;
    ctx.fillRect(x, y, 1, 1);
  }
}
```

---

## 集成到 Skill 系统

每个模板可以作为 `imageStyles` 的新选项加入现有 Skill 系统：

```javascript
// 在各 Skill 的 imageStyles 中添加卡片模板选项
imageStyles: {
  xiaohongshu: '小红书风格（AI生图）',
  // ... 其他 AI 风格 ...
  card_minimalist_literary: '📖 简约文艺卡片',
  card_fresh_cute: '🌸 清新可爱卡片',
  card_premium_business: '💎 高级商务卡片',
  card_ins_aesthetic: '📷 INS风卡片',
  card_warm_healing: '🌅 暖色治愈卡片',
  card_dark_cool: '🖤 暗黑酷炫卡片',
  card_chinese_retro: '🏮 国潮复古卡片',
  card_study_knowledge: '📚 学习干货卡片',
}
```

当用户选择 `card_*` 风格时，不调用 AI 图片生成 API，而是使用 Canvas 本地渲染对应模板。

---

*文档版本：v1.0 · 2026-03-15*
