# FarmaControl — Autenticação

Esta pasta reúne a tela e a integração da autenticação do FarmaControl. O fluxo atual trabalha com cadastro pendente, aprovação administrativa e login conforme o perfil liberado.

## Estrutura

```text
auth/
├── auth.html
├── auth.css
├── auth.js
└── README.md
```

A comunicação com o backend é feita pela API Flask. O endereço da API é configurado no JavaScript conforme o ambiente local.

## Fluxo do cadastro

```text
Usuário envia o cadastro
        ↓
Conta fica pendente
        ↓
Administrador analisa o cadastro
        ↓
Cadastro aprovado ou rejeitado
        ↓
Usuário aprovado pode entrar
        ↓
Acesso conforme o perfil
```

## Segurança

O backend utiliza hash bcrypt para as senhas, CORS configurável e registro das tentativas de acesso. Contas pendentes ou rejeitadas não podem autenticar.

As configurações sensíveis devem ficar em `.env` e nunca devem ser enviadas para o repositório.

## Autor

Módulo desenvolvido e mantido por **SamuelDlv** como parte do FarmaControl.

GitHub: https://github.com/SamuelDlv
