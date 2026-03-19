const h = require('fs').readFileSync('_test_chunk.js', 'utf8');
const lines = h.split('\n');
let braceDepth = 0, bracketDepth = 0;
let inStr = false, strChar = '';

for (let ln = 0; ln < lines.length; ln++) {
  const line = lines[ln];
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inStr) {
      if (c === strChar && line[i-1] !== '\\') inStr = false;
      continue;
    }
    if (c === '/' && line[i+1] === '/') break; // skip rest of line comment
    if (c === "'" || c === '"' || c === '`') { inStr = true; strChar = c; continue; }
    if (c === '{') braceDepth++;
    if (c === '}') braceDepth--;
    if (c === '[') bracketDepth++;
    if (c === ']') bracketDepth--;
    if (braceDepth < 0 || bracketDepth < 0) {
      console.log(`Unmatched at line ${ln+1}: char='${c}' braces=${braceDepth} brackets=${bracketDepth}`);
      console.log('  >', line.trim().slice(0, 80));
      process.exit(1);
    }
  }
}
console.log(`Final: braces=${braceDepth} brackets=${bracketDepth}`);
