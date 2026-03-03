from dotenv import load_dotenv
load_dotenv()

import logging
import os
import uuid
import asyncio
import argparse

from globals import WEB_APP, BOT, CONFIG
from mail import check_emails
from nextcloud import check_nextcloud
from components import NotificationView
from config import save_config_async
import panel

# ==========================================
# CONFIGURATION GÉNÉRALE
# ==========================================

DISCORD_TOKEN = os.getenv("BOT_TOKEN")
if DISCORD_TOKEN is None:
    logging.error("Can't find bot token in environment variables please setup your bot at discord's developper's portal")
    os.abort()

# ==========================================
# GESTION DE LA FERMETURE (SHUTDOWN)
# ==========================================
async def quart_shutdown_trigger():
    """
    Fonction sentinelle. Elle tourne en silence et se termine 
    uniquement lorsque le bot Discord commence sa fermeture.
    Cela indique à Quart de libérer le port 5000 et de s'éteindre proprement.
    """
    while not BOT.is_closed():
        await asyncio.sleep(0.5)
    logging.info("Extinction propre du serveur web Quart...")

# ==========================================
# ÉVÉNEMENTS DISCORD
# ==========================================
@BOT.event
async def on_ready():
    logging.info(f"Bot connecté en tant que {BOT.user}")
    
    # --- MIGRATION & PERSISTANCE DES BOUTONS ---
    config_mutated = False

    if "panel" not in CONFIG:
        CONFIG["panel"] = {"password": "admin"}
        config_mutated = True
    
    # Nextcloud
    if "subscribers" not in CONFIG["nextcloud"]:
        CONFIG["nextcloud"]["subscribers"] = []
        config_mutated = True
    BOT.add_view(NotificationView("nextcloud", "main"))
    
    # E-mails (Ajout d'UUID pour les anciennes règles et enregistrement des vues)
    for rule in CONFIG["email"].get("rules", []):
        if "id" not in rule:
            rule["id"] = str(uuid.uuid4())
            config_mutated = True
        if "subscribers" not in rule:
            rule["subscribers"] = []
            config_mutated = True
            
        BOT.add_view(NotificationView("email", rule["id"]))
        
    if config_mutated:
        await save_config_async(CONFIG)
    # --------------------------------------------

    if not check_emails.is_running():
        logging.info("Starting email checks")
        check_emails.start()
        
    if not check_nextcloud.is_running():
        logging.info("Starting nextcloud checks")
        check_nextcloud.start()

    logging.info("Démarrage du panel d'administration web sur http://127.0.0.1:5000")
    BOT.loop.create_task(WEB_APP.run_task(
        host='0.0.0.0', 
        port=5000, 
        shutdown_trigger=quart_shutdown_trigger
    ))

def main():
    global DISCORD_TOKEN
    assert DISCORD_TOKEN != None
    parser = argparse.ArgumentParser(description="An example script with a flag.")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("app.log", mode="w", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

    if args.debug:
        logging.info("Debug mode is ON")
    else:
        logging.info("Running in standard mode")
        
    BOT.run(DISCORD_TOKEN, log_handler=None)

if __name__ == "__main__":
    main()