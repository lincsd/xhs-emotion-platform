const puppeteer = require('puppeteer-core');
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
// 直接访问 Cloudflare Tunnel 上的前端（本地 server.py 也 serve 前端静态文件）
const TUNNEL_URL = 'https://gale-freelance-collections-corners.trycloudflare.com';

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
async function shot(page, name) {
  try { await page.screenshot({ path: `_ss_${name}.png` }); } catch(e) {}
}

(async () => {
  console.log('=== Cloudflare Tunnel 速度测试 (直连) ===\n');

  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: false,
    defaultViewport: { width: 1400, height: 900 },
    args: ['--no-sandbox'], protocolTimeout: 600000
  });
  const page = await browser.newPage();

  page.on('console', msg => {
    const t = msg.text();
    if (t.includes('后端') || t.includes('Tunnel') || t.includes('Render') || 
        t.includes('✅') || t.includes('❌') || t.includes('🚀') || t.includes('☁️') ||
        t.includes('[ImageGen]') || t.includes('[Gemini]') ||
        t.includes('搜索') || t.includes('生成') || t.includes('分析') ||
        t.includes('Error') || t.includes('失败') || t.includes('成功') ||
        t.includes('CORS') || t.includes('502') || t.includes('重试') ||
        t.includes('配额') || t.includes('联网') || t.includes('百度'))
      console.log('  [LOG] ' + t.substring(0, 300));
  });

  try {
    // 直接加载 Tunnel 上的前端（不用等 GitHub Pages）
    console.log('🌐 加载 Tunnel 前端...');
    await page.goto(TUNNEL_URL, { waitUntil: 'networkidle2', timeout: 60000 });
    await sleep(3000);

    // 检查当前状态
    const info = await page.evaluate(() => ({
      apiBase: typeof API_BASE !== 'undefined' ? API_BASE : 'unknown',
      isGH: typeof IS_GITHUB_PAGES !== 'undefined' ? IS_GITHUB_PAGES : 'unknown'
    }));
    console.log('📡 API_BASE: ' + info.apiBase + ' (isGH=' + info.isGH + ')');
    console.log('🚀 通过 Tunnel 直接访问本地服务器\n');

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
    console.log('  [1] 笔记生成测试 (Tunnel 直连)');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
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
            const hasAnalysis = typeof _lastAnalysis !== 'undefined' && _lastAnalysis !== null;
            const searchUsed = hasAnalysis && (_lastAnalysis.searchUsed || _lastAnalysis.baiduUsed);
            const baiduCount = hasAnalysis ? (_lastAnalysis.baiduCount || 0) : 0;
            const sourcesCount = hasAnalysis ? (_lastAnalysis.sources?.length || 0) : 0;
            if (posts.length > 0) {
              const p = posts[0];
              resolve({
                ok: true, count: posts.length,
                title: p.title, content: (p.content||'').substring(0,100),
                mode: hasAnalysis ? (searchUsed ? '联网搜索' : '知识库分析') : '本地模板',
                baiduCount, sourcesCount
              });
            } else {
              resolve({ ok: false, msg: 'posts.length=0' });
            }
          })
          .catch(e => resolve({ ok: false, msg: e.message || String(e) }));
      });
    });
    const sec1 = ((Date.now()-t1)/1000).toFixed(1);
    if (r1.ok) {
      console.log(`  ✅ 笔记生成成功 — ${sec1}s`);
      console.log(`  模式: ${r1.mode} (百度${r1.baiduCount}条 + ${r1.sourcesCount}个来源)`);
      console.log(`  标题: ${r1.title}`);
    } else {
      console.log(`  ❌ 笔记失败 (${sec1}s): ${r1.msg}`);
    }
    await shot(page, 'tunnel_content');

    // ========== TEST 2: AI生图 x3 ==========
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
      console.log(`\n  [${i+1}/3] 生成中: "${prompts[i].substring(0,20)}..."`);
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
    const avgTime = imgOk > 0
      ? (imgResults.filter(r=>r.ok).reduce((s,r) => s + parseFloat(r.time), 0) / imgOk).toFixed(1)
      : 'N/A';

    // ========== 汇总 ==========
    console.log('\n══════════════════════════════════════');
    console.log('  📋 Cloudflare Tunnel 速度测试结果 🚀');
    console.log('══════════════════════════════════════');
    console.log(`  [1] 笔记生成: ${r1.ok ? `✅ ${sec1}s (${r1.mode})` : '❌'}`);
    console.log(`  [2] AI生图:`);
    imgResults.forEach((r, i) => {
      console.log(`      图${i+1}: ${r.ok ? '✅' : '❌'} ${r.time}s ${r.ok ? r.size : r.msg}`);
    });
    console.log(`      成功率: ${imgOk}/3`);
    console.log(`      总耗时: ${sec2Total}s`);
    console.log(`      平均: ${avgTime}s/张`);
    console.log('══════════════════════════════════════');

    // 之前 Render 的数据对比
    console.log('\n  📊 与 Render 对比 (之前测试数据):');
    console.log('  ┌────────────┬──────────┬──────────┐');
    console.log('  │            │ Render   │ Tunnel   │');
    console.log('  ├────────────┼──────────┼──────────┤');
    console.log(`  │ 笔记生成   │ 48.3s    │ ${sec1.padStart(5)}s   │`);
    console.log(`  │ 生图平均   │ 21.9s    │ ${(avgTime+'').padStart(5)}s   │`);
    console.log(`  │ 生图总计   │ 65.8s    │ ${sec2Total.padStart(5)}s   │`);
    console.log('  └────────────┴──────────┴──────────┘');

  } catch(e) {
    console.error('FATAL:', e.message);
    await shot(page, 'error');
  } finally {
    await sleep(8000);
    await browser.close();
    console.log('\n🏁 测试结束');
  }
})();
