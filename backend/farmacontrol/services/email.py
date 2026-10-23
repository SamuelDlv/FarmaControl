"""services.email: responsabilidades extraídas da aplicação Flask."""

from email.message import EmailMessage
from email.utils import formataddr
import html
import logging
import os
import re
import smtplib
import ssl

log = logging.getLogger("farmacontrol")


def montar_email_html(titulo, conteudo_html, acao_principal=None, acao_secundaria=None):
    """Monta o visual padrão dos e-mails transacionais do FarmaControl."""
    botoes = ""
    if acao_principal:
        texto, url = acao_principal
        botoes += (
            '<p style="margin:28px 0 18px;text-align:center;">'
            f'<a href="{html.escape(url, quote=True)}" '
            'style="display:inline-block;background:#166534;border-radius:8px;color:#ffffff;'
            'font-size:16px;font-weight:700;line-height:20px;padding:14px 24px;text-align:center;'
            'text-decoration:none;">'
            f'{html.escape(texto)}</a></p>'
        )
    if acao_secundaria:
        texto, url = acao_secundaria
        botoes += (
            '<p style="margin:0 0 8px;text-align:center;">'
            f'<a href="{html.escape(url, quote=True)}" '
            'style="color:#4b5563;font-size:14px;text-decoration:underline;">'
            f'{html.escape(texto)}</a></p>'
        )
    # Os convites legados já trazem seus links no conteúdo. Converte-os em
    # CTAs visuais para que continuem bonitos sem duplicar ou alterar URLs.
    contador_links = 0

    def estilizar_link(match):
        nonlocal contador_links
        contador_links += 1
        href, texto = match.groups()
        if contador_links == 1:
            estilo = (
                "display:inline-block;background:#166534;border:1px solid #166534;"
                "border-radius:8px;color:#ffffff;font-size:15px;font-weight:700;"
                "padding:12px 18px;text-decoration:none;"
            )
        else:
            estilo = (
                "display:inline-block;background:#ffffff;border:1px solid #9ca3af;"
                "border-radius:8px;color:#374151;font-size:15px;font-weight:700;"
                "padding:12px 18px;text-decoration:none;"
            )
        return f'<a href="{href}" style="{estilo}">{texto}</a>'

    conteudo_html = re.sub(
        r'<a href="([^"]+)">(.+?)</a>', estilizar_link, conteudo_html,
    ).replace("&nbsp;|&nbsp;", "&nbsp;")
    return f"""<!doctype html>
<html lang="pt-BR">
<body style="margin:0;padding:0;background:#f3f7f4;color:#1f2937;font-family:Arial,Helvetica,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{html.escape(titulo)}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3f7f4;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#ffffff;border-radius:14px;overflow:hidden;">
        <tr><td style="background:#14532d;padding:24px 32px;color:#ffffff;font-size:23px;font-weight:700;letter-spacing:-0.4px;">FarmaControl</td></tr>
        <tr><td style="padding:34px 32px 28px;">
          <h1 style="margin:0 0 18px;color:#173321;font-size:25px;line-height:32px;">{html.escape(titulo)}</h1>
          <div style="color:#374151;font-size:16px;line-height:25px;">{conteudo_html}</div>
          {botoes}
        </td></tr>
        <tr><td style="border-top:1px solid #e5e7eb;padding:20px 32px;color:#6b7280;font-size:12px;line-height:18px;">
          Esta é uma mensagem automática do FarmaControl. Caso não reconheça esta solicitação, entre em contato com a equipe responsável.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def enviar_email_brevo(destinatario, assunto, conteudo_html):
    """Envia e-mail transacional sem deixar indisponível o fluxo principal.

    A configuração vem exclusivamente do ambiente. Falhas no provedor são
    registradas sem incluir chave, destinatário ou conteúdo sensível nos logs.
    """
    host = os.getenv("BREVO_SMTP_HOST", "smtp-relay.brevo.com")
    porta = os.getenv("BREVO_SMTP_PORT", "587")
    login = os.getenv("BREVO_SMTP_LOGIN")
    senha = os.getenv("BREVO_SMTP_PASSWORD")
    remetente = os.getenv("BREVO_SENDER_EMAIL")
    nome_remetente = os.getenv("BREVO_SENDER_NAME", "FarmaControl")
    if not login or not senha or not remetente:
        log.info("E-mail transacional não enviado: SMTP da Brevo não configurado.")
        return False
    conteudo_html = montar_email_html(assunto, conteudo_html)
    try:
        mensagem = EmailMessage()
        mensagem["From"] = formataddr((nome_remetente, remetente))
        mensagem["To"] = destinatario
        mensagem["Subject"] = assunto
        mensagem.set_content("Abra este e-mail em um cliente compatível com HTML.")
        mensagem.add_alternative(conteudo_html, subtype="html")
        with smtplib.SMTP(host, int(porta), timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(login, senha)
            smtp.send_message(mensagem)
        return True
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        log.warning("Não foi possível enviar e-mail transacional pela Brevo: %s", exc)
    return False

