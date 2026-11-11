# Revisão de permissões — 11/11/2026

O erro de logout HTTP 429 vinha do limite compartilhado das rotas de
autenticação, não da autorização do Atendente. Logout deixa de consumir ou
depender dessa cota, preservando origem, CSRF, auditoria e tratamento de falhas.
Login e demais mutações de autenticação continuam limitados por IP/processo.

## Padrões dos perfis

| Perfil | Módulos padrão | Escrita e regras fixas |
| --- | --- | --- |
| Proprietário | Todos os módulos | Operações dos módulos concedidos, PDV e log |
| Gerente / Administrador | Todos os módulos | Operações dos módulos concedidos, PDV e log |
| TI / Suporte | Todos os módulos | Acesso amplo mantido conforme a matriz existente |
| Farmacêutico | Dashboard, estoque, vencimentos, compras e relatórios | Estoque/compras e PDV; sem log administrativo |
| Compras | Dashboard, estoque, vencimentos, compras e relatórios | Estoque/compras; sem PDV nem log administrativo |
| Atendente | Dashboard e estoque, mais PDV por regra fixa | Vendas; estoque e vencimentos somente consulta |
| Visualizador | Dashboard, estoque, vencimentos e relatórios | Somente consulta; nenhuma mutação de módulos |

Logout é permitido para todos os perfis, inclusive sem módulos concedidos.
Visualizador pode encerrar a própria sessão: a proibição de escrita refere-se
a operações do sistema, não à saída da sessão.

Foi consultada somente a configuração de perfis/módulos no banco local. Os sete
perfis estavam com os padrões do schema. Não foram alteradas permissões,
contas, credenciais ou dados operacionais. A matriz configurável permanece
válida; conceder um módulo não remove as restrições de somente consulta.
PDV permanece exclusivo de proprietário, administrador, farmacêutico,
atendente e TI; log permanece exclusivo de proprietário, administrador e TI.

## Correções adicionais

- Atendente não pode cadastrar, editar, excluir ou movimentar estoque pela
  API. Os respectivos controles deixam de aparecer na interface.
- Atalhos de movimentação, reposição e novo lote em outras telas respeitam a
  capacidade de escrita no estoque. Consultas, histórico e exportação de
  estoque continuam disponíveis aos perfis autorizados.
- HTML, API e capacidades do menu usam a mesma política no servidor.
- Contexto validado em cada HTML prevalece sobre perfil/permissões antigos
  guardados no navegador; inclui o CSRF necessário para outra aba autenticada.
- Login escolhe uma página permitida, sem depender de acesso ao dashboard.
- Perfis sem configurações administrativas carregam somente a aparência
  pública, evitando chamadas HTTP 403 desnecessárias.
- Exportação financeira em Relatórios exige acesso ao módulo Financeiro.

## Verificação e limites

`tests/test_permissions.py` percorre todos os endpoints protegidos e as páginas
canônicas/legadas nos sete perfis. Testa concessões explícitas, bloqueios de
escrita, contexto revalidado, página inicial e logout com cota de login esgotada.
Os handlers de negócio são substituídos nesse teste para provar que ações
negadas não chegam à operação; os demais testes de domínio continuam separados.

`scripts/check_permissoes.py` usa Chrome isolado, HTML real gerado pelo Flask e
banco/API simulados. Confere menu, controles estáticos/dinâmicos de estoque,
carregamento de preferências e logout dos sete perfis, inclusive com perfil e
token antigos no cache. Prints ficam somente em `.audit-backup/permissoes/`.

Isso não equivale a executar todas as operações com sete contas reais na base
operacional. Não foram feitos cadastros, vendas, compras ou ajustes reais para
testar permissões. Reinicie o backend e atualize as páginas após a publicação.
