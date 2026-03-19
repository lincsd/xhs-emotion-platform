const https = require('https');
const opts = {
  hostname: 'xhs.xiaohsai.com',
  path: '/?v=' + Date.now(),
  headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' }
};
const req = https.request(opts, r => {
  const chunks = [];
  r.on('data', c => chunks.push(c));
  r.on('end', () => {
    const buf = Buffer.concat(chunks);
    const s = buf.toString('utf8');
    console.log('size:', s.length);
    console.log('has招聘:', s.includes('\u62db\u8058'));
    const idx = s.indexOf('id="skill-switcher"');
    if (idx > -1) {
      const end = s.indexOf('</select>', idx);
      if (end > -1) console.log('dropdown:', s.substring(idx, end + 9));
    } else {
      console.log('skill-switcher not found in page!');
    }
  });
});
req.on('error', e => console.log('err:', e.code || e.message));
req.end();
