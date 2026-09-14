-- Migração 002 — 2026-08-12
-- Correção: a query da rota GET /compras referenciava a coluna inexistente
-- `f.nome` na tabela `fornecedores`. A coluna correta é `nome_fantasia`
-- (conforme schema.sql, linha 111). Esta migração documenta a mudança;
-- a correção do código está em backend/app.py (rota GET /compras).
-- Nenhuma alteração de estrutura de dados é necessária.

SELECT 'Migração 002 aplicada: query GET /compras corrigida para usar f.nome_fantasia.' AS status;
