const puppeteer = require('puppeteer-core');
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const URL = 'https://lincsd.github.io/xhs-emotion-platform/';
const https = require('https');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
async function shot(page, name) {
  try { await page.screenshot({ path: `_ss_${name}.png` }); console.log(`  📸 _ss_${name}.png`); }
  catch(e) {}
}
function warmup() {
  return new Promise(resolve => {
    https.get('https://xhs-gemini-proxy.onrender.com/api/version', res => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => { console.log('  后端: ' + d.trim()); resolve(); });
    }).on('error', () => resolve());
  });
}

(async () => {
  console.log('=== 前端功能测试 (v2) ===\n');

  // 唤醒后端
  console.log('🔄 唤醒后端...');
  await warmup();
  await warmup();

  // 等 GitHub Pages 更新 (index.html 有改动)
  console.log('⏳ 等待35s让 GitHub Pages 更新...');
  await sleep(35000);

  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: false,
    defaultViewport: { width: 1400, height: 900 },
    args: ['--no-sandbox'], protocolTimeout: 600000
  });
  const page = await browser.newPage();

  // 收集控制台日志
  const logs = [];
  page.on('console', msg => {
    const t = msg.text();
    logs.push(t);
    if (t.includes('Error') || t.includes('失败') || t.includes('成功') ||
        t.includes('✅') || t.includes('❌') || t.includes('[ImageGen]') ||
        t.includes('CORS') || t.includes('502') || t.includes('重试') ||
        t.includes('搜索') || t.includes('创作') || t.includes('[Gemini]') ||
        t.includes('fetch') || t.includes('配额') || t.includes('网络错误') ||
        t.includes('生成') || t.includes('fallback') || t.includes('模板') ||
        t.includes('AI') || t.includes('百度') || t.includes('本地') ||
        t.includes('联网') || t.includes('轻量') || t.includes('grounding') ||
        t.includes('分析') || t.includes('检索'))
      console.log('  [LOG] ' + t.substring(0, 300));
  });
  page.on('requestfailed', req => {
    console.log('  [FAIL] ' + req.url().substring(0, 80) + ' — ' + (req.failure()?.errorText || ''));
  });

  try {
    // 加载 & 登录
    await page.goto(URL, { waitUntil: 'networkidle2', timeout: 60000 });
    await sleep(3000);

    // 验证 IS_LIGHT_AI_MODE 是否已禁用
    const lightMode = await page.evaluate(() => typeof IS_LIGHT_AI_MODE !== 'undefined' ? IS_LIGHT_AI_MODE : 'undefined');
    console.log('IS_LIGHT_AI_MODE = ' + lightMode + (lightMode === false ? ' ✅ (完整联网模式)' : ' ⚠️'));

    await page.evaluate(() => {
      document.getElementById('login-username').value = 'lin';
      document.getElementById('login-password').value = '950320';
    });
    await page.evaluate(() => { doLogin(); });
    await sleep(5000);
    const loggedIn = await page.evaluate(() => !!localStorage.getItem('xhs_auth_token'));
    console.log(loggedIn ? '✅ 已登录\n' : '❌ 登录失败\n');
    if (!loggedIn) { await browser.close(); return; }

    // ========== TEST 1: 内容生成 (验证完整联网模式) ==========
    console.log('━━━ [1] 内容生成 (联网搜索+智能生成) ━━━');
    await page.evaluate(() => switchPage('generator'));
    await sleep(800);
    await page.evaluate(() => {
      document.getElementById('gen-category').value = '治愈';
      document.getElementById('gen-count').value = '1';
      const chk = document.getElementById('gen-with-image');
      if (chk && chk.checked) chk.click();
    });

    const t1 = Date.now();
    const r1 = await page.evaluate(() => {
      return new Promise(resolve => {
        generatePosts()
          .then(() => {
            const posts = window._lastGeneratedPosts || [];
            // 检查分析报告是否存在 (完整模式才会有)
            const hasAnalysis = typeof _lastAnalysis !== 'undefined' && _lastAnalysis !== null;
            const searchUsed = hasAnalysis && (_lastAnalysis.searchUsed || _lastAnalysis.baiduUsed);
            const baiduCount = hasAnalysis ? (_lastAnalysis.baiduCount || 0) : 0;
            const sourcesCount = hasAnalysis ? (_lastAnalysis.sources?.length || 0) : 0;
            if (posts.length > 0) {
              const p = posts[0];
              resolve({
                ok: true, count: posts.length,
                title: p.title, content: (p.content||'').substring(0,120), tags: p.tags,
                mode: hasAnalysis ? (searchUsed ? '联网搜索' : '知识库分析') : '本地模板',
                baiduCount, sourcesCount
              });
            } else {
              resolve({ ok: false, msg: `posts.length=0, hasAnalysis=${hasAnalysis}`, mode: 'unknown' });
            }
          })
          .catch(e => resolve({ ok: false, msg: e.message || String(e), mode: 'error' }));
      });
    });
    const sec1 = ((Date.now()-t1)/1000).toFixed(1);
    if (r1.ok) {
      console.log(`  ✅ 成功 (${sec1}s) — ${r1.count} 条`);
      console.log(`  模式: ${r1.mode} (百度${r1.baiduCount}条 + ${r1.sourcesCount}个来源)`);
      console.log('  标题: ' + r1.title);
      console.log('  内容: ' + r1.content + '...');
      console.log('  标签: ' + r1.tags);
    } else {
      console.log('  ❌ 失败 (' + sec1 + 's): ' + r1.msg + ' mode=' + r1.mode);
    }
    await shot(page, '1_content');

    // ========== TEST 2: AI 生图 x3 ==========
    console.log('\n━━━ [2] AI 生图 × 3 ━━━');
    const prompts = [
      '粉色治愈系小红书封面，温暖午后，一杯咖啡和一本书，柔和光线，简约文艺风格',
      '夏日海边落日，金色沙滩，脚印延伸到远方，唯美治愈系摄影风格',
      '秋天枫叶小路，暖色调，一个人背影走在落叶中，文艺清新风格'
    ];
    const imgResults = [];
    const t2Total = Date.now();

    for (let i = 0; i < prompts.length; i++) {
      console.log(`  [${i+1}/3] 生成中...`);
      const t2 = Date.now();
      const r2 = await page.evaluate((prompt) => {
        return new Promise(resolve => {
          generateSingleImage(prompt)
            .then(img => {
              if (img) resolve({ ok: true, size: (img.length/1024).toFixed(0)+'KB' });
              else resolve({ ok: false, msg: (typeof _lastImageGenErrorMsg!=='undefined' ? _lastImageGenErrorMsg : '无返回') });
            })
            .catch(e => resolve({ ok: false, msg: e.message }));
        });
      }, prompts[i]);
      const sec2 = ((Date.now()-t2)/1000).toFixed(1);
      imgResults.push({ ...r2, time: sec2 });
      console.log(r2.ok ? `  [${i+1}/3] ✅ ${sec2}s — ${r2.size}` : `  [${i+1}/3] ❌ ${sec2}s — ${r2.msg}`);
    }
    const sec2Total = ((Date.now()-t2Total)/1000).toFixed(1);
    const imgOk = imgResults.filter(r => r.ok).length;
    console.log(`  📊 总计: ${imgOk}/3 成功, 总耗时 ${sec2Total}s`);
    await shot(page, '2_images');

    // ========== TEST 3: AI 智能卡片 ==========
    console.log('\n━━━ [3] AI 智能卡片生成 ━━━');
    await page.evaluate(() => switchPage('ai-card'));
    await sleep(800);
    await page.evaluate(() => {
      document.getElementById('aicard-title').value = '夏日治愈时光';
      document.getElementById('aicard-content').value = '在快节奏的世界里，偶尔也需要放慢脚步。\n找一个安静的午后，泡一杯咖啡，翻开喜欢的书，让阳光洒在身上。\n这就是属于我的小确幸。生活不止眼前的苟且，还有诗和远方。';
      document.getElementById('aicard-category').value = '情感';
    });

    const t3 = Date.now();
    const r3 = await page.evaluate(() => {
      return new Promise(resolve => {
        doAICardGenerate()
          .then(() => {
            setTimeout(() => {
              const res = document.getElementById('aicard-result');
              if (!res) return resolve({ ok: false, cards: 0, match: '' });
              const cardImgs = res.querySelectorAll('img[src^="data:image"]');
              const text = res.textContent.substring(0, 300);
              const tmplMatch = text.match(/AI 推荐[：:]\s*(.+?)[\n\r]/);
              resolve({ ok: cardImgs.length > 0, cards: cardImgs.length, match: tmplMatch ? tmplMatch[1].trim() : '', text: text.substring(0, 150) });
            }, 2000);
          })
          .catch(e => resolve({ ok: false, cards: 0, match: '', text: e.message }));
      });
    });
    const sec3 = ((Date.now()-t3)/1000).toFixed(1);
    if (r3.ok) {
      console.log('  ✅ 成功 (' + sec3 + 's) — ' + r3.cards + ' 张卡片, 模板: ' + r3.match);
    } else if (r3.text && r3.text.length > 30) {
      console.log('  ⚠️ AI匹配成功, 等待渲染 (' + sec3 + 's)');
      console.log('  结果: ' + r3.text);
    } else {
      console.log('  ❌ 失败 (' + sec3 + 's): ' + (r3.text || 'unknown'));
    }
    await shot(page, '3_card');

    // ========== 汇总 ==========
    console.log('\n═══════════════════════════════════');
    console.log('  [1] 内容生成: ' + (r1.ok ? `✅ ${sec1}s (${r1.mode})` : '❌'));
    console.log('  [2] AI 生图:  ' + `${imgOk}/3 成功, ${sec2Total}s`);
    console.log('  [3] AI 卡片:  ' + (r3.ok ? `✅ ${sec3}s — ${r3.cards}张` : r3.text?.length > 30 ? '⚠️ 匹配OK' : '❌'));
    console.log('═══════════════════════════════════');

  } catch(e) {
    console.error('FATAL:', e.message);
    await shot(page, 'error');
  } finally {
    await sleep(10000);
    await browser.close();
  }
})();
