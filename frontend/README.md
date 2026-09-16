# Frontend — FarmaControl

Esta pasta contém a interface web do FarmaControl. Organizei o frontend por páginas, componentes e serviços para separar a apresentação das chamadas à API.

## Estrutura

```text
frontend/
├── public/
│   ├── icons/
│   └── fonts/
└── src/
    ├── assets/
    ├── styles/
    ├── layouts/
    ├── components/
    │   ├── ui/
    │   └── shared/
    ├── pages/
    │   ├── auth/
    │   ├── dashboard/
    │   ├── estoque/
    │   ├── dispensacao/
    │   ├── compras/
    │   ├── vencimentos/
    │   ├── relatorios/
    │   ├── usuarios/
    │   └── configuracoes/
    ├── services/
    ├── hooks/
    ├── utils/
    ├── contexts/
    ├── constants/
    └── types/
```

## Organização

- Cada página mantém seus arquivos de interface e comportamento próximos.
- Componentes reutilizáveis ficam em `components/`.
- As chamadas para a API ficam concentradas em `services/`.
- A lógica específica da aplicação não deve ficar misturada com a apresentação das páginas.

A estrutura ainda está em evolução conforme o frontend ganha novas telas.

## Autor

Frontend desenvolvido e mantido por **SamuelDlv**.

GitHub: https://github.com/SamuelDlv

Para entender o projeto como um todo, consulte o README da raiz do FarmaControl.
