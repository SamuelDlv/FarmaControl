# FarmaControl

Sistema de controle de estoque para farmácias, desenvolvido como Projeto Integrador no curso de Engenharia da Computação.

> **Status:** Em desenvolvimento

## Sobre o projeto

O FarmaControl tem como objetivo desenvolver uma solução para auxiliar farmácias de pequeno e médio porte na gestão de seus estoques, centralizando informações e reduzindo problemas como falta de medicamentos, excesso de produtos, vencimentos e dificuldades no acompanhamento das movimentações.

O projeto integra conhecimentos das disciplinas de **Engenharia de Software** e **Banco de Dados**, abrangendo levantamento e especificação de requisitos, modelagem de dados, desenvolvimento do sistema, testes e versionamento.

Um dos principais diferenciais previstos é a utilização de **Inteligência Artificial para previsão de demanda**, utilizando o histórico de movimentações para auxiliar na identificação das necessidades de reposição e na tomada de decisões relacionadas ao estoque.

## Principais funcionalidades previstas

- Cadastro e gerenciamento de medicamentos e produtos;
- Controle de entradas e saídas de estoque;
- Rastreabilidade por lote e data de vencimento;
- Acompanhamento do estoque em tempo real;
- Alertas para estoque mínimo e produtos próximos do vencimento;
- Registro e acompanhamento de pedidos a fornecedores;
- Relatórios de movimentação e análise de estoque;
- Previsão de demanda utilizando Inteligência Artificial;
- Sugestões de reposição baseadas no estoque e na demanda prevista;
- Controle de usuários e níveis de acesso.

## Tecnologias e desenvolvimento

A documentação do projeto prevê uma arquitetura baseada em API REST, com possibilidade de utilização de **Node.js ou Python** no backend, interface web responsiva no frontend e **PostgreSQL ou MySQL** como banco de dados. O módulo de previsão de demanda poderá utilizar Python e bibliotecas voltadas à análise e modelagem de séries temporais.

As tecnologias e decisões de implementação podem ser ajustadas conforme o desenvolvimento do projeto.

## Estrutura

```text
FarmaControl/
│
├── frontend/
│   ├── pages/
│   ├── components/
│   └── assets/
│
├── backend/
│   ├── routes/
│   ├── controllers/
│   ├── middlewares/
│   └── database/
│
└── docs/
```

## Desenvolvimento

O projeto encontra-se atualmente em desenvolvimento. A implementação seguirá as etapas definidas no Projeto Integrador, passando pela modelagem, implementação, integração do módulo de Inteligência Artificial, testes e documentação técnica.
