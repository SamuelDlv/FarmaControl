# Segurança: autenticação e permissões

Política e revisão de **11/11/2026**, consolidadas na mesma data. Configuração geral em [backend](../backend/README.md); contratos HTTP em [API](api.md). A revisão de vulnerabilidades de 15/10 permanece no [histórico](historico/2026-10.md#seguranca-2026-10-15).

- [Limites de autenticação](#limites)
- [Perfis e permissões](#permissoes)

<a id="limites"></a>

## Limites de autenticação

Política atualizada em 11/11/2026 para uso local e redes compartilhadas pequenas.

| Controle | Limite | Quando reinicia |
| --- | --- | --- |
| Falhas por conta | 5 falhas em janela de 300 segundos | Login aprovado e auditado com sucesso, ou expiração da janela |
| Autenticação por IP | 100 requisições em janela de 300 segundos | Somente expiração da janela |
| Cadastro, recuperação, redefinição e recusa de convite | 5 solicitações por operação/IP em 300 segundos | Somente expiração da janela |
| Logout | Fora dessas cotas | Não altera os contadores |

Os 100 acessos por IP são uma escolha inicial do projeto, permitindo troca de
perfis e vários usuários atrás do mesmo endereço de rede. A cota abrange
mutações de `/auth/`, exceto logout; não conta navegação, consultas normais da
API nem arquivos estáticos. Todas essas requisições de autenticação contam,
inclusive as bem-sucedidas. O endereço vem de `request.remote_addr`, sem confiar
em `X-Forwarded-For` enviado pelo cliente.

O contador de falhas usa a conta encontrada no banco, independentemente do IP.
Sua chave é um HMAC opaco do ID; variações de e-mail que o banco reconheça como
a mesma conta não criam cotas diferentes. Contas inexistentes recebem a mesma
mensagem e o mesmo contrato de tentativas, usando chave opaca do e-mail
normalizado. A orientação de vincular falhas à conta é descrita pela
[OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#login-throttling).
Os limites numéricos acima são escolhas deste projeto, não números prescritos
por essa referência.

Exemplo: quatro senhas incorretas, seguidas por um login válido, deixam a conta
sem falhas acumuladas. O logout não muda isso. Após sair, uma nova senha errada
deixa quatro tentativas disponíveis; a cota geral do IP continua acumulada.
Após cinco falhas, é necessário aguardar a janela, mesmo conhecendo a senha.
Entrar em outra conta não limpa o bloqueio da primeira conta.

### Consistência

Reservas atômicas limitam verificações simultâneas por conta. Somente senha
incorreta/conta inexistente concluem a reserva como falha; falhas de conexão,
auditoria e contas não aprovadas liberam a reserva sem consumir uma falha.
Login aprovado só zera falhas depois de confirmar sua auditoria. O reset não
apaga verificações de outras requisições em andamento. Reservas têm prazo e
conclusão idempotente, evitando incrementos duplicados.

Logout mantém origem, CSRF e auditoria. Ele permanece disponível com cotas
esgotadas, sem limpar bloqueios de conta ou IP. Cadastro e recuperação não
compartilham o contador de falhas de login.

Respostas de bloqueio identificam `limite_escopo` (`conta`, `ip` ou `acao`),
`tentativas_restantes`, `aguarde_segundos` e `Retry-After`. A interface mostra
qual cota bloqueou a operação; mudar o e-mail limpa o aviso de outra conta,
mas não esconde um bloqueio geral do IP. Isso não muda a autorização da API.

### Verificação e limites de implantação

`tests/test_login_limits.py` cobre o exemplo acima, contas diferentes, IPs
diferentes, a cota real de 100, logout, reserva concorrente, expiração,
capacidade de memória, falhas de banco/auditoria e respostas genéricas.
`tests/login-attempts.test.cjs` cobre a apresentação do bloqueio e a troca de
e-mail. Os testes usam dados e conexões simulados.

`python scripts/check_login_limits.py` reproduz no Chrome isolado quatro
falhas, login correto, logout e nova falha com quatro tentativas disponíveis.
Usa HTML/JavaScript reais e a API Flask com banco simulado; capturas ficam
somente em `.audit-backup/limites-login/`.

Os contadores permanecem em memória por processo, como a implementação
anterior. Reiniciar o backend limpa todos; múltiplos workers precisam de um
armazenamento compartilhado para aplicar uma cota única entre processos.
Nenhuma migração ou alteração de contas/permissões do banco é necessária.

<a id="permissoes"></a>

## Perfis e permissões — 11/11/2026

O erro de logout HTTP 429 vinha do limite compartilhado das rotas de
autenticação, não da autorização do Atendente. Logout deixa de consumir ou
depender dessa cota, preservando origem, CSRF, auditoria e tratamento de falhas.
Login e demais mutações de autenticação continuam limitados por IP/processo.

### Padrões dos perfis

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

### Correções adicionais

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

### Verificação e limites

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
