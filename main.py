from dotenv import load_dotenv
load_dotenv()

import logging
import os

from globals import WEB_APP, BOT
from mail import check_emails
from nextcloud import check_nextcloud


# ==========================================
# CONFIGURATION GÉNÉRALE
# ==========================================

DISCORD_TOKEN = os.getenv("BOT_TOKEN")
if DISCORD_TOKEN is None:
    logging.log(logging.ERROR, "Can't find bot token in environment variables please setup your bot at discord's developper's portal")
    os.abort()

# ==========================================
# ÉVÉNEMENTS DISCORD
# ==========================================
@BOT.event
async def on_ready():
    print(f"Bot connecté en tant que {BOT.user}")

    if not check_emails.is_running():
        check_emails.start()
        print("Surveillance e-mail activée.")
        
    if not check_nextcloud.is_running():
        check_nextcloud.start()
        print("Surveillance Nextcloud activée.")

    print("Démarrage du panel d'administration web sur http://127.0.0.1:5000")
    BOT.loop.create_task(WEB_APP.run_task(host='0.0.0.0', port=5000))

# Lancement du bot
if __name__ == "__main__":
    BOT.run(DISCORD_TOKEN)