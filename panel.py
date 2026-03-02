from quart import request, redirect, url_for, render_template

from globals import WEB_APP, CONFIG, INDEX_HTML
from config import save_config_async

# ==========================================
# ROUTES DU SERVEUR WEB (QUART)
# ==========================================
@WEB_APP.route('/')
async def index():
    """Affiche l'interface avec les données actuelles en RAM."""
    return await render_template(INDEX_HTML, config=CONFIG)

@WEB_APP.route('/update_imap', methods=['POST'])
async def update_imap():
    """Met à jour les identifiants IMAP en RAM et sur le disque."""
    form_data = await request.form
    CONFIG["email"]["imap_server"] = form_data.get("imap_server")
    CONFIG["email"]["port"] = int(form_data.get("imap_port"))
    CONFIG["email"]["email"] = form_data.get("email_address")
    CONFIG["email"]["password"] = form_data.get("email_password")
    
    await save_config_async(CONFIG)
    return redirect(url_for('index'))

@WEB_APP.route('/update_nextcloud', methods=['POST'])
async def update_nextcloud():
    """Met à jour le lien Nextcloud en RAM et sur le disque."""
    form_data = await request.form
    CONFIG["nextcloud"]["share_link"] = form_data.get("nc_link")
    CONFIG["nextcloud"]["channel_id"] = int(form_data.get("nc_channel"))
    
    await save_config_async(CONFIG)
    return redirect(url_for('index'))