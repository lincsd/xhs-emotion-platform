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
    }).on('error', () => { console.log('  后端唤醒失败,重试...'); resolve(); });
  });
}

(async () => {
  console.log('=== 前端功能测试 (笔记生成 + 生图速度) ===\n');

  // 唤醒后端
  console.log('🔄 唤醒后端...');
  await warmup();
  await sleep(3000);
  await warmup();

  // 等 GitHub Pages 更新
  console.log('⏳ 等待40s让 GitHub Pages 更新...');
  await sleep(40000);

  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: false,
    defaultViewport: { width: 1400, height: 900 },
    args: ['--no-sandbox'], protocolTimeout: 600000
  });
  const page = await browser.newPage();

  // 收集控制台日志
  page.on('console', msg => {
    const t = msg.text();
    if (t.includes('Error') || t.includes('失败') || t.includes('成功') ||
        t.includes('✅') || t.includes('❌') || t.includes('[ImageGen]') ||
        t.includes('CORS') || t.includes('502') || t.includes('重试') ||
        t.includes('搜索') || t.includes('创作') || t.includes('[Gemini]') ||
        t.includes('生成') || t.includes('fallback') || t.includes('AI') ||
        t.includes('百度') || t.includes('联网') || t.includes('轻量') ||
        t.includes('grounding') || t.includes('分析') || t.includes('检索') ||
        t.includes('配额') || t.includes('网络错误'))
      console.log('  [LOG] ' + t.substring(0, 300));
  });
  page.on('requestfailed', req => {
    console.log('  [FAIL] ' + req.url().substring(0, 100) + ' — ' + (req.failure()?.errorText || ''));
  });

  try {
    // 加载 & 登录
    console.log('🌐 加载页面...');
    await page.goto(URL, { waitUntil: 'networkidle2', timeout: 90000 });
    await sleep(5000);

    // 检查 IS_LIGHT_AI_MODE
    const lightMode = await page.evaluate(() => typeof IS_LIGHT_AI_MODE !== 'undefined' ? IS_LIGHT_AI_MODE : 'undefined');
    console.log('IS_LIGHT_AI_MODE = ' + lightMode + (lightMode === false ? ' ✅ (完整联网模式)' : ' ⚠️'));

    // 登录
    await page.evaluate(() => {
      document.getElementById('login-username').value = 'lin';
      document.getElementById('login-password').value = '950320';
    });
    await page.evaluate(() => { doLogin(); });
    await sleep(5000);
    const loggedIn = await page.evaluate(() => !!localStorage.getItem('xhs_auth_token'));
    console.log(loggedIn ? '✅ 已登录\n' : '❌ 登录失败\n');
    if (!loggedIn) { await browser.close(); return; }

    // ========== TEST 1: 笔记生成 ==========
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('  [1] 笔记生成测试 (联网搜索+AI生成)');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    await page.evaluate(() => switchPage('generator'));
    await sleep(800);
    await page.evaluate(() => {
      document.getElementById('gen-category').value = '治愈';
      document.getElementById('gen-count').value = '1';
      const chk = document.getElementById('gen-with-image');
      if (chk && chk.checked) chk.click(); // 不带图
    });

    const t1 = Date.now();
    const r1 = await page.evaluate(() => {
      return new Promise(resolve => {
        generatePosts()
          .then(() => {
            const posts = window._lastGeneratedPosts || [];
            const hasAnalysis = typeof _lastAnalysis !== 'undefined' && _lastAnalysis !== null;
            const searchUsed = hasAnalysis && (_lastAnalysis.searchUsed || _lastAnalysis.baiduUsed);
            const baiduCount = hasAnalysis ? (_lastAnalysis.baiduCount || 0) : 0;
            const sourcesCount = hasAnalysis ? (_lastAnalysis.sources?.length || 0) : 0;
            if (posts.length > 0) {
              const p = posts[0];
              resolve({
                ok: true, count: posts.length,
                title: p.title, content: (p.content||'').substring(0,150), tags: p.tags,
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
      console.log(`  ✅ 笔记生成成功 — 耗时 ${sec1}s`);
      console.log(`  生成模式: ${r1.mode} (百度${r1.baiduCount}条 + ${r1.sourcesCount}个来源)`);
      console.log(`  笔记数量: ${r1.count} 条`);
      console.log(`  标题: ${r1.title}`);
      console.log(`  内容: ${r1.content}...`);
      console.log(`  标签: ${r1.tags}`);
    } else {
      console.log(`  ❌ 笔记生成失败 (${sec1}s): ${r1.msg} mode=${r1.mode}`);
    }
    await shot(page, 'test_content');

    // ========== TEST 2: AI生图 x3 (测速) ==========
    console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('  [2] AI生图速度测试 × 3 张');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    const prompts = [
      '粉色治愈系小红书封面，温暖午后，一杯咖啡和一本书，柔和光线，简约文艺风格',
      '夏日海边落日，金色沙滩，脚印延伸到远方，唯美治愈系摄影风格',
      '秋天枫叶小路，暖色调，一个人背影走在落叶中，文艺清新风格'
    ];
    const imgResults = [];
    const t2Total = Date.now();

    for (let i = 0; i < prompts.length; i++) {
      console.log(`\n  [${i+1}/3] 开始生成: "${prompts[i].substring(0,25)}..."`);
      const t2 = Date.now();
      const r2 = await page.evaluate((prompt) => {
        return new Promise(resolve => {
          generateSingleImage(prompt)
            .then(img => {
              if (img) {
                const sizeKB = (img.length / 1024).toFixed(0);
                resolve({ ok: true, size: sizeKB + 'KB' });
              } else {
                resolve({ ok: false, msg: (typeof _lastImageGenErrorMsg !== 'undefined' ? _lastImageGenErrorMsg : '无返回') });
              }
            })
            .catch(e => resolve({ ok: false, msg: e.message }));
        });
      }, prompts[i]);
      const sec2 = ((Date.now()-t2)/1000).toFixed(1);
      imgResults.push({ ...r2, time: sec2, prompt: prompts[i].substring(0,20) });

      if (r2.ok) {
        console.log(`  [${i+1}/3] ✅ 成功 — ${sec2}s, 大小: ${r2.size}`);
      } else {
        console.log(`  [${i+1}/3] ❌ 失败 — ${sec2}s, 原因: ${r2.msg}`);
      }
    }
    const sec2Total = ((Date.now()-t2Total)/1000).toFixed(1);
    const imgOk = imgResults.filter(r => r.ok).length;
    const avgTime = imgResults.filter(r=>r.ok).length > 0
      ? (imgResults.filter(r=>r.ok).reduce((s,r) => s + parseFloat(r.time), 0) / imgResults.filter(r=>r.ok).length).toFixed(1)
      : 'N/A';
    
    console.log('\n  📊 生图速度汇总:');
    imgResults.forEach((r, i) => {
      console.log(`     图${i+1}: ${r.ok ? '✅' : '❌'} ${r.time}s ${r.ok ? r.size : r.msg}`);
    });
    console.log(`     成功率: ${imgOk}/3`);
    console.log(`     总耗时: ${sec2Total}s`);
    console.log(`     平均每张: ${avgTime}s`);
    await shot(page, 'test_images');

    // ========== 汇总 ==========
    console.log('\n══════════════════════════════════════');
    console.log('  📋 测试结果汇总');
    console.log('══════════════════════════════════════');
    console.log(`  [1] 笔记生成: ${r1.ok ? `✅ ${sec1}s (${r1.mode})` : '❌ 失败'}`);
    console.log(`  [2] AI生图:   ${imgOk}/3 成功`);
    console.log(`      总耗时:   ${sec2Total}s`);
    console.log(`      平均速度: ${avgTime}s/张`);
    imgResults.forEach((r, i) => {
      console.log(`      图${i+1}: ${r.ok ? '✅' : '❌'} ${r.time}s`);
    });
    console.log('══════════════════════════════════════');

  } catch(e) {
    console.error('FATAL:', e.message);
    await shot(page, 'error');
  } finally {
    await sleep(8000);
    await browser.close();
    console.log('\n🏁 测试结束');
  }
})();
