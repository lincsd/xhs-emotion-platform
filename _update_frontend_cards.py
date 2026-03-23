"""
Replace the KnowledgeCards module in public/index.html
to support multi-grade dynamic loading.
"""
import os, re

HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public', 'index.html')

# Read
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the module boundaries
# Start marker: "// ============ 知识卡片模块"
# End marker: the closing "})();" of the IIFE followed by the next module comment

START_MARKER = '// ============ \ufffd 知识卡片模块 ============'
# Also try without the garbled char
if START_MARKER not in content:
    # Try with different patterns
    patterns = [
        re.compile(r'// =+ .{0,5}知识卡片模块.{0,5} =+'),
    ]
    for pat in patterns:
        m = pat.search(content)
        if m:
            START_MARKER = m.group(0)
            break

END_MARKER = "return { init, selectUnit, showDetail, downloadCard, switchPack, _getPacks: () => PACKS };\n    })();"

if START_MARKER not in content:
    print(f"ERROR: Could not find start marker. Looking for '知识卡片模块'")
    # Try simpler search
    idx = content.find('知识卡片模块')
    if idx >= 0:
        # Find the start of the line
        line_start = content.rfind('\n', 0, idx)
        snippet = content[line_start:idx+50]
        print(f"Found at position {idx}: ...{snippet}...")
    exit(1)

if END_MARKER not in content:
    print(f"ERROR: Could not find end marker")
    exit(1)

start_idx = content.index(START_MARKER)
end_idx = content.index(END_MARKER) + len(END_MARKER)

# The new module
NEW_MODULE = r'''// ============ 📚 知识卡片模块 (多年级版) ============
    const KnowledgeCards = (() => {
      // ── 配置 ──
      const GRADES_ORDER = ['一上','一下','二上','二下','三上','三下','四上','四下','五上','五下','六上','六下'];
      const GRADE_LABELS = {
        '一上':'一年级上册','一下':'一年级下册','二上':'二年级上册','二下':'二年级下册',
        '三上':'三年级上册','三下':'三年级下册','四上':'四年级上册','四下':'四年级下册',
        '五上':'五年级上册','五下':'五年级下册','六上':'六年级上册','六下':'六年级下册'
      };

      // ── 状态 ──
      let PACKS = [];           // [标准卡片包, 爆款卡片包]
      let activePack = null;
      let activeUnitId = null;
      let currentGrade = '三下'; // 默认年级
      let isLoading = false;
      let cardCache = {};        // { '三下': [stdPack, boomPack], ... }

      // ── 基础路径（兼容 GitHub Pages / 本地 / Tunnel）──
      function getBasePath() {
        // 判断是否在 GitHub Pages 上
        const loc = window.location;
        if (loc.hostname.includes('github.io')) {
          // GitHub Pages: /xhs-emotion-platform/knowledge_cards/小学/
          const pathPrefix = loc.pathname.replace(/\/[^/]*$/, '');
          return pathPrefix + '/knowledge_cards/小学/';
        }
        // 本地或 tunnel: /knowledge_cards/小学/
        return 'knowledge_cards/小学/';
      }

      // ── 加载卡片数据 ──
      async function loadGrade(gradeShort) {
        if (cardCache[gradeShort]) {
          PACKS = cardCache[gradeShort];
          currentGrade = gradeShort;
          activePack = PACKS[0];
          return true;
        }

        const base = getBasePath();
        const stdFile = `${base}数学_${gradeShort}.json`;
        const boomFile = `${base}数学_${gradeShort}_爆款.json`;

        try {
          isLoading = true;
          renderLoading();
          const [stdResp, boomResp] = await Promise.all([
            fetch(encodeURI(stdFile)),
            fetch(encodeURI(boomFile)).catch(() => null)
          ]);

          const packs = [];
          if (stdResp && stdResp.ok) {
            const stdData = await stdResp.json();
            stdData.total_cards = (stdData.units || []).reduce((s,u) => s + (u.cards||[]).length, 0);
            packs.push(stdData);
          }
          if (boomResp && boomResp.ok) {
            const boomData = await boomResp.json();
            boomData.total_cards = (boomData.units || []).reduce((s,u) => s + (u.cards||[]).length, 0);
            packs.push(boomData);
          }

          if (packs.length === 0) throw new Error('无数据');

          PACKS = packs;
          cardCache[gradeShort] = packs;
          currentGrade = gradeShort;
          activePack = PACKS[0];
          isLoading = false;
          return true;
        } catch(e) {
          console.warn('加载卡片失败:', gradeShort, e);
          isLoading = false;
          return false;
        }
      }

      function renderLoading() {
        const grid = document.getElementById('kc-card-grid');
        if (grid) grid.innerHTML = '<div style="text-align:center;padding:60px;color:#999;font-size:15px">⏳ 加载中...</div>';
      }

      function renderError(msg) {
        const grid = document.getElementById('kc-card-grid');
        if (grid) grid.innerHTML = `<div style="text-align:center;padding:60px;color:#c62828;font-size:15px">❌ ${msg}</div>`;
      }

      // ── 初始化 ──
      async function init() {
        const filterBar = document.getElementById('kc-filter-bar');
        if (!filterBar) return;

        // 渲染年级选择器
        renderGradeSelector(filterBar);

        // 加载当前年级
        const ok = await loadGrade(currentGrade);
        if (!ok) {
          renderError('加载失败，请检查网络');
          return;
        }
        renderPackInfo(filterBar);
        renderUnitTabs();
        if (activePack.units.length > 0) selectUnit(activePack.units[0].unit_id);
      }

      function renderGradeSelector(filterBar) {
        // 年级选择器
        const gradeHtml = GRADES_ORDER.map(g => {
          const active = g === currentGrade;
          const label = g;
          return `<button onclick="KnowledgeCards.switchGrade('${g}')"
            class="kc-grade-btn" data-grade="${g}"
            style="padding:5px 12px;border-radius:16px;border:2px solid ${active?'#667eea':'#e0e0e0'};
            background:${active?'linear-gradient(135deg,#667eea,#764ba2)':'#fff'};
            color:${active?'#fff':'#555'};cursor:pointer;font-size:13px;font-weight:${active?'600':'400'};
            transition:all .2s;white-space:nowrap">${active?'📖 ':''}${label}</button>`;
        }).join('');

        // 保留或创建年级选择区域
        let gradeBar = filterBar.querySelector('.kc-grade-bar');
        if (!gradeBar) {
          gradeBar = document.createElement('div');
          gradeBar.className = 'kc-grade-bar';
          gradeBar.style.cssText = 'display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid #eee';
          filterBar.prepend(gradeBar);
        }
        gradeBar.innerHTML = `<span style="font-weight:700;font-size:14px;color:#333;margin-right:4px">📚 年级：</span>${gradeHtml}`;
      }

      function renderPackInfo(filterBar) {
        // 卡片包切换 + 信息区
        let infoArea = filterBar.querySelector('.kc-info-area');
        if (!infoArea) {
          infoArea = document.createElement('div');
          infoArea.className = 'kc-info-area';
          filterBar.appendChild(infoArea);
        }

        const packBtns = PACKS.map((p, i) => {
          const label = p.card_pack || (p.grade + p.semester);
          const active = p === activePack;
          return `<button onclick="KnowledgeCards.switchPack(${i})" style="padding:5px 14px;border-radius:20px;border:2px solid ${active?'#667eea':'#ddd'};background:${active?'#667eea':'#fff'};color:${active?'#fff':'#333'};cursor:pointer;font-size:13px;font-weight:${active?'600':'400'};transition:.2s">${active?'📦 ':''} ${label} (${p.total_cards || '?'})</button>`;
        }).join('');

        infoArea.innerHTML = `
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px">
            <span style="font-weight:600;font-size:13px;color:#555">卡片包：</span>${packBtns}
          </div>
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <span style="background:#e8f5e9;color:#2e7d32;padding:4px 12px;border-radius:20px;font-size:13px">📖 ${activePack.textbook || '人教版'}</span>
            <span style="background:#e3f2fd;color:#1565c0;padding:4px 12px;border-radius:20px;font-size:13px">📐 ${activePack.subject || '数学'}</span>
            <span style="background:#fce4ec;color:#c62828;padding:4px 12px;border-radius:20px;font-size:13px">🎓 ${activePack.grade || ''}${activePack.semester || ''}</span>
            <span style="background:#f3e5f5;color:#6a1b9a;padding:4px 12px;border-radius:20px;font-size:13px">📝 ${activePack.total_cards || 0}张卡片</span>
          </div>`;
      }

      // ── 切换年级 ──
      async function switchGrade(gradeShort) {
        if (gradeShort === currentGrade && PACKS.length > 0) return;
        const filterBar = document.getElementById('kc-filter-bar');

        // 更新按钮样式
        document.querySelectorAll('.kc-grade-btn').forEach(b => {
          const on = b.dataset.grade === gradeShort;
          b.style.border = on ? '2px solid #667eea' : '2px solid #e0e0e0';
          b.style.background = on ? 'linear-gradient(135deg,#667eea,#764ba2)' : '#fff';
          b.style.color = on ? '#fff' : '#555';
          b.style.fontWeight = on ? '600' : '400';
          b.textContent = (on ? '📖 ' : '') + gradeShort;
        });

        const ok = await loadGrade(gradeShort);
        if (!ok) {
          renderError(`加载 ${GRADE_LABELS[gradeShort] || gradeShort} 失败`);
          return;
        }
        renderPackInfo(filterBar);
        renderUnitTabs();
        if (activePack.units.length > 0) selectUnit(activePack.units[0].unit_id);
      }

      function switchPack(idx) {
        if (idx >= 0 && idx < PACKS.length) {
          activePack = PACKS[idx];
          activeUnitId = null;
          const filterBar = document.getElementById('kc-filter-bar');
          renderPackInfo(filterBar);
          renderUnitTabs();
          if (activePack.units.length > 0) selectUnit(activePack.units[0].unit_id);
        }
      }

      function renderUnitTabs() {
        const c = document.getElementById('kc-unit-tabs');
        if (!c || !activePack) return;
        c.innerHTML = activePack.units.map(u =>
          `<button class="kc-unit-btn" data-uid="${u.unit_id}" onclick="KnowledgeCards.selectUnit('${u.unit_id}')"
            style="padding:6px 14px;border-radius:20px;border:1px solid #ddd;background:#fff;cursor:pointer;font-size:13px;white-space:nowrap;transition:.2s">
            ${u.unit_id} ${u.unit_name} <span style="color:#999;font-size:11px">(${u.cards.length})</span></button>`
        ).join('');
      }

      function selectUnit(uid) {
        activeUnitId = uid;
        document.querySelectorAll('.kc-unit-btn').forEach(b => {
          const on = b.dataset.uid === uid;
          b.style.background = on ? '#667eea' : '#fff';
          b.style.color = on ? '#fff' : '#333';
          b.style.borderColor = on ? '#667eea' : '#ddd';
        });
        const unit = activePack.units.find(u => u.unit_id === uid);
        if (unit) renderCards(unit);
      }

      const _tc = {
        '概念卡': { bg:'#e3f2fd', fg:'#1565c0', icon:'💡' },
        '方法卡': { bg:'#e8f5e9', fg:'#2e7d32', icon:'🔧' },
        '公式卡': { bg:'#fff3e0', fg:'#e65100', icon:'📐' },
        '辨析卡': { bg:'#fce4ec', fg:'#c62828', icon:'🔍' },
        '易错卡': { bg:'#f3e5f5', fg:'#6a1b9a', icon:'⚠️' },
        '陷阱卡': { bg:'#fff3e0', fg:'#e65100', icon:'⚡' },
        '速算卡': { bg:'#e0f7fa', fg:'#00838f', icon:'🚀' },
        '挑战卡': { bg:'#fce4ec', fg:'#ad1457', icon:'🏆' },
        '生活卡': { bg:'#e8f5e9', fg:'#2e7d32', icon:'🛒' },
        '对战卡': { bg:'#f3e5f5', fg:'#6a1b9a', icon:'⚔️' },
        '思维卡': { bg:'#e8eaf6', fg:'#283593', icon:'🧠' }
      };
      const _stars = n => '★'.repeat(n) + '☆'.repeat(5 - n);

      function renderCards(unit) {
        const grid = document.getElementById('kc-card-grid');
        if (!grid) return;
        grid.innerHTML = unit.cards.map(c => {
          const tc = _tc[c.type] || { bg:'#f5f5f5', fg:'#333', icon:'📄' };
          const hookHtml = c.emotion_hook ? `<div style="font-size:12px;color:#e65100;margin-top:6px;font-style:italic">💥 ${c.emotion_hook}</div>` : '';
          return `<div onclick="KnowledgeCards.showDetail('${c.full_id}')"
            style="background:#fff;border-radius:14px;padding:18px;cursor:pointer;border:1px solid #eee;transition:.2s;box-shadow:0 2px 8px rgba(0,0,0,.04)"
            onmouseover="this.style.boxShadow='0 4px 16px rgba(102,126,234,.15)';this.style.borderColor='#667eea'"
            onmouseout="this.style.boxShadow='0 2px 8px rgba(0,0,0,.04)';this.style.borderColor='#eee'">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
              <span style="background:${tc.bg};color:${tc.fg};padding:2px 10px;border-radius:12px;font-size:12px">${tc.icon} ${c.type}</span>
              <span style="color:#999;font-size:11px">${c.card_id}</span>
            </div>
            <div style="font-size:15px;font-weight:600;color:#333;margin-bottom:10px;line-height:1.4">${c.title}</div>
            <div style="font-size:13px;color:#666;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">${c.definition}</div>
            ${hookHtml}
            <div style="display:flex;justify-content:space-between;margin-top:12px;font-size:12px;color:#999">
              <span>难度 <span style="color:#ff9800">${_stars(c.difficulty)}</span></span>
              <span>重要 <span style="color:#f44336">${_stars(c.importance)}</span></span>
            </div></div>`;
        }).join('');
      }

      function showDetail(fullId) {
        let card = null;
        for (const u of activePack.units) { card = u.cards.find(c => c.full_id === fullId); if (card) break; }
        if (!card) return;
        const tc = _tc[card.type] || { bg:'#f5f5f5', fg:'#333', icon:'📄' };
        const box = document.getElementById('kc-detail-box');
        // 爆款卡特有字段
        const hookHtml = card.emotion_hook ? `<div style="background:#fff3e0;border-radius:12px;padding:16px;margin-bottom:14px;border-left:4px solid #ff9800">
          <div style="font-size:13px;font-weight:600;color:#e65100;margin-bottom:6px">💥 情绪钩子</div>
          <div style="font-size:15px;color:#333;font-weight:500;line-height:1.6">${card.emotion_hook}</div></div>` : '';
        const trapHtml = card.trap_point ? `<div style="background:#fff8e1;border-radius:12px;padding:16px;margin-bottom:14px">
          <div style="font-size:13px;font-weight:600;color:#f57f17;margin-bottom:6px">🪤 陷阱点</div>
          <div style="font-size:14px;color:#333">${card.trap_point}</div></div>` : '';

        box.innerHTML = `
          <div style="text-align:right"><button onclick="document.getElementById('kc-detail-overlay').style.display='none'" style="background:none;border:none;font-size:22px;cursor:pointer;color:#999">✕</button></div>
          <div style="text-align:center;margin-bottom:18px">
            <span style="background:${tc.bg};color:${tc.fg};padding:4px 16px;border-radius:20px;font-size:13px">${tc.icon} ${card.type}</span>
            <span style="color:#999;font-size:12px;margin-left:8px">${card.full_id}</span>
          </div>
          <h3 style="text-align:center;font-size:20px;color:#333;margin:0 0 6px">${card.title}</h3>
          <div style="text-align:center;font-size:12px;color:#999;margin-bottom:18px">
            难度 <span style="color:#ff9800">${_stars(card.difficulty)}</span> &nbsp; 重要 <span style="color:#f44336">${_stars(card.importance)}</span>
          </div>
          ${hookHtml}
          <div style="background:#f8f9fa;border-radius:12px;padding:16px;margin-bottom:14px">
            <div style="font-size:13px;font-weight:600;color:${tc.fg};margin-bottom:6px">📖 定义</div>
            <div style="font-size:14px;color:#333;line-height:1.6">${card.definition}</div>
          </div>
          <div style="background:#f8f9fa;border-radius:12px;padding:16px;margin-bottom:14px">
            <div style="font-size:13px;font-weight:600;color:${tc.fg};margin-bottom:6px">🎯 核心要点</div>
            <ul style="margin:0;padding-left:18px">${card.core_points.map(p => `<li style="font-size:13px;color:#444;line-height:1.7;margin-bottom:4px">${p}</li>`).join('')}</ul>
          </div>
          <div style="background:#fffde7;border-radius:12px;padding:16px;margin-bottom:14px;border-left:4px solid #ffd54f">
            <div style="font-size:13px;font-weight:600;color:#f57f17;margin-bottom:6px">📝 例题</div>
            <div style="font-size:14px;color:#333;font-weight:500;margin-bottom:8px">${card.example.question}</div>
            <div style="font-size:13px;color:#555">${card.example.steps.map(s => `<div style="margin-bottom:4px">${s}</div>`).join('')}</div>
            <div style="font-size:14px;color:#2e7d32;font-weight:600;margin-top:8px;padding-top:8px;border-top:1px dashed #c8e6c9">✅ ${card.example.answer}</div>
          </div>
          ${trapHtml}
          <div style="background:#ffebee;border-radius:12px;padding:16px;margin-bottom:14px">
            <div style="font-size:13px;font-weight:600;color:#c62828;margin-bottom:6px">⚠️ 易错提醒</div>
            ${card.mistakes.map(m => `<div style="margin-bottom:8px"><div style="font-size:13px;color:#c62828">❌ ${m.wrong}</div><div style="font-size:13px;color:#2e7d32;margin-top:2px">✅ ${m.correct}</div></div>`).join('')}
          </div>
          <div style="background:#e8f5e9;border-radius:12px;padding:16px;margin-bottom:14px">
            <div style="font-size:13px;font-weight:600;color:#2e7d32;margin-bottom:6px">💡 记忆技巧</div>
            <div style="font-size:14px;color:#333;line-height:1.6">${card.memory_tip}</div>
          </div>
          <div style="background:#f3e5f5;border-radius:12px;padding:16px;margin-bottom:18px">
            <div style="font-size:13px;font-weight:600;color:#6a1b9a;margin-bottom:6px">🔗 关联知识</div>
            <div style="font-size:13px;color:#555">前置：${card.related.prerequisite}</div>
            <div style="font-size:13px;color:#555;margin-top:4px">后续：${card.related.next}</div>
          </div>
          <div style="text-align:center">
            <button onclick="KnowledgeCards.downloadCard('${card.full_id}')" style="background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border:none;padding:10px 28px;border-radius:24px;font-size:14px;cursor:pointer;box-shadow:0 4px 12px rgba(102,126,234,.3)">📥 下载卡片图片</button>
          </div>`;
        document.getElementById('kc-detail-overlay').style.display = 'block';
      }

      /* === Canvas card image generation === */
      function downloadCard(fullId) {
        let card = null;
        for (const u of activePack.units) { card = u.cards.find(c => c.full_id === fullId); if (card) break; }
        if (!card) return;
        const canvas = document.getElementById('kc-canvas');
        const ctx = canvas.getContext('2d');
        const W = 750, H = 1334;
        canvas.width = W; canvas.height = H;

        const themes = {
          '概念卡':{ p:'#1565c0', l:'#e3f2fd', a:'#42a5f5' },
          '方法卡':{ p:'#2e7d32', l:'#e8f5e9', a:'#66bb6a' },
          '公式卡':{ p:'#e65100', l:'#fff3e0', a:'#ff9800' },
          '辨析卡':{ p:'#c62828', l:'#ffebee', a:'#ef5350' },
          '易错卡':{ p:'#6a1b9a', l:'#f3e5f5', a:'#ab47bc' },
          '陷阱卡':{ p:'#e65100', l:'#fff3e0', a:'#ff9800' },
          '速算卡':{ p:'#00838f', l:'#e0f7fa', a:'#26c6da' },
          '挑战卡':{ p:'#ad1457', l:'#fce4ec', a:'#ec407a' },
          '生活卡':{ p:'#2e7d32', l:'#e8f5e9', a:'#66bb6a' },
          '对战卡':{ p:'#6a1b9a', l:'#f3e5f5', a:'#ab47bc' },
          '思维卡':{ p:'#283593', l:'#e8eaf6', a:'#5c6bc0' }
        };
        const th = themes[card.type] || { p:'#333', l:'#f5f5f5', a:'#999' };

        // bg
        const grad = ctx.createLinearGradient(0,0,0,H);
        grad.addColorStop(0,'#f8f9ff'); grad.addColorStop(1,'#eef1ff');
        ctx.fillStyle = grad; ctx.fillRect(0,0,W,H);

        // banner
        const bg = ctx.createLinearGradient(0,0,W,0);
        bg.addColorStop(0,th.p); bg.addColorStop(1,th.a);
        ctx.fillStyle = bg; ctx.fillRect(0,0,W,180);

        // type badge
        ctx.fillStyle = 'rgba(255,255,255,0.25)';
        _rr(ctx,30,24,100,32,16); ctx.fill();
        ctx.font = '600 16px sans-serif'; ctx.fillStyle = '#fff';
        ctx.fillText(card.type, 50, 46);
        ctx.font = '14px sans-serif'; ctx.fillStyle = 'rgba(255,255,255,0.7)';
        ctx.textAlign = 'right'; ctx.fillText(card.full_id, W-30, 46); ctx.textAlign = 'left';

        // title
        ctx.font = '700 26px sans-serif'; ctx.fillStyle = '#fff';
        _wt(ctx, card.title, 30, 100, W-60, 34);
        ctx.font = '14px sans-serif'; ctx.fillStyle = 'rgba(255,255,255,0.8)';
        ctx.fillText('难度 '+_stars(card.difficulty)+'  重要 '+_stars(card.importance), 30, 162);

        let y = 200;
        y = _sec(ctx,'📖 定义',card.definition,30,y,W-60,th);
        y = _secList(ctx,'🎯 核心要点',card.core_points,30,y,W-60,th);
        y = _secEx(ctx,card.example,30,y,W-60);
        if (card.mistakes.length>0 && y<H-220) y = _secMis(ctx,card.mistakes[0],30,y,W-60);
        if (y<H-120) y = _sec(ctx,'💡 记忆技巧',card.memory_tip,30,y,W-60,{p:'#2e7d32',l:'#e8f5e9'});

        // bottom
        ctx.fillStyle = th.p; ctx.fillRect(0,H-48,W,48);
        ctx.font = '13px sans-serif'; ctx.fillStyle = 'rgba(255,255,255,0.8)';
        ctx.textAlign = 'center'; ctx.fillText('小红书AI创作平台 · 知识卡片', W/2, H-20); ctx.textAlign = 'left';

        const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
        const dlBox = document.createElement('div');
        dlBox.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:10000;background:rgba(0,0,0,.7);display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px';
        dlBox.onclick = () => dlBox.remove();
        const img = document.createElement('img');
        img.src = dataUrl;
        img.style.cssText = 'max-width:90%;max-height:80vh;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.3)';
        const tip = document.createElement('div');
        tip.style.cssText = 'color:#fff;margin-top:12px;font-size:14px';
        tip.textContent = '📱 长按图片保存 · 点击任意处关闭';
        dlBox.appendChild(img); dlBox.appendChild(tip);
        document.body.appendChild(dlBox);
      }

      /* canvas helpers */
      function _rr(ctx,x,y,w,h,r){ctx.beginPath();ctx.moveTo(x+r,y);ctx.lineTo(x+w-r,y);ctx.quadraticCurveTo(x+w,y,x+w,y+r);ctx.lineTo(x+w,y+h-r);ctx.quadraticCurveTo(x+w,y+h,x+w-r,y+h);ctx.lineTo(x+r,y+h);ctx.quadraticCurveTo(x,y+h,x,y+h-r);ctx.lineTo(x,y+r);ctx.quadraticCurveTo(x,y,x+r,y);ctx.closePath();}

      function _wt(ctx,text,x,y,mw,lh){
        let line='',cy=y;
        for(const ch of text){const t=line+ch;if(ctx.measureText(t).width>mw&&line){ctx.fillText(line,x,cy);line=ch;cy+=lh;}else line=t;}
        if(line)ctx.fillText(line,x,cy);return cy+lh;
      }

      function _gl(ctx,text,mw,font){
        ctx.save();ctx.font=font;const lines=[];
        for(const para of text.split('\n')){let line='';for(const ch of para){if(ctx.measureText(line+ch).width>mw&&line){lines.push(line);line=ch;}else line+=ch;}if(line)lines.push(line);else if(para==='')lines.push('');}
        ctx.restore();return lines;
      }

      function _sec(ctx,label,text,x,y,w,th){
        ctx.font='15px sans-serif';const lines=_gl(ctx,text,w-32,'15px sans-serif');const bh=36+lines.length*22+12;
        ctx.fillStyle=th.l;_rr(ctx,x,y,w,bh,12);ctx.fill();
        ctx.font='600 14px sans-serif';ctx.fillStyle=th.p;ctx.fillText(label,x+16,y+24);
        ctx.font='15px sans-serif';ctx.fillStyle='#333';let ty=y+48;
        for(const l of lines){ctx.fillText(l,x+16,ty);ty+=22;}return y+bh+12;
      }

      function _secList(ctx,label,items,x,y,w,th){
        ctx.font='14px sans-serif';let tot=36;const all=[];
        for(const it of items){const ls=_gl(ctx,'• '+it,w-40,'14px sans-serif');all.push(ls);tot+=ls.length*20+4;}tot+=8;
        ctx.fillStyle=th.l;_rr(ctx,x,y,w,tot,12);ctx.fill();
        ctx.font='600 14px sans-serif';ctx.fillStyle=th.p;ctx.fillText(label,x+16,y+24);
        ctx.font='14px sans-serif';ctx.fillStyle='#444';let ty=y+48;
        for(const ls of all){for(const l of ls){ctx.fillText(l,x+16,ty);ty+=20;}ty+=4;}return y+tot+12;
      }

      function _secEx(ctx,ex,x,y,w){
        ctx.font='14px sans-serif';const ql=_gl(ctx,ex.question,w-40,'14px sans-serif');let tot=36+ql.length*20+12;
        const sl=[];for(const s of ex.steps){const ls=_gl(ctx,s,w-48,'13px sans-serif');sl.push(ls);tot+=ls.length*18+4;}
        const al=_gl(ctx,'✅ '+ex.answer,w-40,'14px sans-serif');tot+=al.length*20+16;
        ctx.fillStyle='#fffde7';_rr(ctx,x,y,w,tot,12);ctx.fill();
        ctx.fillStyle='#ffd54f';_rr(ctx,x,y,4,tot,2);ctx.fill();
        ctx.font='600 14px sans-serif';ctx.fillStyle='#f57f17';ctx.fillText('📝 例题',x+16,y+24);
        ctx.font='14px sans-serif';ctx.fillStyle='#333';let ty=y+48;
        for(const l of ql){ctx.fillText(l,x+16,ty);ty+=20;}ty+=4;
        ctx.font='13px sans-serif';ctx.fillStyle='#555';
        for(const ls of sl){for(const l of ls){ctx.fillText(l,x+24,ty);ty+=18;}ty+=4;}ty+=4;
        ctx.font='600 14px sans-serif';ctx.fillStyle='#2e7d32';
        for(const l of al){ctx.fillText(l,x+16,ty);ty+=20;}return y+tot+12;
      }

      function _secMis(ctx,m,x,y,w){
        ctx.font='13px sans-serif';
        const wl=_gl(ctx,'❌ '+m.wrong,w-40,'13px sans-serif');
        const cl=_gl(ctx,'✅ '+m.correct,w-40,'13px sans-serif');
        const tot=36+(wl.length+cl.length)*18+20;
        ctx.fillStyle='#ffebee';_rr(ctx,x,y,w,tot,12);ctx.fill();
        ctx.font='600 14px sans-serif';ctx.fillStyle='#c62828';ctx.fillText('⚠️ 易错提醒',x+16,y+24);
        ctx.font='13px sans-serif';let ty=y+48;
        ctx.fillStyle='#c62828';for(const l of wl){ctx.fillText(l,x+16,ty);ty+=18;}ty+=6;
        ctx.fillStyle='#2e7d32';for(const l of cl){ctx.fillText(l,x+16,ty);ty+=18;}return y+tot+12;
      }

      return { init, selectUnit, showDetail, downloadCard, switchPack, switchGrade, _getPacks: () => PACKS };
    })();'''

# Replace
new_content = content[:start_idx] + NEW_MODULE + content[end_idx:]

# Verify the size didn't shrink dramatically (sanity check)
old_len = len(content)
new_len = len(new_content)
print(f"Old size: {old_len} chars")
print(f"New size: {new_len} chars")
print(f"Module replaced: {start_idx} -> {end_idx} ({end_idx-start_idx} chars)")
print(f"New module size: {len(NEW_MODULE)} chars")

# Also update the section description 
new_content = new_content.replace(
    '<p class="section-desc">小学知识点卡片 · 按科目/年级/单元浏览 · 下载精美卡片图</p>',
    '<p class="section-desc">小学数学全年级知识卡 · 一年级到六年级 · 按年级/单元浏览 · 下载精美卡片图</p>'
)

# Write
with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ KnowledgeCards module replaced successfully!")
print("   - Dynamic card loading via fetch")
print("   - Grade selector with 12 grades")
print("   - Card caching")
print("   - Boom card type colors")
