# FarmaControl

Sistema de gestão de farmácia — Projeto de Faculdade

## Estrutura

```
FarmaControl/
│
├── frontend/
│   ├── pages/
│   │   ├── auth/          # Login
│   │   ├── dashboard/     # Visão geral (página atual)
│   │   ├── estoque/       # Controle de medicamentos
│   │   ├── dispensacao/   # Registro de saídas
│   │   └── relatorios/    # Relatórios
│   │
│   ├── components/        # Partes reutilizáveis (sidebar, topbar)
│   └── assets/
│       ├── css/           # Estilos globais
│       ├── js/            # Scripts globais
│       └── images/        # Imagens e ícones
│
├── backend/
│   ├── routes/            # Rotas da API
│   ├── controllers/       # Lógica de cada rota
│   ├── middlewares/       # Autenticação e permissões
│   └── database/          # Conexão e queries do banco
│
└── docs/                  # Documentação do projeto
```

## Como rodar

```bash
# Backend
cd backend
npm install
node server.js

# Frontend
# Abrir frontend/pages/dashboard/index.html no navegador
```
