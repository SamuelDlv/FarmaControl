# Guia de manutenção — Processa resumos por e-mail em thread separada com exclusão no MySQL.
# Consulte docs/DESENVOLVIMENTO.md para executar as verificações desta camada.
"""Resumos automáticos, avaliados durante o uso do sistema, sem bloquear a tela."""
import html
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from farmacontrol.services.system_settings import read_settings, active_alerts

_lock = threading.Lock()
_next_check = 0


# Seleciona os resumos ainda não enviados no dia/semana do fuso configurado.
# O chamador controla a transação; o marcador só muda após sucesso do envio.
def send_due(cursor, send_email, now=None):
    settings = read_settings(cursor)
    recipient = settings.get('email_notificacao')
    if not recipient:
        return
    offset = -4 if settings['fuso_horario'] == 'America/Manaus' else -3
    now = now or datetime.now(timezone(timedelta(hours=offset)))
    day = now.date().isoformat()
    jobs = []
    if settings['notificacoes_email'] == 'true' and settings.get('notificacao.ultimo_dia') != day:
        alerts = active_alerts(cursor, settings)
        body = ''.join('<li>' + html.escape(a['titulo'] + ': ' + a['mensagem']) + '</li>' for a in alerts)
        jobs.append(('notificacao.ultimo_dia', day, 'Resumo diário de alertas',
                     '<ul>' + body + '</ul>' if body else '<p>Nenhum alerta ativo.</p>'))
    week = now.strftime('%G-%V')
    if settings['relatorio_semanal'] == 'true' and now.weekday() == 0 and settings.get('notificacao.ultima_semana') != week:
        cursor.execute('''SELECT tipo_movimentacao, SUM(quantidade) AS quantidade
            FROM movimentacoes_estoque WHERE data_movimentacao >= NOW() - INTERVAL 7 DAY
            GROUP BY tipo_movimentacao''')
        rows = cursor.fetchall()
        body = ''.join('<li>' + html.escape(str(r['tipo_movimentacao'])) + ': ' +
                       html.escape(str(r['quantidade'])) + '</li>' for r in rows)
        jobs.append(('notificacao.ultima_semana', week, 'Relatório semanal de movimentações',
                     '<ul>' + body + '</ul>' if body else '<p>Sem movimentações nos últimos sete dias.</p>'))
    for key, marker, subject, body in jobs:
        pharmacy = html.escape(settings.get('nome_farmacia') or 'FarmaControl')
        # Não registrar sucesso quando o transporte falha: o próximo ciclo deve
        # poder tentar novamente. SMTP e MySQL não formam uma transação distribuída;
        # uma falha no commit após envio ainda pode resultar em e-mail repetido.
        if send_email(recipient, subject, '<h2>' + pharmacy + '</h2>' + body):
            cursor.execute('''INSERT INTO configuracoes_sistema (chave, valor)
                VALUES (%s, %s) ON DUPLICATE KEY UPDATE valor=VALUES(valor)''', (key, marker))


# Limita a avaliação a uma vez por minuto neste processo e delega o envio à thread.
def schedule(app, get_db, send_email):
    global _next_check
    with _lock:
        if time.monotonic() < _next_check:
            return
        _next_check = time.monotonic() + 60

    # A thread abre seu próprio contexto e conexão; g do pedido não é compartilhado.
    def run():
        with app.app_context():
            db = get_db()
            acquired = False
            try:
                with db.cursor() as cursor:
                    # O lock Python só protege este processo. O lock MySQL impede
                    # que workers da mesma instância do banco enviem simultaneamente.
                    cursor.execute("SELECT GET_LOCK('farmacontrol_notificacoes', 0) AS acquired")
                    acquired = bool(cursor.fetchone()['acquired'])
                    if acquired:
                        send_due(cursor, send_email)
                        db.commit()
            except Exception:
                # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
                db.rollback()
                logging.getLogger('farmacontrol').exception('Falha ao processar resumos automáticos')
            finally:
                if acquired:
                    with db.cursor() as cursor:
                        cursor.execute("SELECT RELEASE_LOCK('farmacontrol_notificacoes')")

    threading.Thread(target=run, name='farmacontrol-notificacoes', daemon=True).start()
