# Validação local em 05/11/2026

Resultado: os cenários abaixo passaram. Execução com os arquivos locais do projeto,
na instância MySQL configurada em `backend/.env`, usando bases temporárias exclusivas.
As bases temporárias foram removidas ao terminar. Não houve alteração de estoque,
usuários ou permissões globais da base operacional.

## Ambiente e resultados

| Verificação | Resultado |
| --- | --- |
| Python `unittest discover -s tests -v` | 186 aprovados; banco simulado |
| Node `--test --test-isolation=none tests/*.test.cjs` | 25 aprovados |
| `pip check` | Sem conflitos de dependências |
| `check_frontend.cjs` | Sintaxe de 54 scripts aprovada |
| Auditoria estática | Nenhum asset ausente, ID HTML duplicado ou import de backend não utilizado |
| MySQL real | MySQL Community Server 8.0.46 |
| Navegador real | Chrome 156.0.8078.80, headless, via Playwright |

## Integração com MySQL

- Inspeção sem gravação da base configurada confirmou `finalidade`, `motivo` e
  `fornecedor_id` na tabela `movimentacoes_estoque`.
- Schema novo criado em base temporária, excluindo instruções de roles globais.
- Migrações 022 e 023 aplicadas sobre tabela sem as três colunas; 023 reaplicada
  sem erro de coluna duplicada.
- Login, sessão e token CSRF reais, com banco persistente.
- Descarte de lote vencido: 23 unidades menos 5 resultaram em 18.
- Devolução do mesmo lote: 18 menos 4 resultaram em 14, com fornecedor registrado.
- Devolução de produto sem fornecedor preservou referência nula.
- Quantidades zero, negativas, fracionárias, excessivas, booleanas e textuais foram
  rejeitadas. Motivo vazio, fornecedor divergente, saída comum de lote vencido e
  requisição sem CSRF também foram rejeitados, sem movimentação adicional.
- Histórico, busca com e sem resultados, paginação, contagem e auditoria persistida
  aprovados.
- Verificação existente de catálogo aprovada: schema, migração de legado,
  reaplicação, cadastro misto, edição, compras, vendas e estoque. A execução excluiu
  o cabeçalho de roles globais do schema.

## Fluxo completo no navegador

Login pelos campos da interface, abertura de Vencimentos e cliques nos botões do
modal. Nenhuma API foi simulada: navegador → Flask por HTTP → MySQL real.

Descarte e devolução retornaram HTTP 201; a consulta SQL confirmou os saldos 18 e
14 e a página atualizou os valores sem recarregamento manual. Quantidade 999 foi
bloqueada pela interface. Não ocorreram exceções JavaScript. O modal coube nas
larguras de 1440 e 390 pixels; as capturas foram inspecionadas visualmente.

Na validação inicial foi observada uma inconsistência de texto no modal. Ela foi
corrigida: título e explicação agora acompanham a seleção entre descarte e
devolução. A verificação no Chrome cobre alternância nas duas direções e reabertura
do modal, que volta a apresentar os textos de descarte. As operações continuam
gravadas com a finalidade correta.

## Evidências e reprodução

- Script: `scripts/check_devolucao_mysql.py --browser`.
- Evidências publicadas: [resultado estruturado](evidencias/2026-11-05/devolucao-report.json),
  [descarte desktop](evidencias/2026-11-05/vencimentos-desktop.png),
  [descarte móvel](evidencias/2026-11-05/vencimentos-mobile.png),
  [devolução desktop](evidencias/2026-11-05/devolucao-desktop.png) e
  [devolução móvel](evidencias/2026-11-05/devolucao-mobile.png).
- A execução gera as evidências em `.audit-backup/integration-20261105/`;
  as cópias acima registram a execução após a correção visual.
- Executar pela raiz com Python, dependências do backend, Playwright Python e
  Chrome instalado. `CHROME_PATH` permite indicar outro caminho do Chrome.
- O usuário MySQL precisa poder criar e remover a base temporária de testes.

## Limites

As gravações foram feitas em bases temporárias na mesma instância, com schema do
projeto e usuário de teste proprietário. Isso comprova os cenários executados neste
ambiente, mas não testa todos os dados legados, perfis, dispositivos, SMTP,
concorrência, carga de produção ou configuração de uma implantação externa.
