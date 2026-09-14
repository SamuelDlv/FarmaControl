# Backend — FarmaControl

API REST do sistema, com autenticação JWT, controle de acesso por perfil (RBAC) e integração com banco MySQL/MariaDB via PyMySQL.

## Estrutura

```
backend/
├── app.py                 # API Flask e regras de negócio
├── schema.sql             # Schema principal do banco
├── migrations/            # Migrações SQL incrementais
├── requirements.txt       # Dependências Python
├── .env.example           # Template de variáveis de ambiente
└── README.md              # Documentação do backend
```

## Módulos da API

| Módulo         | Rota base           | Descrição                          |
|----------------|---------------------|------------------------------------|
| Auth           | `/api/auth`         | Login, logout, refresh token       |
| Usuários       | `/api/usuarios`     | CRUD de usuários e perfis          |
| Produtos       | `/api/produtos`     | Cadastro e consulta de medicamentos|
| Estoque        | `/api/estoque`      | Movimentações e saldos             |
| Dispensação    | `/api/dispensacao`  | Registro de saídas                 |
| Compras        | `/api/compras`      | Pedidos e fornecedores             |
| Vencimentos    | `/api/vencimentos`  | Alertas de lotes a vencer          |
| Relatórios     | `/api/relatorios`   | Exportação e consolidados          |
| IA / Previsão  | `/api/previsao`     | Previsão de demanda                |

## Perfis RBAC

```
PROPRIETARIO  → acesso total
GERENTE       → sem configurações técnicas
COMPRAS       → estoque, compras, fornecedores
ATENDENTE     → consulta e dispensação
TI            → configurações, logs, usuários
```

## Variáveis de ambiente

Configure as variáveis no arquivo `.env` (que não deve ser versionado):

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=farmacontrol
DB_USER=
DB_PASSWORD=
SECRET_KEY=
FLASK_DEBUG=false
```

