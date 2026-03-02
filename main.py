import discord
from discord.ext import tasks, commands
import imaplib
import email
from email.header import decode_header
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import asyncio
import re

# ==========================================
# CONFIGURATION GÉNÉRALE
# ==========================================
DISCORD_TOKEN = "TON_TOKEN_DISCORD_ICI"

# Configuration de la boîte mail
EMAIL_CONFIG = {
    "imap_server": "imap.gmail.com",
    "email": "ton_email@gmail.com",
    "password": "ton_mot_de_passe_d_application",
    "folder": "inbox",
    "check_interval_minutes": 5 # Vérifie toutes les 5 minutes
}

# Configuration Nextcloud
NEXTCLOUD_CONFIG = {
    "share_link": "https://cloud.tondomaine.com/s/T0k3nEx3mpl3",
    "password": "", # Laisser vide si le lien n'a pas de mot de passe
    "channel_id": 111111111111111111, # ID du channel pour les alertes Nextcloud
    "check_interval_minutes": 10
}

# Règles de tri des e-mails (1 Channel = 1 ou plusieurs conditions)
# Options de conditions : "sender", "recipient", "subject_contains", "body_contains", "case_sensitive"
EMAIL_RULES = [
    {
        "channel_id": 222222222222222222,
        "conditions": {
            "sender": "patron@entreprise.com",
            "subject_contains": "URGENT",
            "case_sensitive": True # Doit être exactement "URGENT" en majuscules
        }
    },
    {
        "channel_id": 333333333333333333,
        "conditions": {
            "subject_contains": "facture",
            "case_sensitive": False # Accepte "Facture", "FACTURE", "facture"
        }
    }
]

# ==========================================
# INITIALISATION DU BOT
# ==========================================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Stockage de l'état précédent de Nextcloud
previous_nc_files = set()

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
# FONCTIONS UTILITAIRES NEXTCLOUD (WEBDAV)
# ==========================================
def get_nextcloud_files():
    """Utilise l'API WebDAV de Nextcloud pour lister les fichiers d'un lien partagé."""
    # Parse le lien partagé pour extraire le domaine et le token
    match = re.match(r"(https?://[^/]+)/s/([a-zA-Z0-9]+)", NEXTCLOUD_CONFIG["share_link"])
    if not match:
        print("Erreur : Le lien Nextcloud n'est pas dans un format standard (/s/TOKEN).")
        return None

    base_url = match.group(1)
    token = match.group(2)
    
    # Point de terminaison officiel WebDAV pour les liens publics
    webdav_url = f"{base_url}/public.php/webdav/"
    
    # Requête PROPFIND standard pour lister le contenu
    headers = {'Depth': '1'}
    auth = (token, NEXTCLOUD_CONFIG["password"])
    
    try:
        response = requests.request("PROPFIND", webdav_url, auth=auth, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Erreur de connexion à Nextcloud : {e}")
        return None

    # Parsing du XML retourné par WebDAV
    files = set()
    root = ET.fromstring(response.content)
    # Les namespaces XML utilisés par WebDAV
    namespaces = {'d': 'DAV:'}
    
    for response_elem in root.findall('d:response', namespaces):
        href = response_elem.find('d:href', namespaces).text
        # Nettoyage pour obtenir juste le nom du fichier, on ignore la racine (qui correspond au dossier lui-même)
        filename = urllib.parse.unquote(href.split('/')[-1])
        if filename:
            files.add(filename)
            
    return files

# ==========================================
# TÂCHES ASYNCRONES (BOUCLES)
# ==========================================
@tasks.loop(minutes=EMAIL_CONFIG["check_interval_minutes"])
async def check_emails():
    """Se connecte à l'IMAP, récupère les e-mails non lus, et les trie selon les règles."""
    try:
        mail = imaplib.IMAP4_SSL(EMAIL_CONFIG["imap_server"])
        mail.login(EMAIL_CONFIG["email"], EMAIL_CONFIG["password"])
        mail.select(EMAIL_CONFIG["folder"])

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
                    for rule in EMAIL_RULES:
                        if check_conditions(mail_info, rule["conditions"]):
                            channel = bot.get_channel(rule["channel_id"])
                            if channel:
                                embed = discord.Embed(
                                    title=f"📧 Nouveau Mail: {subject}",
                                    color=discord.Color.blue()
                                )
                                embed.add_field(name="De", value=sender, inline=False)
                                embed.add_field(name="Pour", value=recipient, inline=False)
                                embed.set_footer(text="Filtre appliqué selon tes conditions.")
                                
                                await channel.send(embed=embed)
                                
            # Marquer l'e-mail comme lu est géré automatiquement par le fetch RFC822 sans le flag (PEEK)
            
        mail.logout()
    except Exception as e:
        print(f"Erreur lors de la vérification des e-mails : {e}")

@tasks.loop(minutes=NEXTCLOUD_CONFIG["check_interval_minutes"])
async def check_nextcloud():
    """Vérifie les ajouts et suppressions de fichiers dans le dossier Nextcloud."""
    global previous_nc_files
    
    current_files = get_nextcloud_files()
    if current_files is None:
        return # Erreur de requête, on passe ce tour

    # Si c'est le premier lancement, on initialise juste la liste sans notifier
    if not previous_nc_files:
        previous_nc_files = current_files
        return

    # Calcul des différences
    added_files = current_files - previous_nc_files
    removed_files = previous_nc_files - current_files

    channel = bot.get_channel(NEXTCLOUD_CONFIG["channel_id"])
    if channel and (added_files or removed_files):
        if added_files:
            embed_add = discord.Embed(title="📁 Nouveaux fichiers ajoutés (Nextcloud)", color=discord.Color.green())
            embed_add.description = "\n".join([f"➕ {f}" for f in added_files])
            await channel.send(embed=embed_add)
            
        if removed_files:
            embed_rem = discord.Embed(title="🗑️ Fichiers supprimés (Nextcloud)", color=discord.Color.red())
            embed_rem.description = "\n".join([f"➖ {f}" for f in removed_files])
            await channel.send(embed=embed_rem)

    # Mise à jour de l'état
    previous_nc_files = current_files

# ==========================================
# ÉVÉNEMENTS DISCORD
# ==========================================
@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")
    
    # Lancement des tâches périodiques
    if not check_emails.is_running():
        check_emails.start()
        print("Surveillance e-mail activée.")
        
    if not check_nextcloud.is_running():
        check_nextcloud.start()
        print("Surveillance Nextcloud activée.")

# Lancement du bot
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)