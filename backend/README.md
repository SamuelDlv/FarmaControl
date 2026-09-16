# Backend — FarmaControl

Esta pasta concentra a API REST do FarmaControl e as regras de negócio do sistema. O backend foi desenvolvido em Flask, com MySQL/MariaDB e autenticação baseada em JWT.

## Estrutura

```text
backend/
├── app.py
├── schema.sql
├── migrations/
├── requirements.txt
├── .env.example
└── README.md
```

## Módulos da API

| Módulo | Rota base | Descrição |
|---|---|---|
| Auth | `/api/auth` | Login, logout e refresh token |
| Usuários | `/api/usuarios` | Usuários e perfis |
| Produtos | `/api/produtos` | Medicamentos e produtos |
| Estoque | `/api/estoque` | Movimentações e saldos |
| Dispensação | `/api/dispensacao` | Registro de saídas |
| Compras | `/api/compras` | Pedidos e fornecedores |
| Vencimentos | `/api/vencimentos` | Lotes e alertas |
| Relatórios | `/api/relatorios` | Relatórios e consolidados |
| Previsão | `/api/previsao` | Previsão de demanda |

## Perfis

O acesso é separado por perfil para evitar que todos os usuários tenham as mesmas permissões. Os perfis utilizados atualmente incluem proprietário, gerente, compras, atendente e TI.

## Configuração

Crie um `.env` a partir de `.env.example` e preencha as configurações do banco e da chave secreta:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=farmacontrol
DB_USER=
DB_PASSWORD=
SECRET_KEY=
FLASK_DEBUG=false
```

O `.env` é local e não deve ser versionado.

## Autor

Backend desenvolvido e mantido por **SamuelDlv**.

GitHub: https://github.com/SamuelDlv

Para uma visão geral do projeto, consulte o README da raiz do FarmaControl.
