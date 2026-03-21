"""Insert PromptLib JS module into public/index.html"""
import re

fpath = 'public/index.html'
data = open(fpath, 'r', encoding='utf-8').read()

# Find the insertion point: after })(); and before the PromoMaterial comment
# The pattern is: })();\r\n or })();\n followed by blank line, then the comment line
marker = '\u63a8\u5e7f\u7269\u6599\u751f\u6210\u7cfb\u7edf'  # 推广物料生成系统
idx = data.find(marker)
if idx < 0:
    print("ERROR: marker not found")
    exit(1)

# Find the start of the comment line (// ============ ...)
line_start = data.rfind('\n', 0, idx)
# Find the })(); before it
close_paren = data.rfind('})();', 0, line_start)
if close_paren < 0:
    print("ERROR: })(); not found before marker")
    exit(1)

# We'll insert right after })();
insert_pos = close_paren + len('})();')

MODULE = r'''

    // ============ 🧪 Prompt 工程库模块 ============
    const PromptLib = (() => {
      // ─── 嵌入数据 ───
      const CARD_TYPES = {
        '概念卡': { count: 8, color: '#54A0FF', icon: '💡', desc: '生活场景→抽象概念', examples: '面积含义、小数含义、方向认知' },
        '方法卡': { count: 21, color: '#FF9F43', icon: '🔧', desc: '具体例题→色块分步→答案', examples: '口算、笔算、估算、验算' },
        '辨析卡': { count: 2, color: '#FF6B6B', icon: '⚖️', desc: '✓/✗ 并排对比→红圈标差异', examples: '商中间有0 vs 商末尾有0' },
        '公式卡': { count: 3, color: '#5ECE7B', icon: '📐', desc: '图形实例→推导可视化→公式', examples: '长方形面积、正方形面积' }
      };

      const CHANGELOG = [
        { ver: 'v9', date: '2026-03-21', title: '例题驱动 + 题型 Skill 分化',
          problem: '卡片看不出在解什么题，解题过程抽象',
          changes: ['每张卡片必须围绕一道具体例题展开', '题目必须醒目展示在卡面上', '解题用色块分步图示，不画竖式', '答案单独大字展示', '建立 card_prompt_lib/ 目录，按题型归档 Skill'] },
        { ver: 'v8', date: '2026-03-21', title: '渐变配色 + 顿悟教学',
          problem: '(1) 教学思路太抽象 (2) 配色太淡不吸引人',
          changes: ['背景改为渐变色（4种主题渐变+具体色号）', '标题banner用饱和色', '教学思路改为"找顿悟点"', '禁止画完整竖式'] },
        { ver: 'v7', date: '2026-03-21', title: '一卡一洞察',
          problem: '信息太多太杂，一张卡片塞太多内容',
          changes: ['"一卡一洞察"原则', '视觉元素≤5个', '箭头≤3个', '留白≥20%'] },
        { ver: 'v6', date: '2026-03-21', title: '图示自解释',
          problem: '箭头没有标签，看不懂',
          changes: ['每个箭头必须有≤4字中文标签', '步骤颜色编码', '计算过程有标注'] },
        { ver: 'v5', date: '2026-03-21', title: '特级教师人设',
          problem: '教学设计不够专业',
          changes: ['25年特级教师人设', '顿悟/类比/防踩坑/记忆钩子'] },
        { ver: 'v4', date: '2026-03-21', title: '文字精简',
          problem: '中文字太多太密，AI渲染质量差',
          changes: ['全卡≤35字', '标题≤4字', '粗笔画圆体/黑体'] },
        { ver: 'v3', date: '2026-03-21', title: '教师视角 + Bug修复',
          problem: '生成的图片太机械',
          changes: ['加入教师人设', '修复thinking消耗token', '修复内容主题漂移', '强制简体中文'] },
        { ver: 'v1-v2', date: '2026-03-21', title: '初始探索',
          problem: '从零开始',
          changes: ['v1: 34张批量生成', 'v2: 参考小红书爆款制定规范'] }
      ];

      const TEMPLATE_INFO = {
        version: 'v9',
        date: '2026-03-21',
        textModel: 'gemini-2.5-flash',
        imageModel: 'nano-banana-pro-preview (Gemini 3 Pro Image Preview)',
        layout: [
          { zone: 'CANVAS', pct: '100%', desc: '竖屏3:4, 渐变背景' },
          { zone: 'TITLE', pct: '10%', desc: '鲜色banner + 标题(≤4字超大)' },
          { zone: 'PROBLEM', pct: '15%', desc: '⚠️例题(白色卡片, 超大醒目字体)' },
          { zone: 'SOLVE', pct: '40%', desc: '色块/图示分步解题(不用竖式!)' },
          { zone: 'ANSWER', pct: '12%', desc: '答案(超大鲜明色) + 口诀' },
          { zone: 'BOTTOM', pct: '8%', desc: '小老师卡通+气泡' }
        ],
        colors: [
          { name: '珊瑚粉渐变', from: '#FF9A9E', to: '#FAD0C4' },
          { name: '薄荷蓝渐变', from: '#A1C4FD', to: '#C2E9FB' },
          { name: '蜜桃橙渐变', from: '#FFD89B', to: '#FFA7A7' },
          { name: '薰衣草紫渐变', from: '#E8D5F5', to: '#D9AAF5' }
        ],
        bannerColors: ['#FF6B6B', '#FF9F43', '#54A0FF', '#5ECE7B'],
        textRules: [
          { elem: '全卡中文', limit: '≤35字' },
          { elem: '标题', limit: '≤4字, 72pt粗体' },
          { elem: '金句', limit: '≤6字, 48pt' },
          { elem: '口诀', limit: '≤10字' },
          { elem: '气泡', limit: '≤6字' }
        ],
        dontList: ['不画完整竖式', '不画裸箭头(必须有标签)', '箭头不超过2个', '不让人猜题目——必须清晰可见', '不只有口诀没有例题']
      };

      let allCards = [];
      let currentTab = 'overview';

      function init() {
        if (allCards.length === 0) {
          try {
            const packs = KnowledgeCards._getPacks();
            if (packs.length > 0) {
              for (const u of packs[0].units) {
                for (const c of u.cards) {
                  allCards.push({ ...c, unit_name: u.unit_name, unit_id: u.unit_id });
                }
              }
            }
          } catch(e) {}
        }
        switchTab('overview');
      }

      function switchTab(tab) {
        currentTab = tab;
        document.querySelectorAll('.pl-tab').forEach(t => {
          const isActive = t.dataset.tab === tab;
          t.classList.toggle('active', isActive);
          t.style.borderBottom = isActive ? '2px solid var(--primary)' : '2px solid transparent';
          t.style.color = isActive ? 'var(--primary)' : 'var(--text-light)';
          t.style.fontWeight = isActive ? '600' : '500';
        });
        document.querySelectorAll('.pl-panel').forEach(p => p.style.display = 'none');
        const panel = document.getElementById('pl-panel-' + tab);
        if (panel) panel.style.display = '';
        renderTab(tab);
      }

      function renderTab(tab) {
        switch(tab) {
          case 'overview': renderOverview(); break;
          case 'prompts': renderPrompts(); break;
          case 'template': renderTemplate(); break;
          case 'changelog': renderChangelog(); break;
        }
      }

      function renderOverview() {
        const el = document.getElementById('pl-panel-overview');
        const totalCards = allCards.length || 34;
        el.innerHTML = `
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px;margin-bottom:24px">
            <div style="background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:20px;border-radius:14px">
              <div style="font-size:28px;font-weight:700">${TEMPLATE_INFO.version}</div>
              <div style="font-size:13px;opacity:.8">当前 Prompt 版本</div>
            </div>
            <div style="background:linear-gradient(135deg,#f093fb,#f5576c);color:#fff;padding:20px;border-radius:14px">
              <div style="font-size:28px;font-weight:700">${CHANGELOG.length}</div>
              <div style="font-size:13px;opacity:.8">迭代次数</div>
            </div>
            <div style="background:linear-gradient(135deg,#4facfe,#00f2fe);color:#fff;padding:20px;border-radius:14px">
              <div style="font-size:28px;font-weight:700">${totalCards}</div>
              <div style="font-size:13px;opacity:.8">知识点卡片</div>
            </div>
            <div style="background:linear-gradient(135deg,#43e97b,#38f9d7);color:#fff;padding:20px;border-radius:14px">
              <div style="font-size:28px;font-weight:700">4</div>
              <div style="font-size:13px;opacity:.8">题型 Skill</div>
            </div>
          </div>
          <h3 style="font-size:16px;margin-bottom:14px">📁 四种题型 Skill</h3>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin-bottom:24px">
            ${Object.entries(CARD_TYPES).map(([name, t]) => `
              <div style="border:1px solid ${t.color}22;border-radius:12px;padding:16px;background:${t.color}08">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
                  <span style="font-size:24px">${t.icon}</span>
                  <span style="font-weight:700;font-size:16px;color:${t.color}">${name}</span>
                  <span style="background:${t.color};color:#fff;padding:2px 8px;border-radius:10px;font-size:12px;margin-left:auto">${t.count}张</span>
                </div>
                <div style="font-size:13px;color:#666;margin-bottom:6px">${t.desc}</div>
                <div style="font-size:12px;color:#999">📌 ${t.examples}</div>
              </div>
            `).join('')}
          </div>
          <h3 style="font-size:16px;margin-bottom:14px">🎨 配色方案</h3>
          <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px">
            ${TEMPLATE_INFO.colors.map(c => `
              <div style="display:flex;align-items:center;gap:8px;padding:10px 16px;border-radius:10px;background:linear-gradient(135deg,${c.from},${c.to});min-width:160px">
                <span style="font-size:13px;font-weight:600;color:#333;text-shadow:0 0 4px rgba(255,255,255,.5)">${c.name}</span>
              </div>
            `).join('')}
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:24px">
            <span style="font-size:13px;color:#999;margin-right:8px">标题Banner色:</span>
            ${TEMPLATE_INFO.bannerColors.map(c => `<div style="width:32px;height:32px;border-radius:8px;background:${c}" title="${c}"></div>`).join('')}
          </div>
          <h3 style="font-size:16px;margin-bottom:14px">📝 文字规范</h3>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;margin-bottom:24px">
            ${TEMPLATE_INFO.textRules.map(r => `
              <div style="background:#f8f9fa;padding:10px 14px;border-radius:8px;display:flex;justify-content:space-between;align-items:center">
                <span style="font-size:13px;font-weight:500">${r.elem}</span>
                <span style="font-size:12px;color:var(--primary);background:#e8f0fe;padding:2px 8px;border-radius:6px">${r.limit}</span>
              </div>
            `).join('')}
          </div>
          <h3 style="font-size:16px;margin-bottom:14px">🚫 禁止事项</h3>
          <div style="display:flex;flex-wrap:wrap;gap:8px">
            ${TEMPLATE_INFO.dontList.map(d => `<span style="background:#fff1f0;color:#cf1322;padding:6px 14px;border-radius:20px;font-size:13px">❌ ${d}</span>`).join('')}
          </div>
        `;
      }

      function renderPrompts() {
        const el = document.getElementById('pl-panel-prompts');
        if (allCards.length === 0) { el.innerHTML = '<p style="color:#999">暂无卡片数据</p>'; return; }
        const types = [...new Set(allCards.map(c => c.type))];
        const units = [...new Set(allCards.map(c => c.unit_id))];
        el.innerHTML = `
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px">
            <select id="pl-filter-type" onchange="PromptLib.filterPrompts()" style="padding:6px 12px;border-radius:8px;border:1px solid #ddd;font-size:13px">
              <option value="">全部题型</option>
              ${types.map(t => '<option value="' + t + '">' + t + '</option>').join('')}
            </select>
            <select id="pl-filter-unit" onchange="PromptLib.filterPrompts()" style="padding:6px 12px;border-radius:8px;border:1px solid #ddd;font-size:13px">
              <option value="">全部单元</option>
              ${units.map(u => { const un = allCards.find(c => c.unit_id === u); return '<option value="' + u + '">第' + u + '单元 ' + (un ? un.unit_name : u) + '</option>'; }).join('')}
            </select>
          </div>
          <div id="pl-prompts-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px"></div>
        `;
        filterPrompts();
      }

      function filterPrompts() {
        const tf = document.getElementById('pl-filter-type'), uf = document.getElementById('pl-filter-unit');
        const typeF = tf ? tf.value : '', unitF = uf ? uf.value : '';
        const grid = document.getElementById('pl-prompts-grid');
        if (!grid) return;
        let cards = allCards;
        if (typeF) cards = cards.filter(c => c.type === typeF);
        if (unitF) cards = cards.filter(c => c.unit_id === unitF);
        const tc = { '概念卡': '#54A0FF', '方法卡': '#FF9F43', '辨析卡': '#FF6B6B', '公式卡': '#5ECE7B' };
        grid.innerHTML = cards.map(c => {
          const color = tc[c.type] || '#999';
          const ex = c.example && c.example.question ? c.example.question.slice(0, 40) : '';
          const tip = c.memory_tip ? c.memory_tip.slice(0, 20) : '';
          return '<div onclick="PromptLib.showDetail(\'' + c.full_id + '\')" style="border:1px solid #e8e8e8;border-radius:12px;padding:14px;cursor:pointer;transition:all .2s;border-left:4px solid ' + color + '" onmouseenter="this.style.boxShadow=\'0 4px 16px rgba(0,0,0,.08)\'" onmouseleave="this.style.boxShadow=\'none\'">' +
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">' +
              '<span style="background:' + color + ';color:#fff;padding:2px 8px;border-radius:6px;font-size:11px">' + c.type + '</span>' +
              '<span style="font-weight:600;font-size:14px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + c.title + '</span>' +
            '</div>' +
            '<div style="font-size:12px;color:#999;margin-bottom:4px">📖 第' + c.unit_id + '单元 · ' + c.unit_name + '</div>' +
            (ex ? '<div style="font-size:12px;color:#666;margin-bottom:4px">📝 ' + ex + '…</div>' : '') +
            '<div style="display:flex;gap:6px;align-items:center;margin-top:6px">' +
              '<span style="font-size:11px;background:#f0f0f0;padding:2px 6px;border-radius:4px">难度 ' + '\u2b50'.repeat(c.difficulty) + '</span>' +
              (tip ? '<span style="font-size:11px;color:#999">💡' + tip + '</span>' : '') +
            '</div></div>';
        }).join('');
      }

      function showDetail(fullId) {
        const card = allCards.find(c => c.full_id === fullId);
        if (!card) return;
        const tc = { '概念卡': '#54A0FF', '方法卡': '#FF9F43', '辨析卡': '#FF6B6B', '公式卡': '#5ECE7B' };
        const color = tc[card.type] || '#999';
        const overlay = document.getElementById('pl-detail-overlay');
        const box = document.getElementById('pl-detail-box');
        const ex = card.example || {};
        const mistakes = card.mistakes || [];

        let html = '<button onclick="document.getElementById(\'pl-detail-overlay\').style.display=\'none\'" style="position:absolute;top:12px;right:16px;background:none;border:none;font-size:24px;cursor:pointer;color:#999">&times;</button>';
        html += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:16px"><span style="background:' + color + ';color:#fff;padding:4px 12px;border-radius:8px;font-size:13px">' + card.type + '</span><h2 style="margin:0;font-size:20px">' + card.full_id + '</h2></div>';
        html += '<h3 style="margin:0 0 12px;font-size:17px;color:#666">' + card.title + '</h3>';

        // 知识点信息
        html += '<div style="background:#f8f9fa;border-radius:10px;padding:14px;margin-bottom:16px">';
        html += '<div style="font-size:13px;margin-bottom:6px"><strong>📖 定义:</strong> ' + (card.definition || '') + '</div>';
        html += '<div style="font-size:13px;margin-bottom:6px"><strong>🔑 核心要点:</strong></div>';
        html += '<ul style="margin:4px 0 8px;padding-left:20px;font-size:13px">' + (card.core_points || []).map(function(p) { return '<li>' + p + '</li>'; }).join('') + '</ul>';
        html += '<div style="font-size:13px"><strong>💡 口诀:</strong> <span style="color:var(--primary);font-weight:500">' + (card.memory_tip || '') + '</span></div>';
        html += '</div>';

        // 例题
        if (ex.question) {
          html += '<div style="background:#fff9e6;border:1px solid #ffd700;border-radius:10px;padding:14px;margin-bottom:16px">';
          html += '<div style="font-weight:600;margin-bottom:6px;font-size:14px">📝 例题</div>';
          html += '<div style="font-size:13px;margin-bottom:8px">' + ex.question + '</div>';
          if (ex.steps) html += '<div style="font-size:12px;color:#666"><strong>解题步骤:</strong><ol style="margin:4px 0;padding-left:18px">' + ex.steps.map(function(s) { return '<li>' + s + '</li>'; }).join('') + '</ol></div>';
          if (ex.answer) html += '<div style="font-size:13px;font-weight:600;color:#2e7d32">\u2705 ' + ex.answer + '</div>';
          html += '</div>';
        }

        // 易错点
        if (mistakes.length > 0) {
          html += '<div style="background:#fff1f0;border:1px solid #ffccc7;border-radius:10px;padding:14px;margin-bottom:16px">';
          html += '<div style="font-weight:600;margin-bottom:6px;font-size:14px">⚠️ 易错点</div>';
          mistakes.forEach(function(m) {
            html += '<div style="font-size:13px;margin-bottom:4px">\u274c ' + m.wrong + '</div>';
            html += '<div style="font-size:13px;color:#2e7d32">\u2705 ' + m.correct + '</div>';
          });
          html += '</div>';
        }

        // 元数据
        html += '<div style="background:#f0f8ff;border-radius:10px;padding:14px"><div style="font-weight:600;margin-bottom:8px;font-size:14px">📊 元数据</div>';
        html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:12px">';
        html += '<div><strong>card_id:</strong> ' + card.full_id + '</div>';
        html += '<div><strong>题型:</strong> ' + card.type + '</div>';
        html += '<div><strong>难度:</strong> ' + card.difficulty + '/5</div>';
        html += '<div><strong>单元:</strong> 第' + card.unit_id + '单元</div>';
        html += '<div><strong>Prompt版本:</strong> ' + TEMPLATE_INFO.version + '</div>';
        html += '<div><strong>模型:</strong> ' + TEMPLATE_INFO.textModel + ' \u2192 ' + TEMPLATE_INFO.imageModel.split(' (')[0] + '</div>';
        html += '</div></div>';

        box.innerHTML = html;
        overlay.style.display = '';
      }

      function renderTemplate() {
        const el = document.getElementById('pl-panel-template');
        const T = TEMPLATE_INFO;
        let html = '<div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">';
        html += '<span style="background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:6px 16px;border-radius:10px;font-weight:700;font-size:18px">' + T.version + '</span>';
        html += '<span style="font-size:14px;color:#999">' + T.date + '</span></div>';

        html += '<h3 style="font-size:15px;margin-bottom:12px">🤖 模型配置</h3>';
        html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px">';
        html += '<div style="background:#f0f8ff;padding:12px;border-radius:10px"><div style="font-size:12px;color:#999">文字模型 (Step 1)</div><div style="font-weight:600;font-size:14px;margin-top:4px">' + T.textModel + '</div><div style="font-size:11px;color:#999;margin-top:2px">thinkingBudget: 2048 | maxOutputTokens: 8192</div></div>';
        html += '<div style="background:#f0fff4;padding:12px;border-radius:10px"><div style="font-size:12px;color:#999">图片模型 (Step 2)</div><div style="font-weight:600;font-size:14px;margin-top:4px">' + T.imageModel + '</div><div style="font-size:11px;color:#999;margin-top:2px">responseModalities: TEXT + IMAGE</div></div></div>';

        html += '<h3 style="font-size:15px;margin-bottom:12px">📐 卡片布局</h3>';
        html += '<div style="border:1px solid #e8e8e8;border-radius:12px;overflow:hidden;margin-bottom:20px">';
        T.layout.forEach(function(l, i) {
          const bg = i === 2 ? '#fff9e6' : i === 3 ? '#f0f8ff' : '#fff';
          html += '<div style="display:flex;align-items:center;padding:10px 16px;' + (i > 0 ? 'border-top:1px solid #e8e8e8;' : '') + 'background:' + bg + '">';
          html += '<code style="background:#e8e8e8;padding:2px 8px;border-radius:4px;font-size:12px;min-width:70px;text-align:center">' + l.zone + '</code>';
          html += '<span style="font-size:12px;color:#999;min-width:40px;text-align:center;margin:0 10px">' + l.pct + '</span>';
          html += '<span style="font-size:13px;flex:1">' + l.desc + '</span></div>';
        });
        html += '</div>';

        html += '<h3 style="font-size:15px;margin-bottom:12px">🎨 配色方案</h3><div style="margin-bottom:20px">';
        html += '<div style="font-size:13px;font-weight:500;margin-bottom:8px">背景渐变 (4选1)</div><div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px">';
        T.colors.forEach(function(c) {
          html += '<div style="width:140px;height:48px;border-radius:10px;background:linear-gradient(135deg,' + c.from + ',' + c.to + ');display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;color:#555;text-shadow:0 0 3px rgba(255,255,255,.6)">' + c.name + '<br><span style="font-size:10px">' + c.from + '\u2192' + c.to + '</span></div>';
        });
        html += '</div>';
        html += '<div style="font-size:13px;font-weight:500;margin-bottom:8px">标题Banner色</div><div style="display:flex;gap:8px;margin-bottom:14px">';
        T.bannerColors.forEach(function(c) {
          html += '<div style="display:flex;align-items:center;gap:6px"><div style="width:28px;height:28px;border-radius:6px;background:' + c + '"></div><code style="font-size:11px">' + c + '</code></div>';
        });
        html += '</div>';
        html += '<div style="display:flex;gap:16px"><div style="display:flex;align-items:center;gap:6px"><div style="width:24px;height:24px;border-radius:6px;background:#2ED573"></div><span style="font-size:12px">\u2713 正确 #2ED573</span></div>';
        html += '<div style="display:flex;align-items:center;gap:6px"><div style="width:24px;height:24px;border-radius:6px;background:#FF4757"></div><span style="font-size:12px">\u2717 错误 #FF4757</span></div></div></div>';

        html += '<h3 style="font-size:15px;margin-bottom:12px">📝 文字规范</h3>';
        html += '<table style="width:100%;border-collapse:collapse;margin-bottom:20px;font-size:13px"><thead><tr style="background:#f8f9fa"><th style="padding:8px 12px;text-align:left;border-bottom:2px solid #e8e8e8">元素</th><th style="padding:8px 12px;text-align:left;border-bottom:2px solid #e8e8e8">限制</th></tr></thead><tbody>';
        T.textRules.forEach(function(r) {
          html += '<tr><td style="padding:8px 12px;border-bottom:1px solid #f0f0f0">' + r.elem + '</td><td style="padding:8px 12px;border-bottom:1px solid #f0f0f0"><code style="background:#e8f5e9;padding:2px 6px;border-radius:4px">' + r.limit + '</code></td></tr>';
        });
        html += '</tbody></table>';

        html += '<h3 style="font-size:15px;margin-bottom:12px">🚫 禁止事项</h3><div style="display:flex;flex-wrap:wrap;gap:8px">';
        T.dontList.forEach(function(d) { html += '<span style="background:#fff1f0;color:#cf1322;padding:6px 14px;border-radius:20px;font-size:13px">\u274c ' + d + '</span>'; });
        html += '</div>';

        el.innerHTML = html;
      }

      function renderChangelog() {
        const el = document.getElementById('pl-panel-changelog');
        let html = '<div style="position:relative;padding-left:28px"><div style="position:absolute;left:10px;top:0;bottom:0;width:2px;background:linear-gradient(to bottom,var(--primary),#e8e8e8)"></div>';
        CHANGELOG.forEach(function(log, i) {
          html += '<div style="position:relative;margin-bottom:24px">';
          html += '<div style="position:absolute;left:-23px;top:4px;width:12px;height:12px;border-radius:50%;background:' + (i === 0 ? 'var(--primary)' : '#ccc') + ';border:2px solid #fff;box-shadow:0 0 0 2px ' + (i === 0 ? 'var(--primary)' : '#ddd') + '"></div>';
          html += '<div style="border:1px solid ' + (i === 0 ? 'rgba(102,126,234,.25)' : '#e8e8e8') + ';border-radius:12px;padding:16px;' + (i === 0 ? 'background:linear-gradient(135deg,#f0f4ff,#fff)' : '') + '">';
          html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">';
          html += '<span style="background:' + (i === 0 ? 'var(--primary)' : '#999') + ';color:#fff;padding:3px 10px;border-radius:6px;font-weight:700;font-size:13px">' + log.ver + '</span>';
          html += '<span style="font-size:13px;color:#999">' + log.date + '</span>';
          if (i === 0) html += '<span style="background:#e8f5e9;color:#2e7d32;padding:2px 8px;border-radius:6px;font-size:11px">当前版本</span>';
          html += '</div>';
          html += '<div style="font-weight:600;font-size:15px;margin-bottom:6px">' + log.title + '</div>';
          html += '<div style="font-size:13px;color:#999;margin-bottom:8px">\ud83d\udcac 问题: ' + log.problem + '</div>';
          html += '<div style="font-size:13px">';
          log.changes.forEach(function(c) { html += '<div style="padding:2px 0">\u2705 ' + c + '</div>'; });
          html += '</div></div></div>';
        });
        html += '</div>';
        el.innerHTML = html;
      }

      return { init, switchTab, filterPrompts, showDetail };
    })();
'''

# Insert the module
new_data = data[:insert_pos] + MODULE + data[insert_pos:]
open(fpath, 'w', encoding='utf-8').write(new_data)
print(f"OK. Inserted PromptLib module ({len(MODULE)} chars) at position {insert_pos}")
print(f"File size: {len(data)} -> {len(new_data)}")
