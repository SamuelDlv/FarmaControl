# FarmaControl — Módulo de Autenticação

Sistema de login/cadastro com **ambiente controlado**: novos cadastros ficam em status
`pendente` até serem aprovados manualmente por um administrador.

---

## Estrutura de arquivos

```
auth_project/
├── auth.html              ← Frontend (não modificado)
├── auth.css               ← Estilos (não modificado)
├── auth.js                ← Frontend atualizado (conecta na API)
└── backend/
    ├── app.py             ← Servidor Flask (API REST)
    ├── schema.sql         ← Schema MySQL completo
    ├── requirements.txt   ← Dependências Python
    └── .env.example       ← Template de configuração
```

---

## 1. Banco de dados (MySQL)

```sql
-- Crie o banco e execute o schema:
mysql -u root -p < backend/schema.sql
```

**Tabelas criadas:**
| Tabela | Descrição |
|---|---|
| `perfis` | Perfis de acesso (farmacêutico, admin, atendente…) |
| `usuarios` | Usuários com status `pendente / aprovado / rejeitado` |
| `analises_cadastro` | Log de cada aprovação/rejeição |
| `log_acessos` | Auditoria de todas as tentativas de login |

---

## 2. Backend Python (Flask)

### Instalação

```bash
cd backend
pip install -r requirements.txt
```

### Configuração

```bash
cp .env.example .env
# Edite o .env com suas credenciais do banco e chave secreta
```

### Rodar o servidor

```bash
python app.py
# Servidor sobe em http://localhost:5000
```

---

## 3. Frontend

Abra `auth.html` num servidor local (ex: Live Server do VS Code, ou):

```bash
python -m http.server 5500
# Acesse http://localhost:5500/auth.html
```

> A `API_BASE` no topo de `auth.js` aponta para `http://localhost:5000`.
> Ajuste se o backend rodar em outro endereço.

---

## 4. Fluxo do cadastro

```
Usuário preenche o formulário
        ↓
POST /auth/register
        ↓
Conta criada com status = "pendente"
        ↓
Administrador consulta GET /admin/pendentes
        ↓
POST /admin/analisar/{id}  { "decisao": "aprovado" }
        ↓
Usuário consegue fazer login (POST /auth/login)
        ↓
Redirecionamento para o dashboard do perfil
```

---

## 5. Rotas da API

### `POST /auth/register`
```json
// Body
{ "nome": "Usuario", "sobrenome": "Exemplo", "email": "usuario@exemplo.com",
  "role": "atendente", "password": "<senha-de-exemplo>" }

// Resposta 201
{ "ok": true, "mensagem": "Cadastro realizado! Aguardando análise…" }
```

### `POST /auth/login`
```json
// Body
{ "email": "usuario@exemplo.com", "password": "<senha-de-exemplo>" }

// Resposta 200 (aprovado)
{ "ok": true, "mensagem": "Bem-vindo, Ana!", "usuario": { "id": 1, "perfil": "atendente", … } }

// Resposta 403 (pendente)
{ "ok": false, "mensagem": "Seu cadastro ainda está sendo analisado…" }
```

### `GET /admin/pendentes`
```json
// Resposta 200
{ "ok": true, "total": 2, "pendentes": [ { "id": 1, "nome": "Ana", … } ] }
```

### `POST /admin/analisar/{id}`
```json
// Body
{ "decisao": "aprovado", "motivo": null }
// ou
{ "decisao": "rejeitado", "motivo": "Funcionário não encontrado no sistema." }
```

---

## 6. Segurança implementada

- **Senhas:** hash bcrypt (12 rounds) — nunca armazenadas em texto plano
- **CORS:** apenas origens definidas em `ALLOWED_ORIGINS` no `.env`
- **Mensagens genéricas:** login inválido retorna "E-mail ou senha incorretos" (não revela qual campo errou)
- **Log de acessos:** todas as tentativas (sucesso/falha) são registradas com IP e User-Agent
- **Status controlado:** usuários `pendente` e `rejeitado` não conseguem autenticar

---

## Perfis disponíveis

| Slug | Nome | Acesso |
|---|---|---|
| `farmaceutico` | Farmacêutico / Proprietário | Estoque, alertas, aprovações |
| `admin` | Gerente | Acesso total |
| `atendente` | Atendente / Balconista | Consulta e dispensação |
| `compras` | Responsável por Compras | Pedidos e fornecedores |
| `ti` | TI / Suporte | Configurações técnicas |
