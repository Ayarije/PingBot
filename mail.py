import discord
from discord.ext import tasks
import imaplib
import email
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


# ==========================================
# TÂCHE ASYNCRONE
# ==========================================
@tasks.loop(minutes=CONFIG["email"]["check_interval_minutes"])
async def check_emails():
    try:
        mail = imaplib.IMAP4_SSL(CONFIG["email"]["imap_server"], CONFIG["email"]["port"])
        mail.login(CONFIG["email"]["email"], CONFIG["email"]["password"])
        mail.select(CONFIG["email"]["folder"])

        status, messages = mail.search(None, 'UNSEEN')
        if status != 'OK':
            return

        for num in messages[0].split():
            status, msg_data = mail.fetch(num, '(RFC822)')
            if status != 'OK': continue

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
                    
                    # Extraction du corps et troncature sécurisée pour Discord (limite de 4096)
                    body = get_email_body(msg)
                    if len(body) > 4000:
                        body = body[:4000] + "\n\n*[... Message tronqué car trop long ...]*"

                    for rule in CONFIG["email"]["rules"]:
                        if check_conditions(mail_info, rule["conditions"]):
                            channel = BOT.get_channel(rule["channel_id"])
                            if channel:
                                # Construction des mentions
                                subs = rule.get("subscribers", [])
                                mentions_str = " ".join([f"<@{uid}>" for uid in subs])
                                content = f"|| {mentions_str} ||" if subs else ""
                                
                                # Construction de l'Embed
                                embed = discord.Embed(
                                    title=f"{sender}: {subject}",
                                    description=body if body else "*(Aucun contenu texte)*",
                                    color=discord.Color.blue()
                                )
                                
                                # Ajout du bouton
                                view = NotificationView("email", rule.get("id"))
                                await channel.send(content=content, embed=embed, view=view)
                                
        mail.logout()
    except Exception as e:
        print(f"Erreur IMAP : {e}")