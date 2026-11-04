-- Aplicar uma vez antes de iniciar a API atualizada.
-- NULL preserva a finalidade desconhecida dos registros anteriores.
-- Não inferir descarte a partir de observações livres.
ALTER TABLE movimentacoes_estoque
  ADD COLUMN finalidade ENUM('descarte', 'venda', 'devolucao_fornecedor') NULL,
  ADD COLUMN motivo VARCHAR(255) NULL;
