import discord
from discord.ext import tasks
import imaplib
import email
from email.header import decode_header

from globals import CONFIG, BOT

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


# ==========================================
# TÂCHE ASYNCRONE
# ==========================================
@tasks.loop(minutes=CONFIG["email"]["check_interval_minutes"])
async def check_emails():
    """Se connecte à l'IMAP, récupère les e-mails non lus, et les trie selon les règles."""
    try:
        mail = imaplib.IMAP4_SSL(CONFIG["email"]["imap_server"], CONFIG["email"]["port"])
        mail.login(CONFIG["email"]["email"], CONFIG["email"]["password"])
        mail.select(CONFIG["email"]["folder"])

        # Cherche les e-mails non lus
        status, messages = mail.search(None, 'UNSEEN')
        if status != 'OK':
            return

        for num in messages[0].split():
            status, msg_data = mail.fetch(num, '(RFC822)')
            if status != 'OK':
                continue

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Extraction des en-têtes
                    subject = decode_mime_words(msg.get("Subject", ""))
                    sender = decode_mime_words(msg.get("From", ""))
                    recipient = decode_mime_words(msg.get("To", ""))
                    
                    mail_info = {
                        "subject": subject,
                        "sender": sender,
                        "recipient": recipient
                    }

                    # Traitement via les règles définies
                    for rule in CONFIG["email"]["rules"]:
                        if check_conditions(mail_info, rule["conditions"]):
                            channel = BOT.get_channel(rule["channel_id"])
                            if channel:
                                embed = discord.Embed(
                                    title=f"📧 Nouveau Mail: {subject}",
                                    description=recipient[:4096],
                                    color=discord.Color.red()
                                )
                                embed.add_field(name="From", value=sender, inline=False)
                                
                                await channel.send(embed=embed)
                                
            # Marquer l'e-mail comme lu est géré automatiquement par le fetch RFC822 sans le flag (PEEK)
            
        mail.logout()
    except Exception as e:
        print(f"Erreur lors de la vérification des e-mails : {e}")