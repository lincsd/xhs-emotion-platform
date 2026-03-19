const h = require('fs').readFileSync('_test_chunk.js', 'utf8');
const lines = h.split('\n');
let braceDepth = 0;
let inStr = false, strChar = '';

for (let ln = 0; ln < lines.length; ln++) {
  const line = lines[ln];
  let prevDepth = braceDepth;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inStr) {
      if (c === strChar && line[i-1] !== '\\') inStr = false;
      continue;
    }
    if (c === '/' && line[i+1] === '/') break;
    if (c === "'" || c === '"' || c === '`') { inStr = true; strChar = c; continue; }
    if (c === '{') braceDepth++;
    if (c === '}') braceDepth--;
  }
  if (braceDepth !== prevDepth) {
    console.log(`L${ln+1} depth:${prevDepth}->${braceDepth}  ${line.trim().slice(0,70)}`);
  }
}
console.log('Final brace depth:', braceDepth);
