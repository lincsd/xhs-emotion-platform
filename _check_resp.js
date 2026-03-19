const f = require('fs').readFileSync('tunnel_response.bin', 'utf8');
console.log('size:', f.length);
console.log('has招聘:', f.includes('\u62db\u8058'));
const idx = f.indexOf('"skill-switcher"');
if (idx > 0) {
  const end = f.indexOf('</select>', idx);
  console.log('dropdown:', f.substring(idx, end + 9));
} else {
  console.log('skill-switcher not found');
}
