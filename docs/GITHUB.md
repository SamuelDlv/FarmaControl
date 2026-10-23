# Versionamento e publicação no GitHub

Revisado em 23/10/2026. Execute os comandos na raiz do projeto, com Git instalado. Publicar o código não hospeda a API Flask nem o banco MySQL.

## Conteúdo do repositório

Versione `backend/` sem o `.env`, `frontend/`, `tests/`, `scripts/`, `docs/`, `README.md`, `LICENSE`, os arquivos `.bat`, `.gitignore` e `.gitattributes`. Mantenha `backend/.env.example` como modelo sem credenciais.

O `.gitignore` exclui ambientes virtuais, arquivos `.env` e suas variantes privadas, caches, logs, resultados de auditoria, backups e arquivos locais de banco. Arquivos SQL de schema e migrações são código do projeto e devem permanecer versionados. Exportações de dados reais não devem ser colocadas entre as migrações.

O `.gitattributes` normaliza arquivos de texto e preserva CRLF nos scripts `.bat`. Favicons e documentos binários são tratados como binários.

## Primeiro envio

Crie no GitHub um repositório vazio, sem README ou licença gerados automaticamente. Use a URL dele no comando `remote add`:

```powershell
git init -b main
git add .
git status --short
git diff --cached --stat
git diff --cached -- backend/.env.example .gitignore
git check-ignore backend/.env
git ls-files -- backend/.env
```

O penúltimo comando deve listar o `.env`; o último não deve retornar nenhum arquivo. Revise os arquivos preparados antes de continuar:

```powershell
git commit -m "Prepara FarmaControl para versionamento"
git remote add origin https://github.com/SEU_USUARIO/FarmaControl.git
git push -u origin main
```

Se o Git solicitar identidade, configure `user.name` e `user.email` conforme sua conta antes do commit. Autentique-se pelo mecanismo oferecido pelo Git/GitHub; não coloque tokens na URL salva do repositório.

## Atualizações posteriores

```powershell
git status --short
git diff
git add README.md docs backend frontend tests scripts
git diff --cached
git commit -m "Descreve a mudança realizada"
git push
```

Adapte a lista de caminhos aos arquivos modificados. Para trabalho em equipe, use uma branch e um pull request, descrevendo comportamento, validação e eventuais migrações necessárias.

## Arquivo privado já rastreado

O `.gitignore` não remove arquivos que já entraram no histórico. Se o `.env` aparecer em `git ls-files`, retire-o do índice preservando a cópia local:

```powershell
git rm --cached -- backend/.env
```

Revise e registre essa alteração. Se credenciais reais já foram publicadas, removê-las do arquivo atual não elimina versões antigas: substitua as credenciais expostas e trate o histórico separadamente.

## Copiar para outra máquina

```powershell
git clone https://github.com/SEU_USUARIO/FarmaControl.git
cd FarmaControl
```

Siga o [README](../README.md) para criar o ambiente e o [guia de transferência](TRANSFERENCIA.md) se houver dados a restaurar. O clone não inclui `.env`, dependências instaladas ou banco de dados.

## Estado do repositório

O repositório é [SamuelDlv/FarmaControl](https://github.com/SamuelDlv/FarmaControl), com branch principal `main`. Em 23/10/2026, as correções de logout e limite de autenticação foram publicadas pelo conector GitHub. Esse envio não cria uma pasta `.git` nem configura um remoto no diretório local; os comandos de Git deste guia exigem um clone ou repositório local inicializado.

Arquivos locais de `.audit-backup` e ambientes virtuais permanecem fora do versionamento. Publicar uma atualização no GitHub não reinicia o servidor local: depois de atualizar o código, reinicie o backend para carregar mudanças Python.
