# Verificações automáticas

O workflow `.github/workflows/ci.yml` roda em pushes para `main`, pull requests e
acionamento manual pelo GitHub Actions. Usa Python 3.12, Node 22 e Ubuntu 24.04.

## Unitários e auditoria

- Instala as dependências fixadas e executa `pip check`.
- Executa todos os testes Python e JavaScript, sem banco real.
- Valida sintaxe dos scripts frontend.
- Falha se a auditoria encontrar assets ausentes, IDs HTML duplicados ou imports
  de backend não utilizados. Repetições de CSS continuam apenas informativas.

## MySQL e navegador

- Inicia MySQL 8.0.46 em um serviço descartável, com credenciais exclusivas do job.
- Instala `requirements-dev.txt` e Chromium pelo Playwright.
- Executa `check_migrations_mysql.py`, `check_catalogo_mysql.py` e
  `check_devolucao_mysql.py --browser`.
- Os testes criam e removem bases aleatórias. Não usam o `.env` privado da instalação.
- Não publica screenshots nem faz deploy ou migração da base operacional.

Os dois jobs precisam ficar verdes para a validação ser considerada concluída.
O workflow publica resultados na aba Actions. Exigir esses checks antes de merge
depende de uma regra de proteção da branch; criar o workflow não ativa essa regra.

## Reprodução local

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -B -m unittest discover -s tests -v
node --test tests/*.test.cjs
node scripts/check_frontend.cjs
python -B scripts/audit_static.py
python -B scripts/check_migrations_mysql.py
python -B scripts/check_catalogo_mysql.py
python -B scripts/check_devolucao_mysql.py --browser
```

No Windows, o teste usa o Chrome instalado quando disponível; `CHROME_PATH`
permite escolher outro executável. No CI Linux usa o Chromium instalado pelo
Playwright. Os testes de integração exigem MySQL local e credenciais com permissão
para criar/remover bases temporárias. Variáveis `DB_*` de ambiente prevalecem sobre
`backend/.env`.

Referências: [workflows Python do GitHub](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
e [instalação de navegadores Playwright](https://playwright.dev/python/docs/browsers).
