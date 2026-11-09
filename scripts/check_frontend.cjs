/* Guia de manutenção — Verificador de frontend: confira pré-requisitos, argumentos e cenários antes de executar.
 * Os resultados cobrem os cenários descritos neste arquivo; mocks não comprovam integração real.
 */
/* Verifica sintaxe de scripts clássicos e scripts inline sem executar a aplicação. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..', 'frontend', 'src');
let count = 0;
// Percorre arquivos e verifica scripts externos e inline sem executar a aplicação.
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
