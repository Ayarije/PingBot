import os
import json
import logging
import asyncio

CONFIG_FILE = os.getenv("CONFIG_FILE") if os.getenv("CONFIG_FILE") is not None else ""
if CONFIG_FILE is None:
    logging.error("Can't find CONFIG_FILE in environment's variables")
    os.abort()

DEFAULT_CONFIG = {
    "email": {
        "imap_server": "imap.gmail.com",
        "port": 993,
        "email": "",
        "password": "",
        "folder": "inbox",
        "check_interval_minutes": 5,
        "rules": []
    },
    "nextcloud": {
        "share_link": "",
        "channel_id": 0,
        "check_interval_minutes": 10
    },
}

def load_config():
    """Charge la configuration depuis le fichier JSON de manière synchrone au démarrage."""
    assert CONFIG_FILE != None
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logging.error("Le fichier JSON est corrompu. Chargement des paramètres par défaut.")
    return DEFAULT_CONFIG

async def save_config_async(config_data):
    """Sauvegarde la configuration de manière asynchrone pour ne pas bloquer le bot Discord."""
    def _write_json():
        assert CONFIG_FILE != None
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
    
    # Délègue l'opération I/O bloquante à un thread séparé
    await asyncio.to_thread(_write_json)