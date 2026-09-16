# FarmaControl

Sistema de controle de estoque para farmácias, desenvolvido por mim como Projeto Integrador no curso de Engenharia da Computação.

> **Status:** Em desenvolvimento

## Sobre o projeto

O FarmaControl busca centralizar o gerenciamento de estoque de farmácias, acompanhando produtos, lotes, validade, movimentações, compras e usuários.

O projeto integra conhecimentos de **Engenharia de Software**, **Banco de Dados**, desenvolvimento web e segurança de aplicações. Também estou desenvolvendo um módulo de **previsão de demanda** a partir do histórico de movimentações.

## Principais funcionalidades

- Cadastro e gerenciamento de medicamentos e produtos
- Controle de entradas e saídas de estoque
- Rastreabilidade por lote e data de vencimento
- Acompanhamento de saldos de estoque
- Alertas para estoque mínimo e produtos próximos do vencimento
- Registro e acompanhamento de compras e fornecedores
- Relatórios de movimentação e consolidados
- Controle de usuários e níveis de acesso
- Previsão de demanda

## Tecnologias e desenvolvimento

### Backend

- Python 3
- Flask 3
- MySQL/MariaDB
- PyMySQL
- Flask-CORS
- python-dotenv
- bcrypt
- API REST

### Frontend

- HTML
- CSS
- JavaScript

O backend possui módulos para autenticação, usuários, produtos, estoque, dispensação, compras, vencimentos, relatórios e previsão. A documentação específica da API fica em `backend/README.md`.

## Estrutura

```text
FarmaControl/
│
├── frontend/              # Interface web
├── backend/               # API e regras de negócio
│   ├── app.py
│   ├── schema.sql
│   ├── migrations/
│   ├── requirements.txt
│   └── .env.example
│
└── docs/                  # Documentação técnica
```

## Requisitos

- Python 3.10+
- MySQL 8+ ou MariaDB compatível
- `pip`
- Navegador moderno

## Instalação

Clone o repositório:

```bash
git clone https://github.com/SamuelDlv/FarmaControl.git
cd FarmaControl
```

Entre no backend e crie um ambiente virtual:

```bash
cd backend
python -m venv .venv
```

Ative o ambiente virtual e instale as dependências:

```bash
pip install -r requirements.txt
```

Crie o banco usando o schema:

```bash
mysql -u root -p < schema.sql
```

Depois crie o `.env` a partir de `.env.example` e configure as credenciais do banco e a chave secreta.

Exemplo:

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

Inicie a aplicação:

```bash
python app.py
```

Para detalhes dos módulos da API e das configurações disponíveis, consulte `backend/README.md`.

## Desenvolvimento

O projeto encontra-se em desenvolvimento. As decisões de arquitetura podem ser ajustadas conforme novas funcionalidades forem implementadas e testadas.

A pasta `docs/` mantém a documentação técnica do projeto, enquanto os READMEs do frontend e backend explicam suas respectivas partes da aplicação.

## Segurança

As credenciais e outras informações sensíveis devem ficar somente no `.env`. O repositório mantém `.env.example` como modelo e utiliza `.gitignore` para evitar o versionamento das configurações locais.

O backend utiliza `bcrypt` para senhas e autenticação baseada em tokens. Antes de qualquer implantação pública, ainda é necessário revisar HTTPS, CORS, permissões, proteção contra abuso e demais controles de segurança.

## Autor

Projeto desenvolvido e mantido por **SamuelDlv**.

GitHub: https://github.com/SamuelDlv
