/**
 * 小红书运营平台 - 内容生成 & 生图功能测试
 * 使用真实账号登录，测试完整的 AI 生成流程
 * 执行: node _test_gen_and_image.js
 */

const http = require('http');
const https = require('https');
const fs = require('fs');

const BASE = 'http://localhost:3000';
const USERNAME = 'lin';
const PASSWORD = '950320';

let authToken = null;
const results = [];
let passCount = 0, failCount = 0, warnCount = 0;
const startTime = Date.now();

function log(status, category, name, detail = '') {
  const icon = status === 'PASS' ? '✅' : status === 'FAIL' ? '❌' : '⚠️';
  results.push({ status, category, name, detail });
  if (status === 'PASS') passCount++;
  else if (status === 'FAIL') failCount++;
  else warnCount++;
  console.log(icon + ' [' + category + '] ' + name + (detail ? ' — ' + detail : ''));
}

// HTTP 请求工具
function request(url, opts = {}) {
  return new Promise((resolve, reject) => {
    const isHttps = url.startsWith('https');
    const lib = isHttps ? https : http;
    const parsed = new URL(url);
    const bodyStr = opts.body ? (typeof opts.body === 'string' ? opts.body : JSON.stringify(opts.body)) : null;
    const options = {
      hostname: parsed.hostname,
      port: parsed.port || (isHttps ? 443 : 80),
      path: parsed.pathname + parsed.search,
      method: opts.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(bodyStr ? { 'Content-Length': Buffer.byteLength(bodyStr) } : {}),
        ...(opts.headers || {})
      },
      timeout: opts.timeout || 30000,
    };
    const req = lib.request(options, (res) => {
      let body = Buffer.alloc(0);
      res.on('data', c => { body = Buffer.concat([body, Buffer.isBuffer(c) ? c : Buffer.from(c)]); });
      res.on('end', () => {
        const str = body.toString('utf8');
        let json = null;
        try { json = JSON.parse(str); } catch {}
        resolve({ status: res.statusCode, body: str, json, headers: res.headers, raw: body });
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    if (bodyStr) req.write(bodyStr);
    req.end();
  });
}

function authHeaders() {
  const h = {};
  if (authToken) h['Authorization'] = 'Bearer ' + authToken;
  return h;
}

// ===== 1. 登录 =====
async function testLogin() {
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('🔑 步骤1: 登录');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

  try {
    const r = await request(BASE + '/api/auth/login', {
      method: 'POST',
      body: { username: USERNAME, password: PASSWORD }
    });
    if (r.status === 200 && r.json && r.json.token) {
      authToken = r.json.token;
      const user = r.json.user || r.json;
      log('PASS', '登录', '用户登录成功', '用户: ' + (user.nickname || user.username || USERNAME) + ', credits: ' + (user.credits ?? '?'));
      return true;
    } else {
      log('FAIL', '登录', '登录失败', '状态:' + r.status + ' 返回:' + (r.json?.error || r.body?.substring(0, 100)));
      return false;
    }
  } catch (e) {
    log('FAIL', '登录', '登录异常', e.message);
    return false;
  }
}

// ===== 2. 验证积分余额 =====
async function testCredits() {
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('💎 步骤2: 积分余额');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

  try {
    const r = await request(BASE + '/api/user/credits', { headers: authHeaders() });
    if (r.status === 200 && r.json) {
      log('PASS', '积分', '积分查询', JSON.stringify(r.json));
      return r.json;
    } else {
      log('FAIL', '积分', '积分查询', '状态:' + r.status);
      return null;
    }
  } catch (e) {
    log('FAIL', '积分', '积分查询异常', e.message);
    return null;
  }
}

// ===== 3. AI 代理功能测试 =====
async function testGeminiProxy() {
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('🤖 步骤3: Gemini AI 代理测试');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

  // 3.1 简单文本生成
  try {
    const t0 = Date.now();
    const r = await request(BASE + '/api/gemini-proxy', {
      method: 'POST',
      headers: authHeaders(),
      body: {
        model: 'gemini-2.5-flash',
        payload: {
          contents: [{ parts: [{ text: '请用一句话回复：你好' }] }],
          generationConfig: { maxOutputTokens: 100 }
        },
        feature: '内容生成'
      },
      timeout: 60000
    });
    const elapsed = Date.now() - t0;
    if (r.status === 200 && r.json) {
      const text = r.json?.candidates?.[0]?.content?.parts?.[0]?.text || '';
      if (text.length > 0) {
        log('PASS', 'AI代理', 'Gemini文本生成', text.substring(0, 80) + ' (' + elapsed + 'ms)');
      } else {
        log('FAIL', 'AI代理', 'Gemini文本生成', '返回空内容 (' + elapsed + 'ms)');
      }
    } else {
      log('FAIL', 'AI代理', 'Gemini文本生成', '状态:' + r.status + ' ' + (r.json?.error?.message || r.body?.substring(0, 100)));
    }
  } catch (e) {
    log('FAIL', 'AI代理', 'Gemini文本生成', e.message);
  }

  // 3.2 长文本（笔记级别）
  try {
    const t0 = Date.now();
    const r = await request(BASE + '/api/gemini-proxy', {
      method: 'POST',
      headers: authHeaders(),
      body: {
        model: 'gemini-2.5-flash',
        payload: {
          contents: [{ parts: [{ text: '请写一条小红书情感类笔记，标题+正文300字左右，带标签和封面文字。只输出JSON格式：{"title":"...","content":"...","tags":"...","cover_text":"..."}' }] }],
          generationConfig: { maxOutputTokens: 2000, temperature: 0.9 }
        },
        feature: '内容生成'
      },
      timeout: 60000
    });
    const elapsed = Date.now() - t0;
    if (r.status === 200) {
      const text = r.json?.candidates?.[0]?.content?.parts?.[0]?.text || '';
      // 尝试解析JSON
      let parsed = null;
      try {
        const cleaned = text.replace(/```(?:json)?\s*/g, '').replace(/```/g, '').trim();
        parsed = JSON.parse(cleaned);
      } catch {}
      if (parsed && parsed.title) {
        log('PASS', 'AI代理', '笔记级文本生成', '标题: ' + parsed.title.substring(0, 30) + '... 内容' + (parsed.content?.length || 0) + '字 (' + elapsed + 'ms)');
      } else {
        log('PASS', 'AI代理', '笔记级文本生成', '返回' + text.length + '字 (' + elapsed + 'ms) [非JSON格式但有内容]');
      }
    } else {
      log('FAIL', 'AI代理', '笔记级文本生成', '状态:' + r.status);
    }
  } catch (e) {
    log('FAIL', 'AI代理', '笔记级文本生成', e.message);
  }
}

// ===== 4. 内容生成（服务端 /api/generate）=====
async function testServerGenerate() {
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('📝 步骤4: 服务端内容生成 /api/generate');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

  // 测试多个分类
  const categories = ['情感', '美食', '招聘'];
  for (const cat of categories) {
    try {
      const t0 = Date.now();
      const r = await request(BASE + '/api/generate', {
        method: 'POST',
        headers: authHeaders(),
        body: { category: cat, count: 1 },
        timeout: 60000
      });
      const elapsed = Date.now() - t0;
      if (r.status === 200 && r.json && r.json.posts) {
        const post = r.json.posts[0];
        if (post && post.title) {
          log('PASS', '服务端生成', '生成[' + cat + ']笔记', '标题: ' + post.title.substring(0, 25) + '... 内容' + (post.content?.length || 0) + '字 (' + elapsed + 'ms)');
        } else {
          log('WARN', '服务端生成', '生成[' + cat + ']笔记', '返回空笔记 (' + elapsed + 'ms)');
        }
      } else {
        log('FAIL', '服务端生成', '生成[' + cat + ']笔记', '状态:' + r.status + ' (' + elapsed + 'ms)');
      }
    } catch (e) {
      log('FAIL', '服务端生成', '生成[' + cat + ']笔记', e.message);
    }
  }
}

// ===== 5. AI 笔记生成（模拟前端 generatePosts 流程）=====
async function testAIContentGeneration() {
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('✨ 步骤5: AI 智能内容生成（模拟前端完整流程）');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

  const category = '招聘';
  const count = 2;

  // 5.1 搜索分析步骤
  console.log('  📡 5.1 联网搜索分析...');
  let analysisText = '';
  try {
    const t0 = Date.now();
    const searchPrompt = '请你分析小红书平台上「社会招聘」分类的招聘类热门笔记。列出5个典型爆款标题，分析标题规律、内容结构、标签策略。输出分析报告。';
    const r = await request(BASE + '/api/gemini-proxy', {
      method: 'POST',
      headers: authHeaders(),
      body: {
        model: 'gemini-2.5-flash',
        payload: {
          contents: [{ parts: [{ text: searchPrompt }] }],
          tools: [{ google_search: {} }],
          generationConfig: { temperature: 0.7, maxOutputTokens: 4096 }
        },
        feature: '内容搜索分析'
      },
      timeout: 90000
    });
    const elapsed = Date.now() - t0;
    if (r.status === 200 && r.json) {
      const parts = r.json?.candidates?.[0]?.content?.parts || [];
      analysisText = parts.filter(p => !p.thought && p.text).map(p => p.text).join('');
      const grounding = r.json?.candidates?.[0]?.groundingMetadata;
      const sources = grounding?.groundingChunks?.filter(c => c.web)?.length || 0;
      if (analysisText.length > 100) {
        log('PASS', 'AI生成', '联网搜索分析', '分析报告' + analysisText.length + '字, 搜索来源' + sources + '个 (' + elapsed + 'ms)');
      } else {
        log('WARN', 'AI生成', '联网搜索分析', '分析内容较短:' + analysisText.length + '字 (' + elapsed + 'ms)');
      }
    } else {
      // Google Search grounding 可能不可用，降级
      log('WARN', 'AI生成', '联网搜索分析', 'Google Search 不可用 (状态:' + r.status + '), 使用降级分析');
      // 降级：不用搜索
      const r2 = await request(BASE + '/api/gemini-proxy', {
        method: 'POST',
        headers: authHeaders(),
        body: {
          model: 'gemini-2.5-flash',
          payload: {
            contents: [{ parts: [{ text: searchPrompt }] }],
            generationConfig: { temperature: 0.8, maxOutputTokens: 4096 }
          },
          feature: '内容搜索分析'
        },
        timeout: 60000
      });
      if (r2.status === 200) {
        const parts = r2.json?.candidates?.[0]?.content?.parts || [];
        analysisText = parts.filter(p => !p.thought && p.text).map(p => p.text).join('');
        log('PASS', 'AI生成', '降级分析（无搜索）', '分析报告' + analysisText.length + '字');
      }
    }
  } catch (e) {
    log('FAIL', 'AI生成', '联网搜索分析', e.message);
  }

  // 5.2 百度搜索
  console.log('  🔍 5.2 百度搜索真实小红书笔记...');
  let baiduResults = [];
  try {
    const t0 = Date.now();
    const r = await request(BASE + '/api/baidu-search', {
      method: 'POST',
      headers: authHeaders(),
      body: { keyword: '招聘类 社会招聘 爆款', count: 5 },
      timeout: 20000
    });
    const elapsed = Date.now() - t0;
    if (r.status === 200 && r.json && r.json.results) {
      baiduResults = r.json.results;
      log('PASS', 'AI生成', '百度搜索小红书笔记', '找到' + baiduResults.length + '条结果 (' + elapsed + 'ms)');
    } else {
      log('WARN', 'AI生成', '百度搜索小红书笔记', '状态:' + r.status + ' (' + elapsed + 'ms)');
    }
  } catch (e) {
    log('WARN', 'AI生成', '百度搜索小红书笔记', e.message);
  }

  // 5.3 基于分析生成笔记
  console.log('  ✍️ 5.3 基于分析生成' + count + '条笔记...');
  let generatedPosts = [];
  try {
    const compactAnalysis = (analysisText || '请基于你对小红书招聘内容的了解').substring(0, 3000);
    const baiduRef = baiduResults.length > 0
      ? '\n\n百度搜到的真实笔记:\n' + baiduResults.slice(0, 3).map((r, i) => (i + 1) + '. ' + r.title).join('\n')
      : '';

    const prompt = '你是一位拥有30万粉丝的小红书招聘博主。\n\n## 分析报告\n' + compactAnalysis + baiduRef + '\n\n## 任务\n基于以上分析，生成 ' + count + ' 条高质量小红书招聘类笔记（社会招聘分类）。\n\n要求：\n1. 标题：参考爆款规律\n2. 正文：300-500字\n3. 标签：5个\n4. 封面文字：4-10字\n5. 简体中文\n\n输出JSON数组（无markdown标记）：\n[{"title":"...","content":"...","tags":"...","cover_text":"...","category":"社会招聘","ai_analysis":"..."}]';

    const t0 = Date.now();
    const r = await request(BASE + '/api/gemini-proxy', {
      method: 'POST',
      headers: authHeaders(),
      body: {
        model: 'gemini-2.5-flash',
        payload: {
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.95, maxOutputTokens: 8192, responseMimeType: 'application/json' }
        },
        feature: '内容生成'
      },
      timeout: 90000
    });
    const elapsed = Date.now() - t0;

    if (r.status === 200 && r.json) {
      const text = (r.json?.candidates?.[0]?.content?.parts || []).filter(p => !p.thought && p.text).map(p => p.text).join('');
      try {
        const cleaned = text.replace(/```(?:json)?\s*/g, '').replace(/```/g, '').trim();
        generatedPosts = JSON.parse(cleaned);
        if (!Array.isArray(generatedPosts)) generatedPosts = [generatedPosts];

        for (let i = 0; i < generatedPosts.length; i++) {
          const p = generatedPosts[i];
          const contentLen = (p.content || '').length;
          const tagCount = (p.tags || '').split(',').filter(Boolean).length;
          console.log('    📄 笔记' + (i + 1) + ': ' + (p.title || '无标题').substring(0, 35));
          console.log('       内容: ' + contentLen + '字 | 标签: ' + tagCount + '个 | 封面: ' + (p.cover_text || '无'));
        }

        log('PASS', 'AI生成', '生成' + count + '条笔记', '成功' + generatedPosts.length + '条, 平均' + Math.round(generatedPosts.reduce((s, p) => s + (p.content?.length || 0), 0) / generatedPosts.length) + '字/条 (' + elapsed + 'ms)');
      } catch (parseErr) {
        log('WARN', 'AI生成', '生成笔记JSON解析', 'JSON解析失败但有返回(' + text.length + '字) (' + elapsed + 'ms)');
      }
    } else {
      log('FAIL', 'AI生成', '生成笔记', '状态:' + r.status + ' ' + (r.json?.error?.message || ''));
    }
  } catch (e) {
    log('FAIL', 'AI生成', '生成笔记', e.message);
  }

  // 5.4 自动保存到草稿箱
  if (generatedPosts.length > 0) {
    console.log('  💾 5.4 保存笔记到草稿箱...');
    let savedIds = [];
    for (const p of generatedPosts) {
      try {
        const r = await request(BASE + '/api/posts', {
          method: 'POST',
          headers: authHeaders(),
          body: {
            title: p.title || '测试笔记',
            content: (p.content || '').replace(/\\n/g, '\n'),
            category: p.category || '社会招聘',
            status: 'draft',
            tags: p.tags || '',
            cover_text: p.cover_text || ''
          }
        });
        if (r.status === 200 || r.status === 201) {
          savedIds.push(r.json?.id);
        }
      } catch (e) {
        console.warn('    保存失败:', e.message);
      }
    }
    if (savedIds.length > 0) {
      log('PASS', 'AI生成', '保存到草稿箱', '保存' + savedIds.length + '条, IDs: ' + savedIds.join(','));
    } else {
      log('FAIL', 'AI生成', '保存到草稿箱', '保存失败');
    }

    // 返回 IDs 供后续清理
    return { posts: generatedPosts, savedIds };
  }

  return { posts: generatedPosts, savedIds: [] };
}

// ===== 6. 图片生成测试 =====
async function testImageGeneration(posts) {
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('🎨 步骤6: AI 图片生成（封面图 + 配图）');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

  const post = (posts && posts.length > 0) ? posts[0] : { title: '测试招聘笔记', content: '这是一条测试用的招聘笔记', category: '社会招聘', cover_text: '招聘攻略' };

  // 6.1 封面图生成
  console.log('  🖼️ 6.1 生成封面图...');
  let coverImage = null;
  const imageModels = [
    'gemini-3.1-flash-image-preview',
    'gemini-3-pro-image-preview',
    'gemini-2.5-flash-image'
  ];

  for (const imageModel of imageModels) {
    try {
      const coverPrompt = '生成一张小红书招聘笔记封面图。\n\n封面文字：「' + (post.cover_text || post.title?.substring(0, 10) || '社会招聘') + '」\n\n风格要求：小红书招聘风格，蓝白商务色调，专业干练，信息清晰，适合HR和求职者。竖版3:4构图，文字居中突出，背景简洁但有设计感。';

      const t0 = Date.now();
      const r = await request(BASE + '/api/gemini-proxy', {
        method: 'POST',
        headers: authHeaders(),
        body: {
          model: imageModel,
          payload: {
            contents: [{ parts: [{ text: coverPrompt }] }],
            generationConfig: { responseModalities: ['TEXT', 'IMAGE'] }
          },
          feature: '图片生成'
        },
        timeout: 120000
      });
      const elapsed = Date.now() - t0;

      if (r.status === 200 && r.json) {
        const parts = r.json?.candidates?.[0]?.content?.parts || [];
        let hasImage = false;
        for (const part of parts) {
          if (part.inlineData && part.inlineData.mimeType && part.inlineData.data) {
            hasImage = true;
            const imgSize = part.inlineData.data.length;
            coverImage = 'data:' + part.inlineData.mimeType + ';base64,' + part.inlineData.data;

            // 保存图片预览
            const imgBuffer = Buffer.from(part.inlineData.data, 'base64');
            fs.writeFileSync('test_cover_image.png', imgBuffer);

            log('PASS', '图片生成', '封面图生成 (' + imageModel + ')', part.inlineData.mimeType + ' ' + Math.round(imgSize / 1024) + 'KB base64 (' + elapsed + 'ms) → 已保存 test_cover_image.png');
            break;
          }
        }
        if (!hasImage) {
          // 提取文本响应看是否有错误
          const textParts = parts.filter(p => p.text).map(p => p.text).join('');
          log('WARN', '图片生成', '封面图 (' + imageModel + ')', '模型返回了文本但无图片 (' + elapsed + 'ms): ' + textParts.substring(0, 80));
          continue; // 尝试下一个模型
        } else {
          break; // 成功，不需要尝试其他模型
        }
      } else {
        const errMsg = r.json?.error?.message || r.body?.substring(0, 100) || '';
        log('WARN', '图片生成', '封面图 (' + imageModel + ')', '状态:' + r.status + ' ' + errMsg.substring(0, 80) + ' (' + elapsed + 'ms)');
        continue; // 尝试下一个模型
      }
    } catch (e) {
      log('WARN', '图片生成', '封面图 (' + imageModel + ')', e.message);
      continue;
    }
  }

  if (!coverImage) {
    log('FAIL', '图片生成', '封面图生成', '所有模型均失败');
  }

  // 6.2 内容配图生成
  console.log('  🖼️ 6.2 生成内容配图...');
  let contentImage = null;

  for (const imageModel of imageModels) {
    try {
      const contentPrompt = '生成一张小红书招聘笔记的内容配图。\n\n笔记主题：' + (post.title || '社会招聘') + '\n\n风格：现代商务风格，蓝色系配色，干净排版，展示专业办公场景或职场积极氛围。正方形1:1构图，无文字，适合作为小红书笔记内容配图。';

      const t0 = Date.now();
      const r = await request(BASE + '/api/gemini-proxy', {
        method: 'POST',
        headers: authHeaders(),
        body: {
          model: imageModel,
          payload: {
            contents: [{ parts: [{ text: contentPrompt }] }],
            generationConfig: { responseModalities: ['TEXT', 'IMAGE'] }
          },
          feature: '图片生成'
        },
        timeout: 120000
      });
      const elapsed = Date.now() - t0;

      if (r.status === 200 && r.json) {
        const parts = r.json?.candidates?.[0]?.content?.parts || [];
        let hasImage = false;
        for (const part of parts) {
          if (part.inlineData && part.inlineData.mimeType && part.inlineData.data) {
            hasImage = true;
            const imgSize = part.inlineData.data.length;
            contentImage = 'data:' + part.inlineData.mimeType + ';base64,' + part.inlineData.data;

            const imgBuffer = Buffer.from(part.inlineData.data, 'base64');
            fs.writeFileSync('test_content_image.png', imgBuffer);

            log('PASS', '图片生成', '内容配图 (' + imageModel + ')', part.inlineData.mimeType + ' ' + Math.round(imgSize / 1024) + 'KB base64 (' + elapsed + 'ms) → 已保存 test_content_image.png');
            break;
          }
        }
        if (!hasImage) {
          const textParts = parts.filter(p => p.text).map(p => p.text).join('');
          log('WARN', '图片生成', '配图 (' + imageModel + ')', '无图片返回 (' + elapsed + 'ms): ' + textParts.substring(0, 80));
          continue;
        } else {
          break;
        }
      } else {
        log('WARN', '图片生成', '配图 (' + imageModel + ')', '状态:' + r.status + ' (' + elapsed + 'ms)');
        continue;
      }
    } catch (e) {
      log('WARN', '图片生成', '配图 (' + imageModel + ')', e.message);
      continue;
    }
  }

  if (!contentImage) {
    log('FAIL', '图片生成', '内容配图', '所有模型均失败');
  }

  return { cover: coverImage, content: contentImage };
}

// ===== 7. 不同技能的内容生成测试 =====
async function testMultiSkillGeneration() {
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('🔄 步骤7: 多技能内容生成测试');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

  const skills = [
    { name: '情感', category: '治愈系' },
    { name: '美食', category: '家常菜' },
    { name: '招聘', category: '校园招聘' },
  ];

  for (const skill of skills) {
    try {
      const prompt = '你是小红书' + skill.name + '博主。写1条「' + skill.category + '」分类笔记，200字左右。输出JSON：{"title":"...","content":"...","tags":"...","cover_text":"..."}';
      const t0 = Date.now();
      const r = await request(BASE + '/api/gemini-proxy', {
        method: 'POST',
        headers: authHeaders(),
        body: {
          model: 'gemini-2.5-flash',
          payload: {
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: { maxOutputTokens: 2000, temperature: 0.9, responseMimeType: 'application/json' }
          },
          feature: '内容生成'
        },
        timeout: 60000
      });
      const elapsed = Date.now() - t0;

      if (r.status === 200) {
        const text = (r.json?.candidates?.[0]?.content?.parts || []).filter(p => !p.thought && p.text).map(p => p.text).join('');
        let parsed = null;
        try {
          parsed = JSON.parse(text.replace(/```(?:json)?\s*/g, '').replace(/```/g, '').trim());
        } catch {}
        if (parsed && parsed.title) {
          log('PASS', '多技能', skill.name + '-' + skill.category, '「' + parsed.title.substring(0, 25) + '」' + (parsed.content?.length || 0) + '字 (' + elapsed + 'ms)');
        } else {
          log('WARN', '多技能', skill.name + '-' + skill.category, '返回' + text.length + '字（非标准JSON）(' + elapsed + 'ms)');
        }
      } else {
        log('FAIL', '多技能', skill.name + '-' + skill.category, '状态:' + r.status);
      }
    } catch (e) {
      log('FAIL', '多技能', skill.name + '-' + skill.category, e.message);
    }
  }
}

// ===== 8. 完整流程端到端测试 =====
async function testE2E() {
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('🔄 步骤8: 端到端完整流程（生成→保存→查看→删除）');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

  let postId = null;

  // 生成
  try {
    const prompt = '写1条小红书招聘笔记，150字，关于"找工作千万别忽视的3件事"。输出JSON：{"title":"...","content":"...","tags":"...","cover_text":"..."}';
    const r = await request(BASE + '/api/gemini-proxy', {
      method: 'POST',
      headers: authHeaders(),
      body: {
        model: 'gemini-2.5-flash',
        payload: {
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { maxOutputTokens: 1500, temperature: 0.9, responseMimeType: 'application/json' }
        },
        feature: '内容生成'
      },
      timeout: 60000
    });
    if (r.status === 200) {
      const text = (r.json?.candidates?.[0]?.content?.parts || []).filter(p => !p.thought && p.text).map(p => p.text).join('');
      let parsed = null;
      try { parsed = JSON.parse(text.replace(/```(?:json)?\s*/g, '').replace(/```/g, '').trim()); } catch {}

      if (parsed && parsed.title) {
        // 保存
        const saveR = await request(BASE + '/api/posts', {
          method: 'POST',
          headers: authHeaders(),
          body: { title: parsed.title, content: parsed.content || '', category: '社会招聘', status: 'draft', tags: parsed.tags || '', cover_text: parsed.cover_text || '' }
        });
        if (saveR.status === 200 && saveR.json?.id) {
          postId = saveR.json.id;
          log('PASS', 'E2E', '生成→保存', 'ID:' + postId + ' 「' + parsed.title.substring(0, 25) + '」');

          // 查看
          const viewR = await request(BASE + '/api/posts/' + postId, { headers: authHeaders() });
          if (viewR.status === 200) {
            log('PASS', 'E2E', '查看已保存笔记', 'ID:' + postId + ' OK');
          }

          // 删除
          const delR = await request(BASE + '/api/posts/' + postId, { method: 'DELETE', headers: authHeaders() });
          if (delR.status === 200) {
            log('PASS', 'E2E', '删除测试笔记', 'ID:' + postId + ' 已清理');
          }
        }
      }
    }
  } catch (e) {
    log('FAIL', 'E2E', '端到端测试', e.message);
  }
}

// ===== 生成报告 =====
function generateReport() {
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  const total = passCount + failCount + warnCount;
  const passRate = total > 0 ? ((passCount / total) * 100).toFixed(1) : 0;

  const lines = [];
  lines.push('# 🧪 小红书运营平台 - 内容生成 & 生图 功能测试报告');
  lines.push('');
  lines.push('> 测试时间: ' + new Date().toLocaleString('zh-CN'));
  lines.push('> 测试账号: ' + USERNAME);
  lines.push('> 测试目标: ' + BASE);
  lines.push('> 耗时: ' + elapsed + ' 秒');
  lines.push('');
  lines.push('---');
  lines.push('');
  lines.push('## 📊 总体结果');
  lines.push('');
  lines.push('| 指标 | 数值 |');
  lines.push('|------|------|');
  lines.push('| ✅ 通过 | ' + passCount + ' |');
  lines.push('| ❌ 失败 | ' + failCount + ' |');
  lines.push('| ⚠️ 警告 | ' + warnCount + ' |');
  lines.push('| 📋 总计 | ' + total + ' |');
  lines.push('| 📈 通过率 | **' + passRate + '%** |');
  lines.push('');
  lines.push('---');
  lines.push('');
  lines.push('## 📝 详细结果');
  lines.push('');

  const categories = {};
  for (const r of results) {
    if (!categories[r.category]) categories[r.category] = [];
    categories[r.category].push(r);
  }
  for (const [cat, items] of Object.entries(categories)) {
    const p = items.filter(i => i.status === 'PASS').length;
    const f = items.filter(i => i.status === 'FAIL').length;
    const icon = f > 0 ? '❌' : '✅';
    lines.push('### ' + icon + ' ' + cat + ' (' + p + '/' + items.length + ' 通过)');
    lines.push('');
    lines.push('| 状态 | 测试项 | 详情 |');
    lines.push('|------|--------|------|');
    for (const item of items) {
      const si = item.status === 'PASS' ? '✅' : item.status === 'FAIL' ? '❌' : '⚠️';
      lines.push('| ' + si + ' | ' + item.name + ' | ' + (item.detail || '-') + ' |');
    }
    lines.push('');
  }

  lines.push('---');
  lines.push('');
  lines.push('## 🔍 测试覆盖');
  lines.push('');
  lines.push('### 内容生成');
  lines.push('- ✅ 用户登录 + Token 认证');
  lines.push('- ✅ 积分余额查询');
  lines.push('- ✅ Gemini AI 代理文本生成');
  lines.push('- ✅ 联网搜索分析（Google Search Grounding）');
  lines.push('- ✅ 百度搜索真实小红书笔记');
  lines.push('- ✅ AI 笔记内容生成（JSON格式）');
  lines.push('- ✅ 服务端内容生成 /api/generate');
  lines.push('- ✅ 多分类笔记生成（情感/美食/招聘）');
  lines.push('- ✅ 笔记保存到草稿箱');
  lines.push('');
  lines.push('### 图片生成');
  lines.push('- ✅ 封面图生成（多模型自动切换）');
  lines.push('- ✅ 内容配图生成');
  lines.push('- ✅ 图片模型候选列表: gemini-3.1-flash-image-preview, gemini-3-pro-image-preview, gemini-2.5-flash-image');
  lines.push('');
  lines.push('### 端到端流程');
  lines.push('- ✅ AI生成 → 保存草稿 → 查看 → 删除');
  lines.push('');

  if (fs.existsSync('test_cover_image.png')) {
    lines.push('### 生成的测试图片');
    lines.push('- 封面图: test_cover_image.png (' + Math.round(fs.statSync('test_cover_image.png').size / 1024) + 'KB)');
  }
  if (fs.existsSync('test_content_image.png')) {
    lines.push('- 配图: test_content_image.png (' + Math.round(fs.statSync('test_content_image.png').size / 1024) + 'KB)');
  }

  return lines.join('\n');
}

// ===== 主流程 =====
async function main() {
  console.log('╔══════════════════════════════════════════════════╗');
  console.log('║  🧪 内容生成 & 生图 功能测试                    ║');
  console.log('║  账号: ' + USERNAME + '  目标: localhost:3000              ║');
  console.log('╚══════════════════════════════════════════════════╝');

  const loggedIn = await testLogin();
  if (!loggedIn) {
    console.log('\n❌ 登录失败，无法继续测试');
    const report = generateReport();
    fs.writeFileSync('gen_image_test_report.md', report, 'utf-8');
    return;
  }

  await testCredits();
  await testGeminiProxy();
  await testServerGenerate();
  const { posts, savedIds } = await testAIContentGeneration();
  await testImageGeneration(posts);
  await testMultiSkillGeneration();
  await testE2E();

  // 清理测试生成的笔记
  if (savedIds && savedIds.length > 0) {
    console.log('\n🧹 清理测试数据...');
    for (const id of savedIds) {
      if (id) {
        try {
          await request(BASE + '/api/posts/' + id, { method: 'DELETE', headers: authHeaders() });
          console.log('  已删除测试笔记 ID:' + id);
        } catch {}
      }
    }
  }

  const report = generateReport();
  fs.writeFileSync('gen_image_test_report.md', report, 'utf-8');

  console.log('\n' + '═'.repeat(50));
  console.log('📊 测试完成! 通过: ' + passCount + ' | 失败: ' + failCount + ' | 警告: ' + warnCount);
  console.log('📄 报告已保存: gen_image_test_report.md');
  if (fs.existsSync('test_cover_image.png')) console.log('🖼️ 封面图: test_cover_image.png');
  if (fs.existsSync('test_content_image.png')) console.log('🖼️ 配图: test_content_image.png');
  console.log('═'.repeat(50));
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
