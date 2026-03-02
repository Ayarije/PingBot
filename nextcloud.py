import discord
from discord.ext import tasks
import re
import requests
import urllib.parse
import xml.etree.ElementTree as ET

from globals import CONFIG, PREVIOUS_NC_FILES, BOT

# ==========================================
# FONCTIONS UTILITAIRES NEXTCLOUD (WEBDAV)
# ==========================================
def get_nextcloud_files():
    """Utilise l'API WebDAV de Nextcloud pour lister les fichiers d'un lien partagé."""
    # Parse le lien partagé pour extraire le domaine et le token
    match = re.match(r"(https?://[^/]+)/s/([a-zA-Z0-9]+)", CONFIG["nextcloud"]["share_link"])
    if not match:
        print("Erreur : Le lien Nextcloud n'est pas dans un format standard (/s/TOKEN).")
        return None

    base_url = match.group(1)
    token = match.group(2)
    
    # Point de terminaison officiel WebDAV pour les liens publics
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
        # Nettoyage pour obtenir juste le nom du fichier, on ignore la racine (qui correspond au dossier lui-même)
        filename = urllib.parse.unquote(href.split('/')[-1])
        if filename:
            files.add(filename)
            
    return files

@tasks.loop(minutes=CONFIG["nextcloud"]["check_interval_minutes"])
async def check_nextcloud():
    """Vérifie les ajouts et suppressions de fichiers dans le dossier Nextcloud."""
    global PREVIOUS_NC_FILES
    
    current_files = get_nextcloud_files()
    if current_files is None:
        return # Erreur de requête, on passe ce tour

    # Si c'est le premier lancement, on initialise juste la liste sans notifier
    if not PREVIOUS_NC_FILES:
        PREVIOUS_NC_FILES = current_files
        return

    # Calcul des différences
    added_files = current_files - PREVIOUS_NC_FILES
    removed_files = PREVIOUS_NC_FILES - current_files

    channel = BOT.get_channel(CONFIG["nextcloud"]["channel_id"])
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