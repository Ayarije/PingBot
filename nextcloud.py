import discord
from discord.ext import tasks
import re
import requests
import logging
import urllib.parse
import xml.etree.ElementTree as ET

from globals import CONFIG, PREVIOUS_NC_FILES, BOT, NC_INITIALIZED
from components import NotificationView

# ==========================================
# FONCTIONS UTILITAIRES NEXTCLOUD (WEBDAV)
# ==========================================
def get_nextcloud_files():
    """Utilise l'API WebDAV de Nextcloud pour lister les fichiers d'un lien partagé."""
    match = re.match(r"(https?://[^/]+)/s/([a-zA-Z0-9]+)", CONFIG["nextcloud"]["share_link"])
    if not match:
        logging.error("Le lien Nextcloud n'est pas dans un format standard (/s/TOKEN).")
        return None

    base_url = match.group(1)
    token = match.group(2)
    
    webdav_url = f"{base_url}/public.php/webdav/"
    
    # Requête PROPFIND standard pour lister le contenu
    headers = {'Depth': '1'}
    auth = (token, CONFIG["nextcloud"]["password"])
    
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
        filename = urllib.parse.unquote(href.split('/')[-1])
        if filename:
            files.add(filename)
            
    return files

@tasks.loop(minutes=CONFIG["nextcloud"]["check_interval_minutes"])
async def check_nextcloud():
    global PREVIOUS_NC_FILES, NC_INITIALIZED
    logging.info("Checking nextcloud...")
    
    current_files = get_nextcloud_files()
    if current_files is None: return

    if not NC_INITIALIZED:
        NC_INITIALIZED = True
        PREVIOUS_NC_FILES = current_files
        return

    added_files = current_files - PREVIOUS_NC_FILES
    removed_files = PREVIOUS_NC_FILES - current_files


    channel = BOT.get_channel(CONFIG["nextcloud"]["channel_id"])
    if channel and (added_files or removed_files):
        logging.info("There is added or removed files")

        # Extraction des abonnés
        subs = CONFIG["nextcloud"].get("subscribers", [])
        mentions_str = " ".join([f"<@{uid}>" for uid in subs])
        content = f"|| {mentions_str} ||" if subs else ""
        
        view = NotificationView("nextcloud", "main")
        
        if added_files:
            logging.info("There is added files")
            embed_add = discord.Embed(title="📁 Nouveaux fichiers ajoutés (Nextcloud)", color=discord.Color.green())
            embed_add.description = "\n".join([f"➕ {f}" for f in added_files])
            await channel.send(content=content, embed=embed_add, view=view)
            
        if removed_files:
            logging.info("There is removed files")
            embed_rem = discord.Embed(title="🗑️ Fichiers supprimés (Nextcloud)", color=discord.Color.red())
            embed_rem.description = "\n".join([f"➖ {f}" for f in removed_files])
            await channel.send(content=content, embed=embed_rem, view=view)

    PREVIOUS_NC_FILES = current_files