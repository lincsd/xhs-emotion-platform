const puppeteer = require('puppeteer-core');
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const URL = 'https://lincsd.github.io/xhs-emotion-platform/';
const https = require('https');
const http = require('http');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
async function shot(page, name) {
  try { await page.screenshot({ path: `_ss_${name}.png` }); } catch(e) {}
}

// Test Tunnel directly first
function testTunnel() {
  return new Promise(resolve => {
    https.get('https://gale-freelance-collections-corners.trycloudflare.com/api/version', res => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => { console.log('  Tunnel: ' + d.trim()); resolve(true); });
    }).on('error', (e) => { console.log('  Tunnel: offline -', e.message); resolve(false); });
  });
}

(async () => {
  console.log('=== Cloudflare Tunnel 速度测试 ===\n');

  console.log('🔍 检查隧道状态...');
  const tunnelOk = await testTunnel();
  if (!tunnelOk) {
    console.log('❌ 隧道不可用，请先启动 cloudflared');
    return;
  }

  console.log('⏳ 等待40s让 GitHub Pages 更新...');
  await sleep(40000);

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
    console.log('🌐 加载页面...');
    await page.goto(URL, { waitUntil: 'networkidle2', timeout: 90000 });
    await sleep(5000);

    // 检查用了哪个后端
    const backendInfo = await page.evaluate(() => {
      return {
        activeBackend: typeof _activeBackend !== 'undefined' ? _activeBackend : 'unknown',
        apiBase: typeof API_BASE !== 'undefined' ? API_BASE : 'unknown',
        lightMode: typeof IS_LIGHT_AI_MODE !== 'undefined' ? IS_LIGHT_AI_MODE : 'unknown'
      };
    });
    console.log('📡 Active Backend: ' + backendInfo.activeBackend);
    console.log('📡 API_BASE: ' + backendInfo.apiBase);
    console.log('IS_LIGHT_AI_MODE: ' + backendInfo.lightMode);
    const isTunnel = backendInfo.activeBackend.includes('trycloudflare');
    console.log(isTunnel ? '🚀 使用 Cloudflare Tunnel (本地+梯子)' : '☁️ 使用 Render 云端');

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
    console.log('  [1] 笔记生成测试');
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
    console.log('  📋 速度测试结果 (' + (isTunnel ? 'Cloudflare Tunnel 🚀' : 'Render ☁️') + ')');
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

  } catch(e) {
    console.error('FATAL:', e.message);
    await shot(page, 'error');
  } finally {
    await sleep(8000);
    await browser.close();
    console.log('\n🏁 测试结束');
  }
})();
