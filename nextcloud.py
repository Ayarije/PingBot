import discord
from discord.ext import tasks
import re
import requests
import urllib.parse
import xml.etree.ElementTree as ET
import urllib3
import asyncio
import logging
from bs4 import BeautifulSoup

from globals import CONFIG, PREVIOUS_NC_FILES, BOT, NC_INITIALIZED
from components import NotificationView

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# FONCTION HYBRIDE (SCRAPING DE JETON + WEBDAV)
# ==========================================
def get_nextcloud_files():
    """Simule un navigateur : Utilise 100% la session PHP, sans déclencher le Basic Auth."""
    match = re.match(r"(https?://[^/]+)/s/([a-zA-Z0-9]+)", CONFIG["nextcloud"]["share_link"])
    if not match:
        return None

    base_url = match.group(1)
    share_token = match.group(2)
    share_url = CONFIG["nextcloud"]["share_link"]
    
    # L'ancienne URL WebDAV classique
    webdav_url = f"{base_url}/public.php/webdav/"
    password = CONFIG["nextcloud"]["password"]

    # En-têtes standards d'un navigateur
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive'
    }

    session = requests.Session()
    session.verify = False 

    try:
        # ÉTAPE 1 : Initialiser la session PHP et récupérer le CSRF
        response = session.get(share_url, headers=headers, timeout=15)
        response.raise_for_status()

        if 'name="password"' in response.text and password:
            session.post(f"{share_url}/authenticate", data={'password': password}, headers=headers, timeout=15)
            response = session.get(share_url, headers=headers, timeout=15)

        soup = BeautifulSoup(response.text, 'html.parser')
        head_tag = soup.find('head')
        request_token = head_tag.get('data-requesttoken') if head_tag else None

    except Exception as e:
        logging.error(f"Erreur lors de l'initialisation de la session : {e}")
        return None

    # ÉTAPE 2 : Requête WebDAV avec la SESSION UNIQUEMENT (Pas de 'auth=')
    propfind_headers = headers.copy()
    propfind_headers['Depth'] = '1'
    propfind_headers['Accept'] = 'application/xml, text/xml, */*; q=0.01'
    
    # L'en-tête magique qui indique à Nextcloud d'utiliser la session au lieu du Basic Auth
    propfind_headers['X-Requested-With'] = 'XMLHttpRequest'
    
    if request_token:
        propfind_headers['requesttoken'] = request_token

    try:
        dav_res = session.request("PROPFIND", webdav_url, headers=propfind_headers, timeout=15)
        dav_res.raise_for_status()

        files = set()
        root = ET.fromstring(dav_res.content)
        namespaces = {'d': 'DAV:'}
        
        for response_elem in root.findall('d:response', namespaces):
            href = response_elem.find('d:href', namespaces)
            assert isinstance(href, ET.Element)
            href = href.text
            assert isinstance(href, str)
            filename = urllib.parse.unquote(href.split('/')[-1])
            if filename:
                files.add(filename)
                
        logging.debug(f"Succès total ! Fichiers trouvés (WebDAV par Session) : {len(files)}")
        return files

    except requests.RequestException as e:
        logging.debug(f"Échec sur l'URL WebDAV classique : {e}")
        
        # =========================================================
        # FALLBACK : Tentative sur la nouvelle API SabreDAV Nextcloud
        # =========================================================
        logging.debug("Tentative de basculement sur la nouvelle API SabreDAV...")
        # Les serveurs récents utilisent cette route pour les liens publics
        alt_webdav_url = f"{base_url}/public.php/dav/files/{share_token}/"
        
        try:
            alt_res = session.request("PROPFIND", alt_webdav_url, headers=propfind_headers, timeout=15)
            alt_res.raise_for_status()
            
            files = set()
            root = ET.fromstring(alt_res.content)
            namespaces = {'d': 'DAV:'}
            for response_elem in root.findall('d:response', namespaces):
                href = response_elem.find('d:href', namespaces)
                assert isinstance(href, ET.Element)
                href = href.text
                assert isinstance(href, str)
                filename = urllib.parse.unquote(href.split('/')[-1])
                if filename and filename != share_token:
                    files.add(filename)
                    
            logging.debug(f"Succès total ! Fichiers trouvés (SabreDAV) : {len(files)}")
            return files
            
        except Exception as alt_e:
            logging.error(f"Erreur fatale sur les deux APIs : {alt_e}")
            return None

# ==========================================
# BOUCLE ASYNCHRONE DISCORD
# ==========================================
@tasks.loop(minutes=CONFIG["nextcloud"]["check_interval_minutes"])
async def check_nextcloud():
    global PREVIOUS_NC_FILES, NC_INITIALIZED
    
    if not CONFIG["nextcloud"]["share_link"]:
        return

    # Lancement dans un thread pour protéger la réactivité du bot Discord
    current_files = await asyncio.to_thread(get_nextcloud_files)
    
    if current_files is None:
        return 

    if not NC_INITIALIZED:
        PREVIOUS_NC_FILES = current_files
        NC_INITIALIZED = True
        return

    added_files = current_files - PREVIOUS_NC_FILES
    removed_files = PREVIOUS_NC_FILES - current_files

    channel = BOT.get_channel(CONFIG["nextcloud"]["channel_id"])
    assert isinstance(channel, discord.TextChannel)
    if channel and (added_files or removed_files):
        
        subs = CONFIG["nextcloud"].get("subscribers", [])
        mentions_str = " ".join([f"<@{uid}>" for uid in subs])
        content = f"|| {mentions_str} ||" if subs else ""
        
        view = NotificationView("nextcloud", "main")

        if added_files:
            embed_add = discord.Embed(title="📁 Nouveaux fichiers ajoutés (Nextcloud)", color=discord.Color.green())
            embed_add.description = "\n".join([f"➕ {f}" for f in added_files])
            await channel.send(content=content, embed=embed_add, view=view)
            
        if removed_files:
            embed_rem = discord.Embed(title="🗑️ Fichiers supprimés (Nextcloud)", color=discord.Color.red())
            embed_rem.description = "\n".join([f"➖ {f}" for f in removed_files])
            await channel.send(content=content, embed=embed_rem, view=view)

    PREVIOUS_NC_FILES = current_files