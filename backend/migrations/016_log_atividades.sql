-- Historico preservado mesmo apos exclusao do usuario (identidade por snapshot).
CREATE TABLE IF NOT EXISTS log_atividades (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NULL,
    usuario_nome VARCHAR(255) NOT NULL,
    perfil VARCHAR(40) NOT NULL,
    acao VARCHAR(255) NOT NULL,
    detalhes VARCHAR(1000) NOT NULL,
    status_http SMALLINT UNSIGNED NOT NULL,
    criado_em DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    INDEX idx_log_usuario (usuario_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
