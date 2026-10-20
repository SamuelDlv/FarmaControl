/* Verifica sintaxe de scripts clássicos e scripts inline sem executar a aplicação. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..', 'frontend', 'src');
let count = 0;
function scan(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      scan(file);
      continue;
    }
    const source = fs.readFileSync(file, 'utf8');
    if (file.endsWith('.js')) {
      new vm.Script(source, { filename: file });
      count++;
    }
    if (file.endsWith('.html')) {
      for (const match of source.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)) {
        if (match[1].trim()) {
          new vm.Script(match[1], { filename: file + ':inline' });
          count++;
        }
      }
    }
  }
}
scan(root);
console.log('Sintaxe JavaScript validada: ' + count + ' scripts (externos e inline).');
