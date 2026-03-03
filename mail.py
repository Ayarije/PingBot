import discord
from discord.ext import tasks
import imaplib
import email
import asyncio
from email.header import decode_header

from globals import CONFIG, BOT
from components import NotificationView

# ==========================================
# FONCTIONS UTILITAIRES MAIL
# ==========================================
def decode_mime_words(s):
    """Décode les en-têtes d'e-mails (sujet, expéditeur) proprement."""
    if not s:
        return ""
    decoded_words = decode_header(s)
    result = ""
    for word, charset in decoded_words:
        if isinstance(word, bytes):
            try:
                result += word.decode(charset or 'utf-8')
            except LookupError:
                result += word.decode('utf-8', errors='ignore')
        else:
            result += word
    return result

def check_conditions(mail_data, rule_conditions):
    """Vérifie si un e-mail satisfait les conditions d'une règle."""
    case_sensitive = rule_conditions.get("case_sensitive", False)
    
    # Extraction des données du mail
    sender = mail_data.get("sender", "")
    recipient = mail_data.get("recipient", "")
    subject = mail_data.get("subject", "")
    
    if not case_sensitive:
        sender = sender.lower()
        recipient = recipient.lower()
        subject = subject.lower()
    
    # Vérification Sender
    if "sender" in rule_conditions:
        rule_sender = rule_conditions["sender"] if case_sensitive else rule_conditions["sender"].lower()
        if rule_sender not in sender:
            return False
            
    # Vérification Recipient
    if "recipient" in rule_conditions:
        rule_recip = rule_conditions["recipient"] if case_sensitive else rule_conditions["recipient"].lower()
        if rule_recip not in recipient:
            return False
            
    # Vérification Subject
    if "subject_contains" in rule_conditions:
        rule_subj = rule_conditions["subject_contains"] if case_sensitive else rule_conditions["subject_contains"].lower()
        if rule_subj not in subject:
            return False

    return True

def get_email_body(msg):
    """Extrait le texte brut d'un e-mail avec une gestion rigoureuse de l'encodage."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            # On cherche uniquement le texte brut, pas le HTML ou les pièces jointes
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
                charset = part.get_content_charset() or 'utf-8'
                try:
                    body = part.get_payload(decode=True).decode(charset, errors='replace')
                    break
                except Exception:
                    continue
    else:
        charset = msg.get_content_charset() or 'utf-8'
        try:
            body = msg.get_payload(decode=True).decode(charset, errors='replace')
        except Exception:
            pass
            
    return body.strip()

def fetch_emails_sync():
    """Fonction SÉPARÉE ET BLOQUANTE qui gère le réseau de manière isolée."""
    cfg = CONFIG["email"]
    # Sécurité : on annule si la configuration est vide
    if not cfg.get("imap_server") or not cfg.get("email") or not cfg.get("password"):
        return []

    try:
        # Cette ligne peut prendre du temps si le réseau bloque, mais elle ne gênera plus le bot
        mail = imaplib.IMAP4_SSL(cfg["imap_server"], int(cfg["port"]))
        mail.login(cfg["email"], cfg["password"])
        mail.select(cfg["folder"])

        status, messages = mail.search(None, 'UNSEEN')
        if status != 'OK':
            mail.logout()
            return []

        emails_data = []
        for num in messages[0].split():
            status, msg_data = mail.fetch(num, '(RFC822)')
            if status == 'OK':
                emails_data.append(msg_data)

        mail.logout()
        return emails_data
    except Exception as e:
        print(f"Erreur réseau IMAP (Thread) : {e}")
        return []
    
def check_imap_connection_sync():
    """Vérifie rapidement si la connexion IMAP est fonctionnelle pour la commande /status."""
    cfg = CONFIG["email"]
    if not cfg.get("imap_server") or not cfg.get("email") or not cfg.get("password"):
        return False, "Non configuré dans le panel"

    try:
        mail = imaplib.IMAP4_SSL(cfg["imap_server"], int(cfg["port"]))
        mail.login(cfg["email"], cfg["password"])
        mail.logout()
        return True, "En ligne et authentifié"
    except Exception as e:
        return False, f"Erreur : {e}"


# ==========================================
# TÂCHE ASYNCRONE
# ==========================================
@tasks.loop(minutes=CONFIG["email"]["check_interval_minutes"])
async def check_emails():
    """Tâche principale asynchrone qui appelle le thread réseau."""
    # L'APPEL MAGIQUE : On délègue la tâche bloquante à un thread et on attend le résultat sans bloquer Discord !
    messages_data = await asyncio.to_thread(fetch_emails_sync)
    
    if not messages_data:
        return

    for msg_data in messages_data:
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                subject = decode_mime_words(msg.get("Subject", ""))
                sender = decode_mime_words(msg.get("From", ""))
                recipient = decode_mime_words(msg.get("To", ""))
                
                mail_info = {
                    "subject": subject,
                    "sender": sender,
                    "recipient": recipient
                }
                
                body = get_email_body(msg)
                if len(body) > 4000:
                    body = body[:4000] + "\n\n*[... Message tronqué car trop long ...]*"

                for rule in CONFIG["email"]["rules"]:
                    if check_conditions(mail_info, rule["conditions"]):
                        channel = BOT.get_channel(rule["channel_id"])
                        assert isinstance(channel, discord.TextChannel)
                        if channel:
                            subs = rule.get("subscribers", [])
                            mentions_str = " ".join([f"<@{uid}>" for uid in subs])
                            content = f"|| {mentions_str} ||" if subs else ""
                            
                            embed = discord.Embed(
                                title=f"{sender}: {subject}",
                                description=body if body else "*(Aucun contenu texte)*",
                                color=discord.Color.blue()
                            )
                            
                            view = NotificationView("email", rule.get("id"))
                            await channel.send(content=content, embed=embed, view=view)