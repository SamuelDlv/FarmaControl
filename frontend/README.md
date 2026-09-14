# Frontend — FarmaControl

Interface web do sistema, organizada por páginas e componentes reutilizáveis.

## Estrutura

```
frontend/
├── public/
│   ├── icons/           # Favicons e ícones PWA
│   └── fonts/           # Fontes locais (fallback)
│
└── src/
    ├── assets/
    │   ├── images/      # Logos, ilustrações
    │   ├── icons/       # SVGs de ícones
    │   └── fonts/       # Arquivos de fonte
    │
    ├── styles/          # CSS global, variáveis, reset, tipografia
    ├── layouts/         # Shells de layout (sidebar, topbar, painel)
    │
    ├── components/
    │   ├── ui/          # Botões, badges, pills, toasts, inputs
    │   └── shared/      # KPI cards, tabelas, gráficos, alertas
    │
    ├── pages/
    │   ├── auth/        # Login, recuperação de senha
    │   ├── dashboard/   # Visão geral (atual)
    │   ├── estoque/     # Lista e detalhe de produtos
    │   ├── dispensacao/ # Registro de saídas
    │   ├── compras/     # Pedidos e fornecedores
    │   ├── vencimentos/ # Controle de lotes
    │   ├── relatorios/  # Relatórios e exportações
    │   ├── usuarios/    # Gestão de usuários e perfis
    │   └── configuracoes/ # Configurações do sistema
    │
    ├── services/        # Chamadas à API (fetch/axios)
    ├── hooks/           # Lógica reutilizável (auth, permissões)
    ├── utils/           # Formatadores, helpers, máscaras
    ├── contexts/        # Estado global (auth, tema, perfil)
    ├── constants/       # Enums, perfis, rotas, configurações fixas
    └── types/           # Tipagens e interfaces (JSDoc)
```

## Convenções

- Cada página tem seu próprio `.html`, `.css` e `.js`
- Componentes reutilizáveis ficam em `components/`
- Chamadas à API ficam **somente** em `services/`
- Nenhuma lógica de negócio dentro dos arquivos de página
