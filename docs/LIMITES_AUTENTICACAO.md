# Limites de autenticação

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

## Consistência

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

## Verificação e limites de implantação

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
