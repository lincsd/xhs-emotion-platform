"""
小红书店铺商品图 - HTML+Chrome截图版
生成5张主图(800x800) + 8张详情图(750宽) + 1张完整长图
"""
import os, shutil
from html2image import Html2Image

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shop_images")
os.makedirs(OUT_DIR, exist_ok=True)

hti = Html2Image(output_path=OUT_DIR, browser='chrome',
                 custom_flags=['--no-sandbox','--disable-gpu','--hide-scrollbars',
                               '--force-device-scale-factor=2'])

BASE_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body {
  font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
  -webkit-font-smoothing: antialiased;
  overflow: hidden;
}
"""

MAIN1_HTML = """
<div style="width:800px;height:800px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
  display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;padding:40px;">
  <div style="background:rgba(255,255,255,0.18);padding:8px 28px;border-radius:24px;font-size:22px;
    font-weight:700;margin-bottom:28px;border:1px solid rgba(255,255,255,0.25);letter-spacing:2px;">
    ✨ 教育博主必备工具
  </div>
  <div style="font-size:80px;font-weight:900;line-height:1.2;text-align:center;
    text-shadow:0 4px 20px rgba(0,0,0,0.15);margin-bottom:8px;">知识卡片</div>
  <div style="font-size:80px;font-weight:900;line-height:1.2;text-align:center;
    text-shadow:0 4px 20px rgba(0,0,0,0.15);margin-bottom:24px;">AI生成器</div>
  <div style="font-size:26px;opacity:0.8;text-align:center;line-height:1.8;margin-bottom:28px;">
    小学 · 初中 · 高中 全学段覆盖<br>数学 · 语文 · 英语 全科目支持
  </div>
  <div style="display:flex;align-items:baseline;gap:4px;margin-bottom:32px;">
    <span style="font-size:32px;font-weight:700;">¥</span>
    <span style="font-size:88px;font-weight:900;line-height:1;">9.9</span>
    <span style="font-size:28px;opacity:0.7;">起</span>
  </div>
  <div style="display:flex;gap:14px;flex-wrap:wrap;justify-content:center;">
    <span style="background:rgba(255,255,255,0.18);padding:10px 22px;border-radius:12px;font-size:20px;font-weight:700;">🤖 AI出图</span>
    <span style="background:rgba(255,255,255,0.18);padding:10px 22px;border-radius:12px;font-size:20px;font-weight:700;">📝 自动文案</span>
    <span style="background:rgba(255,255,255,0.18);padding:10px 22px;border-radius:12px;font-size:20px;font-weight:700;">🎨 10种模板</span>
    <span style="background:rgba(255,255,255,0.18);padding:10px 22px;border-radius:12px;font-size:20px;font-weight:700;">⚡ 3分钟出片</span>
  </div>
</div>
"""

MAIN2_HTML = """
<div style="width:800px;height:800px;background:#fff;display:flex;flex-direction:column;padding:45px 40px;">
  <div style="text-align:center;margin-bottom:30px;">
    <div style="font-size:42px;font-weight:900;color:#333;">⚡ 四大核心功能</div>
    <div style="font-size:20px;color:#999;margin-top:6px;">从内容创作到发布全覆盖</div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;flex:1;">
    <div style="background:#e8f0fe;border-radius:24px;padding:32px 24px;text-align:center;display:flex;flex-direction:column;align-items:center;justify-content:center;">
      <div style="font-size:52px;margin-bottom:12px;">🤖</div>
      <div style="font-size:28px;font-weight:800;color:#1a73e8;margin-bottom:8px;">AI智能出图</div>
      <div style="font-size:17px;color:#666;line-height:1.6;">Gemini大模型驱动<br>v3全自动流水线<br>OCR审计零乱码</div>
    </div>
    <div style="background:#fce4ec;border-radius:24px;padding:32px 24px;text-align:center;display:flex;flex-direction:column;align-items:center;justify-content:center;">
      <div style="font-size:52px;margin-bottom:12px;">📝</div>
      <div style="font-size:28px;font-weight:800;color:#c62828;margin-bottom:8px;">笔记文案</div>
      <div style="font-size:17px;color:#666;line-height:1.6;">一键生成完整笔记<br>标题+正文+标签<br>多种写作风格</div>
    </div>
    <div style="background:#e8f5e9;border-radius:24px;padding:32px 24px;text-align:center;display:flex;flex-direction:column;align-items:center;justify-content:center;">
      <div style="font-size:52px;margin-bottom:12px;">🎨</div>
      <div style="font-size:28px;font-weight:800;color:#2e7d32;margin-bottom:8px;">10种卡片</div>
      <div style="font-size:17px;color:#666;line-height:1.6;">概念/方法/生活<br>陷阱/对战/公式<br>连算/速算/句型</div>
    </div>
    <div style="background:#fff3e0;border-radius:24px;padding:32px 24px;text-align:center;display:flex;flex-direction:column;align-items:center;justify-content:center;">
      <div style="font-size:52px;margin-bottom:12px;">📚</div>
      <div style="font-size:28px;font-weight:800;color:#e65100;margin-bottom:8px;">6大赛道</div>
      <div style="font-size:17px;color:#666;line-height:1.6;">小学/初中/高中<br>养生减脂/国学<br>情感生活</div>
    </div>
  </div>
</div>
"""

MAIN3_HTML = """
<div style="width:800px;height:800px;background:linear-gradient(180deg,#0f0c29 0%,#302b63 50%,#24243e 100%);
  color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px;">
  <div style="font-size:44px;font-weight:900;margin-bottom:10px;">🎯 生成效果展示</div>
  <div style="font-size:22px;opacity:0.45;margin-bottom:36px;">AI全自动 · 质量评分85+</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;width:100%;margin-bottom:36px;">
    <div style="background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.1);border-radius:20px;padding:28px;text-align:center;">
      <div style="font-size:44px;margin-bottom:8px;">📖</div>
      <div style="font-size:24px;font-weight:800;">小学教育</div>
      <div style="font-size:17px;opacity:0.45;margin-top:4px;">三上~六下 8学期</div>
    </div>
    <div style="background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.1);border-radius:20px;padding:28px;text-align:center;">
      <div style="font-size:44px;margin-bottom:8px;">🏫</div>
      <div style="font-size:24px;font-weight:800;">初中全科</div>
      <div style="font-size:17px;opacity:0.45;margin-top:4px;">七上~九下 6学期</div>
    </div>
    <div style="background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.1);border-radius:20px;padding:28px;text-align:center;">
      <div style="font-size:44px;margin-bottom:8px;">🎓</div>
      <div style="font-size:24px;font-weight:800;">高中全科</div>
      <div style="font-size:17px;opacity:0.45;margin-top:4px;">高一~高三 6学期</div>
    </div>
    <div style="background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.1);border-radius:20px;padding:28px;text-align:center;">
      <div style="font-size:44px;margin-bottom:8px;">🧘</div>
      <div style="font-size:24px;font-weight:800;">生活赛道</div>
      <div style="font-size:17px;opacity:0.45;margin-top:4px;">养生/国学/情感</div>
    </div>
  </div>
  <div style="text-align:center;">
    <div style="font-size:72px;font-weight:900;background:linear-gradient(135deg,#667eea,#764ba2);
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;">3分钟</div>
    <div style="font-size:22px;opacity:0.45;margin-top:4px;">一张精美知识卡片 · 从40分钟到3分钟</div>
  </div>
</div>
"""

MAIN4_HTML = """
<div style="width:800px;height:800px;background:#fff;display:flex;flex-direction:column;padding:40px 45px;">
  <div style="text-align:center;margin-bottom:32px;">
    <div style="font-size:42px;font-weight:900;color:#333;">💎 积分套餐</div>
  </div>
  <div style="display:flex;flex-direction:column;gap:16px;flex:1;">
    <div style="display:flex;align-items:center;background:#e8f0fe;border-radius:20px;padding:24px 28px;gap:18px;">
      <div style="font-size:44px;">🎁</div>
      <div style="flex:1;"><div style="font-size:26px;font-weight:800;color:#1a73e8;">体验包</div><div style="font-size:18px;color:#888;margin-top:2px;">100积分 · 可生成~10张卡片</div></div>
      <div style="font-size:36px;font-weight:900;color:#1a73e8;">¥9.9</div>
    </div>
    <div style="display:flex;align-items:center;background:#fce4ec;border-radius:20px;padding:24px 28px;gap:18px;">
      <div style="font-size:44px;">⭐</div>
      <div style="flex:1;"><div style="font-size:26px;font-weight:800;color:#c62828;">月卡</div><div style="font-size:18px;color:#888;margin-top:2px;">500积分 · 可生成~50张卡片</div></div>
      <div style="font-size:36px;font-weight:900;color:#c62828;">¥39.9</div>
    </div>
    <div style="display:flex;align-items:center;background:#e8f5e9;border-radius:20px;padding:24px 28px;gap:18px;border:3px solid #2e7d32;position:relative;">
      <div style="position:absolute;top:-14px;right:20px;background:#ff4d4f;color:#fff;padding:4px 16px;border-radius:12px;font-size:16px;font-weight:800;">🔥 最热</div>
      <div style="font-size:44px;">🔥</div>
      <div style="flex:1;"><div style="font-size:26px;font-weight:800;color:#2e7d32;">季卡（热卖）</div><div style="font-size:18px;color:#888;margin-top:2px;">2000积分 · 可生成~200张卡片</div></div>
      <div style="font-size:36px;font-weight:900;color:#2e7d32;">¥99.9</div>
    </div>
    <div style="display:flex;align-items:center;background:linear-gradient(135deg,#fffbf0,#fff5e6);border-radius:20px;padding:24px 28px;gap:18px;">
      <div style="font-size:44px;">👑</div>
      <div style="flex:1;"><div style="font-size:26px;font-weight:800;color:#e65100;">年卡</div><div style="font-size:18px;color:#888;margin-top:2px;">10000积分 · 可生成~1000张卡片</div></div>
      <div style="font-size:36px;font-weight:900;color:#e65100;">¥399.9</div>
    </div>
  </div>
  <div style="text-align:center;font-size:22px;color:#999;margin-top:20px;">积分永久有效 · 不限使用时间 · 即买即用</div>
</div>
"""

MAIN5_HTML = """
<div style="width:800px;height:800px;background:linear-gradient(135deg,#f093fb 0%,#f5576c 100%);
  color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:50px;">
  <div style="font-size:88px;margin-bottom:16px;">🛡️</div>
  <div style="font-size:52px;font-weight:900;margin-bottom:14px;text-shadow:0 3px 10px rgba(0,0,0,0.1);">放心购买</div>
  <div style="font-size:24px;opacity:0.8;text-align:center;line-height:1.8;margin-bottom:36px;">
    拍下后自动发送兑换码<br>输入即到账，立即可用
  </div>
  <div style="width:100%;display:flex;flex-direction:column;gap:14px;margin-bottom:36px;">
    <div style="background:rgba(255,255,255,0.18);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:18px 28px;font-size:24px;font-weight:700;display:flex;align-items:center;gap:14px;">
      <span style="font-size:28px;">✅</span> 兑换码即拍即发 · 秒到账
    </div>
    <div style="background:rgba(255,255,255,0.18);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:18px 28px;font-size:24px;font-weight:700;display:flex;align-items:center;gap:14px;">
      <span style="font-size:28px;">✅</span> 积分永久有效 · 不过期
    </div>
    <div style="background:rgba(255,255,255,0.18);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:18px 28px;font-size:24px;font-weight:700;display:flex;align-items:center;gap:14px;">
      <span style="font-size:28px;">✅</span> 覆盖全学段 · 全科目
    </div>
    <div style="background:rgba(255,255,255,0.18);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:18px 28px;font-size:24px;font-weight:700;display:flex;align-items:center;gap:14px;">
      <span style="font-size:28px;">✅</span> 7×24小时客服 · 有问必答
    </div>
  </div>
  <div style="background:#fff;color:#f5576c;padding:18px 64px;border-radius:40px;font-size:28px;font-weight:900;box-shadow:0 6px 24px rgba(0,0,0,0.12);">
    👉 立即购买体验
  </div>
</div>
"""

DETAIL_1_HTML = """<div style="width:750px;height:500px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
  color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px;">
  <div style="font-size:20px;opacity:0.55;margin-bottom:14px;letter-spacing:3px;">教育博主 · 知识号 · 学习号 专属工具</div>
  <div style="font-size:48px;font-weight:900;margin-bottom:14px;">知识卡片 AI 生成器</div>
  <div style="font-size:22px;opacity:0.8;line-height:1.8;text-align:center;margin-bottom:28px;">AI全自动生成精美知识卡片 + 小红书笔记文案<br>做教育号，再也不用手动做图了</div>
  <div style="display:flex;gap:10px;flex-wrap:wrap;justify-content:center;">
    <span style="background:rgba(255,255,255,0.2);padding:8px 20px;border-radius:20px;font-size:18px;font-weight:700;">小学</span>
    <span style="background:rgba(255,255,255,0.2);padding:8px 20px;border-radius:20px;font-size:18px;font-weight:700;">初中</span>
    <span style="background:rgba(255,255,255,0.2);padding:8px 20px;border-radius:20px;font-size:18px;font-weight:700;">高中</span>
    <span style="background:rgba(255,255,255,0.2);padding:8px 20px;border-radius:20px;font-size:18px;font-weight:700;">养生减脂</span>
    <span style="background:rgba(255,255,255,0.2);padding:8px 20px;border-radius:20px;font-size:18px;font-weight:700;">国学文化</span>
    <span style="background:rgba(255,255,255,0.2);padding:8px 20px;border-radius:20px;font-size:18px;font-weight:700;">情感生活</span>
  </div>
</div>"""

DETAIL_2_HTML = """<div style="width:750px;background:#fff;padding:40px 36px;">
  <div style="text-align:center;font-size:34px;font-weight:900;color:#333;margin-bottom:28px;">😩 做教育号，你是不是也……</div>
  <div style="display:flex;flex-direction:column;gap:14px;">
    <div style="background:#fff5f5;border-radius:16px;padding:22px 24px;display:flex;align-items:center;gap:16px;">
      <span style="font-size:40px;">😰</span>
      <div><div style="font-weight:800;font-size:21px;color:#c62828;">做一张知识卡片要40分钟</div><div style="font-size:16px;color:#888;margin-top:3px;">排版、配色、文字校对太耗时间</div></div>
    </div>
    <div style="background:#fff5f5;border-radius:16px;padding:22px 24px;display:flex;align-items:center;gap:16px;">
      <span style="font-size:40px;">😤</span>
      <div><div style="font-weight:800;font-size:21px;color:#c62828;">AI生成的图中文总是乱码</div><div style="font-size:16px;color:#888;margin-top:3px;">用各种AI工具出的图，中文全是乱七八糟</div></div>
    </div>
    <div style="background:#fff5f5;border-radius:16px;padding:22px 24px;display:flex;align-items:center;gap:16px;">
      <span style="font-size:40px;">😫</span>
      <div><div style="font-weight:800;font-size:21px;color:#c62828;">笔记文案写不出爆款感</div><div style="font-size:16px;color:#888;margin-top:3px;">标题没吸引力、正文干巴巴</div></div>
    </div>
    <div style="background:#fff5f5;border-radius:16px;padding:22px 24px;display:flex;align-items:center;gap:16px;">
      <span style="font-size:40px;">😭</span>
      <div><div style="font-weight:800;font-size:21px;color:#c62828;">内容产量跟不上更新频率</div><div style="font-size:16px;color:#888;margin-top:3px;">一天一更都做不到，赛道竞争越来越大</div></div>
    </div>
  </div>
  <div style="text-align:center;margin-top:24px;padding:18px;background:linear-gradient(135deg,#667eea,#764ba2);border-radius:14px;color:#fff;font-size:24px;font-weight:800;">👇 一个工具，全部搞定</div>
</div>"""

DETAIL_3_HTML = """<div style="width:750px;background:#f8f9ff;padding:40px 36px;">
  <div style="text-align:center;margin-bottom:28px;">
    <div style="font-size:34px;font-weight:900;color:#333;">⚡ 核心功能</div>
    <div style="font-size:18px;color:#999;margin-top:4px;">AI驱动 · 全流程自动化</div>
  </div>
  <div style="display:flex;flex-direction:column;gap:18px;">
    <div style="background:#fff;border-radius:18px;padding:26px;box-shadow:0 2px 12px rgba(0,0,0,0.04);">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:14px;">
        <span style="font-size:40px;">🤖</span><span style="font-size:26px;font-weight:800;color:#1a73e8;">AI智能出图</span>
      </div>
      <div style="font-size:17px;color:#555;line-height:2;padding-left:8px;">• Gemini 2.5 大模型驱动<br>• v3全自动流水线：生图→OCR审计→自动重试→质量评分<br>• 中文零乱码保障（PIL文字修补兜底）</div>
    </div>
    <div style="background:#fff;border-radius:18px;padding:26px;box-shadow:0 2px 12px rgba(0,0,0,0.04);">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:14px;">
        <span style="font-size:40px;">📝</span><span style="font-size:26px;font-weight:800;color:#c62828;">笔记工坊</span>
      </div>
      <div style="font-size:17px;color:#555;line-height:2;padding-left:8px;">• 从知识卡片一键生成完整小红书笔记<br>• 标题、正文、配图、标签全自动<br>• 反差型/干货型/种草型 多种风格</div>
    </div>
    <div style="background:#fff;border-radius:18px;padding:26px;box-shadow:0 2px 12px rgba(0,0,0,0.04);">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:14px;">
        <span style="font-size:40px;">🎨</span><span style="font-size:26px;font-weight:800;color:#2e7d32;">10种卡片模板</span>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:6px;">
        <span style="background:#e8f5e9;color:#2e7d32;padding:6px 16px;border-radius:8px;font-size:16px;font-weight:700;">概念卡</span>
        <span style="background:#e8f5e9;color:#2e7d32;padding:6px 16px;border-radius:8px;font-size:16px;font-weight:700;">方法卡</span>
        <span style="background:#e8f5e9;color:#2e7d32;padding:6px 16px;border-radius:8px;font-size:16px;font-weight:700;">生活卡</span>
        <span style="background:#e8f5e9;color:#2e7d32;padding:6px 16px;border-radius:8px;font-size:16px;font-weight:700;">陷阱卡</span>
        <span style="background:#e8f5e9;color:#2e7d32;padding:6px 16px;border-radius:8px;font-size:16px;font-weight:700;">对战卡</span>
        <span style="background:#e8f5e9;color:#2e7d32;padding:6px 16px;border-radius:8px;font-size:16px;font-weight:700;">公式卡</span>
        <span style="background:#e8f5e9;color:#2e7d32;padding:6px 16px;border-radius:8px;font-size:16px;font-weight:700;">连算卡</span>
        <span style="background:#e8f5e9;color:#2e7d32;padding:6px 16px;border-radius:8px;font-size:16px;font-weight:700;">速算卡</span>
        <span style="background:#e8f5e9;color:#2e7d32;padding:6px 16px;border-radius:8px;font-size:16px;font-weight:700;">句型卡</span>
        <span style="background:#e8f5e9;color:#2e7d32;padding:6px 16px;border-radius:8px;font-size:16px;font-weight:700;">总结卡</span>
      </div>
    </div>
  </div>
</div>"""

DETAIL_4_HTML = """<div style="width:750px;background:linear-gradient(180deg,#0f0c29 0%,#302b63 50%,#24243e 100%);color:#fff;padding:40px 36px;">
  <div style="text-align:center;margin-bottom:28px;">
    <div style="font-size:34px;font-weight:900;">📚 覆盖范围</div>
    <div style="font-size:18px;opacity:0.4;margin-top:4px;">6大赛道 · 3大科目 · 20个学期</div>
  </div>
  <div style="display:flex;flex-direction:column;gap:12px;">
    <div style="display:flex;align-items:center;gap:16px;background:rgba(255,255,255,0.07);border-radius:14px;padding:18px 22px;">
      <span style="font-size:36px;">📖</span><div><div style="font-weight:800;font-size:22px;">小学教育</div><div style="font-size:16px;opacity:0.45;margin-top:2px;">三年级~六年级 · 数学/语文/英语 · 8学期</div></div>
    </div>
    <div style="display:flex;align-items:center;gap:16px;background:rgba(255,255,255,0.07);border-radius:14px;padding:18px 22px;">
      <span style="font-size:36px;">🏫</span><div><div style="font-weight:800;font-size:22px;">初中教育</div><div style="font-size:16px;opacity:0.45;margin-top:2px;">七年级~九年级 · 数学/语文/英语 · 6学期</div></div>
    </div>
    <div style="display:flex;align-items:center;gap:16px;background:rgba(255,255,255,0.07);border-radius:14px;padding:18px 22px;">
      <span style="font-size:36px;">🎓</span><div><div style="font-weight:800;font-size:22px;">高中教育</div><div style="font-size:16px;opacity:0.45;margin-top:2px;">高一~高三 · 数学/语文/英语 · 6学期</div></div>
    </div>
    <div style="display:flex;align-items:center;gap:16px;background:rgba(255,255,255,0.07);border-radius:14px;padding:18px 22px;">
      <span style="font-size:36px;">🧘</span><div><div style="font-weight:800;font-size:22px;">养生减脂</div><div style="font-size:16px;opacity:0.45;margin-top:2px;">健康饮食 · 运动方案 · 中医养生</div></div>
    </div>
    <div style="display:flex;align-items:center;gap:16px;background:rgba(255,255,255,0.07);border-radius:14px;padding:18px 22px;">
      <span style="font-size:36px;">📜</span><div><div style="font-weight:800;font-size:22px;">国学文化</div><div style="font-size:16px;opacity:0.45;margin-top:2px;">诗词典故 · 传统文化 · 经典解读</div></div>
    </div>
    <div style="display:flex;align-items:center;gap:16px;background:rgba(255,255,255,0.07);border-radius:14px;padding:18px 22px;">
      <span style="font-size:36px;">💕</span><div><div style="font-weight:800;font-size:22px;">情感生活</div><div style="font-size:16px;opacity:0.45;margin-top:2px;">亲子关系 · 情感分析 · 心理疏导</div></div>
    </div>
  </div>
</div>"""

DETAIL_5_HTML = """<div style="width:750px;background:#fff;padding:40px 36px;">
  <div style="text-align:center;margin-bottom:28px;">
    <div style="font-size:34px;font-weight:900;color:#333;">📱 使用流程</div>
    <div style="font-size:18px;color:#999;margin-top:4px;">3步搞定，超简单</div>
  </div>
  <div style="display:flex;flex-direction:column;gap:8px;">
    <div style="display:flex;gap:18px;align-items:flex-start;">
      <div style="width:52px;height:52px;border-radius:50%;background:#1a73e8;display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:900;color:#fff;flex-shrink:0;">1</div>
      <div style="padding-top:4px;"><div style="font-size:24px;font-weight:800;color:#1a73e8;">拍下 → 收到兑换码</div><div style="font-size:17px;color:#888;margin-top:6px;line-height:1.7;">下单后自动发送兑换码到订单消息<br>格式：XHS-XXXX-XXXX-XXXX</div></div>
    </div>
    <div style="margin-left:25px;font-size:28px;color:#ddd;">⬇</div>
    <div style="display:flex;gap:18px;align-items:flex-start;">
      <div style="width:52px;height:52px;border-radius:50%;background:#2e7d32;display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:900;color:#fff;flex-shrink:0;">2</div>
      <div style="padding-top:4px;"><div style="font-size:24px;font-weight:800;color:#2e7d32;">登录平台 → 输入兑换码</div><div style="font-size:17px;color:#888;margin-top:6px;line-height:1.7;">打开平台网址 → 注册/登录<br>点击「💎 AI积分」→ 输入兑换码 → 积分到账</div></div>
    </div>
    <div style="margin-left:25px;font-size:28px;color:#ddd;">⬇</div>
    <div style="display:flex;gap:18px;align-items:flex-start;">
      <div style="width:52px;height:52px;border-radius:50%;background:#e65100;display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:900;color:#fff;flex-shrink:0;">3</div>
      <div style="padding-top:4px;"><div style="font-size:24px;font-weight:800;color:#e65100;">开始创作 → AI自动出图</div><div style="font-size:17px;color:#888;margin-top:6px;line-height:1.7;">选择学段+科目+知识点<br>点击「🎨 AI生成卡片」→ 3分钟出精美图片</div></div>
    </div>
  </div>
</div>"""

DETAIL_6_HTML = """<div style="width:750px;background:#f8f9ff;padding:40px 36px;">
  <div style="text-align:center;margin-bottom:24px;">
    <div style="font-size:34px;font-weight:900;color:#333;">💎 套餐选择</div>
    <div style="font-size:18px;color:#999;margin-top:4px;">积分永久有效 · 不限使用时间</div>
  </div>
  <table style="width:100%;border-collapse:collapse;font-size:17px;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.04);">
    <thead><tr style="background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;">
      <th style="padding:16px 12px;font-size:18px;">套餐</th><th style="padding:16px 12px;">积分</th><th style="padding:16px 12px;">可生成</th><th style="padding:16px 12px;">价格</th><th style="padding:16px 12px;">单价</th>
    </tr></thead>
    <tbody>
      <tr style="border-bottom:1px solid #f0f0f0;"><td style="padding:16px 12px;font-weight:700;">🎁 体验包</td><td style="padding:16px;text-align:center;">100</td><td style="padding:16px;text-align:center;">~10张</td><td style="padding:16px;text-align:center;font-weight:800;color:#1a73e8;">¥9.9</td><td style="padding:16px;text-align:center;">¥0.99/张</td></tr>
      <tr style="border-bottom:1px solid #f0f0f0;"><td style="padding:16px 12px;font-weight:700;">⭐ 月卡</td><td style="padding:16px;text-align:center;">500</td><td style="padding:16px;text-align:center;">~50张</td><td style="padding:16px;text-align:center;font-weight:800;color:#c62828;">¥39.9</td><td style="padding:16px;text-align:center;">¥0.80/张</td></tr>
      <tr style="border-bottom:1px solid #f0f0f0;background:#f0fff4;"><td style="padding:16px 12px;font-weight:700;">🔥 季卡</td><td style="padding:16px;text-align:center;">2000</td><td style="padding:16px;text-align:center;">~200张</td><td style="padding:16px;text-align:center;font-weight:800;color:#2e7d32;font-size:20px;">¥99.9</td><td style="padding:16px;text-align:center;color:#2e7d32;font-weight:800;">¥0.50/张</td></tr>
      <tr><td style="padding:16px 12px;font-weight:700;">👑 年卡</td><td style="padding:16px;text-align:center;">10000</td><td style="padding:16px;text-align:center;">~1000张</td><td style="padding:16px;text-align:center;font-weight:800;color:#e65100;">¥399.9</td><td style="padding:16px;text-align:center;color:#e65100;font-weight:800;">¥0.40/张</td></tr>
    </tbody>
  </table>
  <div style="text-align:center;margin-top:16px;font-size:17px;color:#999;">🔥 季卡性价比最高，推荐教育号日更博主选择</div>
</div>"""

DETAIL_7_HTML = """<div style="width:750px;background:#fff;padding:40px 36px;">
  <div style="text-align:center;margin-bottom:28px;"><div style="font-size:34px;font-weight:900;color:#333;">❓ 常见问题</div></div>
  <div style="display:flex;flex-direction:column;gap:14px;">
    <div style="background:#f8f9ff;border-radius:14px;padding:22px;"><div style="font-size:20px;font-weight:800;color:#333;margin-bottom:8px;">Q: 积分会过期吗？</div><div style="font-size:17px;color:#555;line-height:1.7;">A: 不会！积分永久有效，买了随时都可以用，没有使用期限。</div></div>
    <div style="background:#f8f9ff;border-radius:14px;padding:22px;"><div style="font-size:20px;font-weight:800;color:#333;margin-bottom:8px;">Q: 兑换码怎么用？</div><div style="font-size:17px;color:#555;line-height:1.7;">A: 拍下后自动收到兑换码（格式：XHS-XXXX-XXXX-XXXX）。<br>打开平台 → 登录 → 点「💎 AI积分」→ 输入兑换码 → 积分秒到。</div></div>
    <div style="background:#f8f9ff;border-radius:14px;padding:22px;"><div style="font-size:20px;font-weight:800;color:#333;margin-bottom:8px;">Q: 一个积分能生成什么？</div><div style="font-size:17px;color:#555;line-height:1.7;">A: 每天有10次免费AI调用。超出后生成卡片约10积分，笔记约2积分。每天免费额度会重置。</div></div>
    <div style="background:#f8f9ff;border-radius:14px;padding:22px;"><div style="font-size:20px;font-weight:800;color:#333;margin-bottom:8px;">Q: 支持哪些科目和年级？</div><div style="font-size:17px;color:#555;line-height:1.7;">A: 小学(3-6年级)、初中(7-9年级)、高中(高一~高三)的数学/语文/英语。还有养生减脂、国学文化、情感生活赛道。</div></div>
    <div style="background:#f8f9ff;border-radius:14px;padding:22px;"><div style="font-size:20px;font-weight:800;color:#333;margin-bottom:8px;">Q: 可以退款吗？</div><div style="font-size:17px;color:#555;line-height:1.7;">A: 虚拟商品，兑换码一经兑换不支持退款。未兑换的卡密可联系客服处理。</div></div>
  </div>
</div>"""

DETAIL_8_HTML = """<div style="width:750px;height:400px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:40px 36px;display:flex;flex-direction:column;align-items:center;">
  <div style="font-size:34px;font-weight:900;margin-bottom:6px;">🛡️ 服务保障</div>
  <div style="font-size:18px;opacity:0.5;margin-bottom:28px;">放心购买 · 售后无忧</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;width:100%;">
    <div style="text-align:center;padding:24px 16px;border-radius:16px;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.2);"><div style="font-size:40px;margin-bottom:8px;">⚡</div><div style="font-size:18px;font-weight:700;line-height:1.6;">即买即用<br>兑换码秒发</div></div>
    <div style="text-align:center;padding:24px 16px;border-radius:16px;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.2);"><div style="font-size:40px;margin-bottom:8px;">♾️</div><div style="font-size:18px;font-weight:700;line-height:1.6;">永久有效<br>积分不过期</div></div>
    <div style="text-align:center;padding:24px 16px;border-radius:16px;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.2);"><div style="font-size:40px;margin-bottom:8px;">🔄</div><div style="font-size:18px;font-weight:700;line-height:1.6;">持续更新<br>功能迭代中</div></div>
    <div style="text-align:center;padding:24px 16px;border-radius:16px;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.2);"><div style="font-size:40px;margin-bottom:8px;">💬</div><div style="font-size:18px;font-weight:700;line-height:1.6;">在线客服<br>有问必答</div></div>
  </div>
  <div style="margin-top:auto;font-size:18px;opacity:0.6;">如有任何问题，请随时私信联系 ❤️</div>
</div>"""


def screenshot_fixed(html, css, filename, size):
    full = f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{html}</body></html>"
    hti.screenshot(html_str=full, save_as=filename, size=size)
    fpath = os.path.join(OUT_DIR, filename)
    sz = os.path.getsize(fpath) // 1024
    print(f"  ✅ {filename}  ({size[0]}x{size[1]}, {sz}KB)")

def screenshot_auto_h(html, css, filename, width=750):
    big_h = 2000
    full = f"<html><head><meta charset='utf-8'><style>{css}</style></head><body style='width:{width}px;'>{html}</body></html>"
    tmp = f"_tmp_{filename}"
    hti.screenshot(html_str=full, save_as=tmp, size=(width, big_h))
    
    from PIL import Image
    tmp_path = os.path.join(OUT_DIR, tmp)
    img = Image.open(tmp_path)
    px = img.load()
    w, h = img.size
    bottom = h
    for y in range(h-1, 0, -1):
        blank = True
        for x in range(0, w, 8):
            p = px[x, y]
            r, g, b = (p[0], p[1], p[2]) if isinstance(p, tuple) else (255, 255, 255)
            if not (r > 250 and g > 250 and b > 250):
                blank = False
                break
        if not blank:
            bottom = min(y + 4, h)
            break
    
    cropped = img.crop((0, 0, w, bottom))
    out_path = os.path.join(OUT_DIR, filename)
    cropped.save(out_path, quality=95)
    os.remove(tmp_path)
    sz = os.path.getsize(out_path) // 1024
    print(f"  ✅ {filename}  ({cropped.width}x{cropped.height}, {sz}KB)")
    return cropped


if __name__ == '__main__':
    for f in os.listdir(OUT_DIR):
        if f.endswith('.png') and not f.startswith('_'):
            os.remove(os.path.join(OUT_DIR, f))
    
    print("📸 生成主图 (800x800)...\n")
    screenshot_fixed(MAIN1_HTML, BASE_CSS, "主图1_产品封面.png", (800, 800))
    screenshot_fixed(MAIN2_HTML, BASE_CSS, "主图2_核心功能.png", (800, 800))
    screenshot_fixed(MAIN3_HTML, BASE_CSS, "主图3_效果展示.png", (800, 800))
    screenshot_fixed(MAIN4_HTML, BASE_CSS, "主图4_套餐价格.png", (800, 800))
    screenshot_fixed(MAIN5_HTML, BASE_CSS, "主图5_信任背书.png", (800, 800))
    
    print("\n📸 生成详情图 (750宽)...\n")
    parts = []
    parts.append(screenshot_auto_h(DETAIL_1_HTML, BASE_CSS, "详情图_1_头图.png"))
    parts.append(screenshot_auto_h(DETAIL_2_HTML, BASE_CSS, "详情图_2_痛点共鸣.png"))
    parts.append(screenshot_auto_h(DETAIL_3_HTML, BASE_CSS, "详情图_3_核心功能.png"))
    parts.append(screenshot_auto_h(DETAIL_4_HTML, BASE_CSS, "详情图_4_覆盖范围.png"))
    parts.append(screenshot_auto_h(DETAIL_5_HTML, BASE_CSS, "详情图_5_使用流程.png"))
    parts.append(screenshot_auto_h(DETAIL_6_HTML, BASE_CSS, "详情图_6_套餐对比.png"))
    parts.append(screenshot_auto_h(DETAIL_7_HTML, BASE_CSS, "详情图_7_FAQ.png"))
    parts.append(screenshot_auto_h(DETAIL_8_HTML, BASE_CSS, "详情图_8_服务保障.png"))
    
    from PIL import Image
    total_h = sum(p.height for p in parts)
    w = parts[0].width
    long_img = Image.new('RGB', (w, total_h))
    y = 0
    for p in parts:
        long_img.paste(p, (0, y))
        y += p.height
    lp = os.path.join(OUT_DIR, "详情图_完整长图.png")
    long_img.save(lp, quality=95)
    sz = os.path.getsize(lp) // 1024
    print(f"\n  ✅ 详情图_完整长图.png  ({w}x{total_h}, {sz}KB)")
    
    with open(os.path.join(OUT_DIR, "商品标题和描述.txt"), 'w', encoding='utf-8') as f:
        f.write("""# 商品标题（选一个）
1. 知识卡片AI生成器｜教育号小红书出图神器｜全学段全科目
2. AI知识卡片自动生成工具｜小学初中高中｜教育博主必备
3. 教育号AI出图工具｜知识卡片3分钟生成｜积分充值

# SKU
🎁 体验包 100积分  ¥9.9
⭐ 月卡 500积分    ¥39.9
🔥 季卡 2000积分   ¥99.9
👑 年卡 10000积分  ¥399.9

# 商品描述
【商品说明】本商品为「知识卡片AI生成器」积分兑换码（虚拟商品）。
📌 什么是知识卡片AI生成器？
一款专为教育号/知识号/学习号博主打造的AI出图工具。
输入知识点 → AI自动生成精美卡片图 + 小红书笔记文案。
📌 支持内容：小学/初中/高中 数学·语文·英语 + 养生减脂/国学文化/情感生活
📌 使用方法：拍下→收到兑换码→登录平台输入→积分到账→开始创作
📌 积分说明：每天10次免费，超出后卡片约10积分，笔记约2积分，永久有效
📌 温馨提示：虚拟商品，兑换后不退款，未兑换可联系客服
""")
    
    print(f"\n🎉 全部完成！文件在: {OUT_DIR}")
