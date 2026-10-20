-- Preserva o histórico existente e permite detalhar todos os itens de uma operação.
ALTER TABLE log_atividades MODIFY COLUMN detalhes MEDIUMTEXT NOT NULL;
