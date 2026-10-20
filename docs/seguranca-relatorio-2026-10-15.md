# Relatório de segurança — FarmaControl

> **Revisão histórica de 15/10.** Nota documental de 19/10/2026: as consultas de vulnerabilidades e os resultados abaixo não foram repetidos nesta atualização dos Markdown. O ambiente `.venv-audit` citado foi destinado à limpeza; novas instalações devem criar `.venv`. Consulte [desenvolvimento](DESENVOLVIMENTO.md) para reproduzir as verificações locais e [backend](../backend/README.md) para configuração e autorização atuais. Este relatório não atesta a situação atual de serviços externos ou dependências além da consulta datada.

Data: **15/10/2026** (America/Sao_Paulo).

## Resultado

Foram corrigidos problemas de autenticação, revogação de sessões, consumo de tokens, validação de entradas e proteção HTTP. Quatro dependências foram atualizadas. A consulta final do `pip-audit` não encontrou vulnerabilidades conhecidas nas 12 dependências fixadas em `backend/requirements.txt`.

Esta é uma revisão do código local com testes isolados. Não constitui certificação de ausência de vulnerabilidades nem teste de invasão da infraestrutura publicada.

## Escopo e método

- Leitura do backend Flask, configuração, autenticação, autorização, auditoria e consultas SQL; busca de pontos de inserção HTML no frontend e revisão por amostragem.
- Testes HTTP pelo cliente de testes do Flask, com conexões reais ao banco explicitamente bloqueadas e dados simulados. Nenhuma exploração foi executada contra dados reais.
- Consulta pública de vulnerabilidades pelo `pip-audit` 2.10.1 e documentação dos mantenedores. Somente nomes e versões das dependências foram necessários para essa consulta.
- Nenhum e-mail real enviado, nenhuma migração aplicada e nenhum segredo do `.env` copiado para este relatório.
- A suíte inicial passou em 103 testes. A suíte final contém 120 testes, incluindo 17 novos testes de segurança.

## Achados e correções

As prioridades abaixo são avaliações locais de impacto, não pontuações CVSS.

| Achado | Prioridade | Evidência e impacto anterior | Correção |
| --- | --- | --- | --- |
| Sessões sobreviviam à troca de senha | Alta | A validação consultava status/perfil, sem vínculo com a senha atual. Um cookie obtido anteriormente continuava aceito após redefinição. | O cookie contém um HMAC da credencial, verificado contra o hash atual no banco em cada acesso protegido. O hash bcrypt não é exposto no cookie. Login e aceite de convite geram esse vínculo. |
| Recuperação de senha com janela de concorrência | Alta | Leitura do token e atualização eram separadas, sem bloqueio da linha. Requisições concorrentes poderiam validar o mesmo token antes de consumi-lo. | `SELECT ... FOR UPDATE` mantém a validação e o consumo na mesma transação. A alteração administrativa da senha também elimina tokens de recuperação anteriores. |
| Aceite de convite sem verificar consumo | Média | A atualização final não verificava quantas linhas haviam sido consumidas nem repetia a validade. | Bloqueio do convite durante a transação, condição de validade na atualização e rollback se exatamente um convite não for consumido. |
| Tentativas de autenticação sem limite | Alta | Login, cadastro e recuperação permitiam repetição sem contenção na aplicação. | Limite compartilhado entre mutações `/auth/`: 20 requisições por IP em 300 segundos, por processo; resposta 429 com `Retry-After`, proteção de concorrência e até 4096 entradas. |
| JSON e campos de autenticação malformados | Média | Listas no lugar de objetos, campos estruturados e senhas acima de 72 bytes podiam causar exceções; bcrypt 5 rejeita senhas longas. | Validação de objeto JSON, tipos dos campos de autenticação/administração, UTF-8 válido e máximo de 72 bytes para senhas. Erros retornam 400. Não há truncamento silencioso da senha. |
| Corpo da requisição sem limite explícito | Média | O servidor podia tentar carregar JSON excessivamente grande. | Limite de 1 MiB no Flask; resposta JSON 413 antes de acesso ao banco nos testes. |
| Cabeçalho CSRF não ASCII e permissões com objetos | Baixa | Comparação de strings não ASCII e conversão de objetos para conjunto podiam gerar erro 500. | Comparação CSRF em bytes e validação dos elementos da lista de módulos. |
| IP dos registros controlável pelo cliente | Média | `X-Forwarded-For` era utilizado diretamente nos registros de acesso e aceites legais. | Uso de `request.remote_addr`. Cabeçalhos forjados não alteram o IP nem contornam o limitador. |
| Ausência de endurecimento HTTP | Média | Sem política explícita contra enquadramento, envio de referências e armazenamento de respostas sensíveis. | `DENY`, `nosniff`, `no-referrer`, CSP com `frame-ancestors`, `object-src` e `base-uri`; `no-store` nas APIs protegidas e autenticação; HSTS em produção. |
| Mutações de autenticação sem validação de origem | Média, defesa adicional | As rotas públicas de autenticação não passavam pelo CSRF das APIs protegidas. | Quando `Origin` está presente, somente a própria origem ou `ALLOWED_ORIGINS` são aceitas. Clientes sem Origin continuam suportados; a proteção CSRF existente das APIs é preservada. |
| Dependências desatualizadas | Variável | Versões fixadas anteriores incluíam pacotes com avisos de segurança publicados. | Atualizações da tabela seguinte; instalação e testes no ambiente `.venv-audit`. |

## Dependências

| Pacote | Antes | Depois |
| --- | --- | --- |
| Flask | 3.1.0 | 3.1.3 |
| Flask-Cors | 5.0.0 | 6.0.1 |
| python-dotenv | 1.0.1 | 1.2.2 |
| Werkzeug | 3.1.8 | 3.1.9 |

A primeira tentativa de atualização conservadora para Flask 3.1.2 ainda apresentou avisos. A consulta automatizada indicou correções em Flask 3.1.3 (`PYSEC-2026-2151`), python-dotenv 1.2.2 (`PYSEC-2026-2270`) e Werkzeug 3.1.9 (`PYSEC-2026-4312`); essas versões foram instaladas e novamente auditadas. O serviço retornou entradas duplicadas para dois avisos, portanto a contagem bruta não representa cinco problemas distintos.

O aviso de rotação de chaves do Flask 3.1.0 depende de `SECRET_KEY_FALLBACKS`, que não foi encontrado configurado no código revisado. O aviso do python-dotenv envolve escrita por `set_key`/`unset_key`; a aplicação revisada usa leitura por `load_dotenv`. Atualizar esses componentes é prevenção, não evidência de exploração no FarmaControl. O CORS também passou a negar explicitamente `allow_private_network`.

Evidência final: [seguranca-dependencias-2026-10-15.json](seguranca-dependencias-2026-10-15.json). A consulta usa `--no-deps --disable-pip` porque o arquivo enumera também as dependências transitivas fixadas; não audita bibliotecas externas carregadas pelo navegador, sistema operacional ou servidor MySQL.

## Validação reproduzível

Na raiz do projeto, PowerShell:

```powershell
.\.venv-audit\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
.\.venv-audit\Scripts\python.exe -m pip check
.\.venv-audit\Scripts\python.exe -m pip_audit -r backend/requirements.txt --no-deps --disable-pip --format json --output docs/seguranca-dependencias-2026-10-15.json
```

Resultados: **120 testes aprovados**, `pip check` sem incompatibilidades e auditoria final sem vulnerabilidades conhecidas nas versões consultadas. Os logs de erro simulados durante os testes de rollback são esperados.

Os novos testes cobrem: limitação de tentativas e falsificação de IP; expiração e capacidade do limitador; origem externa; JSON inválido; senha multibyte nos limites; corpo grande; sessão antiga e sessão após troca de senha; HMAC sem divulgação do hash; SQL de bloqueio do token; invalidação administrativa do reset; rollback e sucesso no aceite de convite; cabeçalhos HTTP; CSRF não ASCII e módulos estruturados inválidos.

**Limitação dos testes de concorrência:** o banco é simulado. Os testes verificam bloqueio SQL e rollback, mas não executam duas conexões concorrentes reais no MariaDB. Essa validação de integração permanece necessária antes de uma implantação crítica.

## Efeito operacional e pendências

1. **Reiniciar o backend para carregar as correções.** Nenhum processo em execução foi reiniciado nesta revisão. Sessões emitidas antes desta atualização exigirão novo login por não conterem o vínculo de credencial. Não há alteração de schema.
2. O ambiente `.venv-audit` foi atualizado. Se a instalação usar outra `.venv` ou outro servidor, instalar `backend/requirements.txt` nesse ambiente antes de iniciar.
3. O limitador é local e perde estado no reinício; múltiplos workers multiplicam o limite. Ataques distribuídos requerem limite compartilhado no proxy ou armazenamento central. Atrás de proxy, o IP observado pode ser o do próprio proxy, compartilhando a cota entre usuários. Não habilitar confiança irrestrita em `X-Forwarded-For`.
4. O consumo único depende de tabelas transacionais e dos bloqueios do banco. Validar essa configuração e a concorrência em um banco descartável.
5. A CSP adicionada impede enquadramento e objetos, mas **não restringe scripts**. O frontend usa scripts/handlers inline; uma CSP completa e testes de XSS em navegador exigem trabalho específico. A busca estática de `innerHTML` não garante ausência de XSS.
6. A autorização por módulos persistidos foi preservada. Conceder o módulo `usuarios` a um perfil permite operações administrativas conforme a política atual; revisar a matriz com o responsável pela farmácia. O Visualizador continua sem escrita e o log mantém restrição fixa de cargos.
7. Logout elimina o cookie do navegador, mas não mantém lista central de revogação individual de cookies copiados. A troca de senha agora revoga todos os cookies vinculados à credencial anterior.
8. Infraestrutura HTTPS, restrição de Host no proxy, privilégios do usuário MySQL, backups, proteção do `.env` e configuração real de produção não foram auditados dinamicamente. Não foram examinados histórico Git nem segredos em backups. Não foram executados testes de navegador/JavaScript nesta rodada; não houve alteração de frontend.
9. O cadastro público ainda informa e-mail já existente, e o login pode apresentar diferença de tempo entre conta inexistente e senha incorreta. O limitador reduz abuso, mas não elimina enumeração de contas.

## Arquivos alterados/criados

- `backend/app.py`: validações, proteção de autenticação, sessão, transações de tokens e cabeçalhos.
- `backend/security.py`: HMAC e limitador local.
- `backend/runtime_config.py`: limite de corpo HTTP.
- `backend/requirements.txt`: versões corrigidas.
- `tests/test_security.py`: novos testes de segurança.
- `tests/test_backend.py`, `tests/test_catalogo.py`, `tests/test_pdv.py`: fixtures de sessão atualizadas para incluir a credencial consultada.
- Este relatório e o JSON da auditoria de dependências.

## Referências

- [Flask: considerações de segurança e limites de requisição](https://flask.palletsprojects.com/en/stable/web-security/).
- [Flask: aviso sobre rotação de chaves em 3.1.0](https://github.com/pallets/flask/security/advisories/GHSA-4grg-w6v8-c28g).
- [Flask-Cors: release 6.0.1](https://github.com/corydolphin/flask-cors/releases/tag/6.0.1).
- A evidência JSON vinculada acima registra as versões efetivamente consultadas no serviço de vulnerabilidades.
