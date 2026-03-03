import uuid
from quart import request, redirect, url_for, render_template, session
from functools import wraps

from globals import WEB_APP, CONFIG, INDEX_HTML
from config import save_config_async

# ==========================================
# DÉCORATEUR DE SÉCURITÉ
# ==========================================
def login_required(f):
    """Vérifie si l'utilisateur possède un cookie de session valide."""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for('login'))
        return await f(*args, **kwargs)
    return decorated_function

# ==========================================
# ROUTES D'AUTHENTIFICATION
# ==========================================
@WEB_APP.route('/login', methods=['GET', 'POST'])
async def login():
    """Gère l'affichage et la soumission du formulaire de connexion."""
    error = None
    if request.method == 'POST':
        form_data = await request.form
        # Vérification stricte du mot de passe
        if form_data.get("password") == CONFIG["panel"]["password"]:
            session["logged_in"] = True
            return redirect(url_for('index'))
        else:
            error = "Mot de passe incorrect."
            
    return await render_template("login.html", error=error)

@WEB_APP.route('/logout')
async def logout():
    """Détruit la session en cours."""
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# ROUTES DU SERVEUR WEB (VERROUILLÉES)
# ==========================================
@WEB_APP.route('/')
@login_required
async def index():
    return await render_template(INDEX_HTML, config=CONFIG)

@WEB_APP.route('/update_imap', methods=['POST'])
@login_required
async def update_imap():
    form_data = await request.form
    CONFIG["email"]["imap_server"] = form_data.get("imap_server")
    CONFIG["email"]["port"] = int(str(form_data.get("imap_port")))
    CONFIG["email"]["email"] = form_data.get("email_address")
    CONFIG["email"]["password"] = form_data.get("email_password")
    await save_config_async(CONFIG)
    return redirect(url_for('index'))

@WEB_APP.route('/update_nextcloud', methods=['POST'])
@login_required
async def update_nextcloud():
    form_data = await request.form
    CONFIG["nextcloud"]["share_link"] = form_data.get("nc_link")
    CONFIG["nextcloud"]["password"] = form_data.get("password")
    CONFIG["nextcloud"]["channel_id"] = int(str(form_data.get("nc_channel")))
    
    from globals import PREVIOUS_NC_FILES, NC_INITIALIZED
    NC_INITIALIZED = False
    PREVIOUS_NC_FILES.clear()
    
    await save_config_async(CONFIG)
    return redirect(url_for('index'))

@WEB_APP.route('/add_rule', methods=['POST'])
async def add_rule():
    """Ajoute une nouvelle règle de tri des e-mails."""
    form_data = await request.form
    
    # Vérification stricte du Channel ID
    try:
        channel_id = int(form_data.get("rule_channel_id", 0))
    except ValueError:
        return redirect(url_for('index')) # Sécurité : Ignore si ce n'est pas un nombre
        
    conditions = {}
    
    # Nettoyage (.strip()) et ajout des conditions uniquement si elles sont remplies
    if form_data.get("cond_sender") and str(form_data.get("cond_sender")).strip():
        conditions["sender"] = str(form_data.get("cond_sender")).strip()
        
    if form_data.get("cond_recipient") and str(form_data.get("cond_recipient")).strip():
        conditions["recipient"] = str(form_data.get("cond_recipient")).strip()
        
    if form_data.get("cond_subject") and str(form_data.get("cond_subject")).strip():
        conditions["subject_contains"] = str(form_data.get("cond_subject")).strip()
        
    # La sensibilité à la casse
    conditions["case_sensitive"] = True if form_data.get("cond_case_sensitive") == "true" else False
    
    # N'ajouter la règle que si au moins une condition (hors casse) est définie
    if len(conditions) > 1:
        new_rule = {
            "id": str(uuid.uuid4()),
            "channel_id": channel_id,
            "conditions": conditions,
            "subscribers": []
        }
        
        if "rules" not in CONFIG["email"]:
            CONFIG["email"]["rules"] = []
            
        CONFIG["email"]["rules"].append(new_rule)
        
        from main import BOT
        from components import NotificationView
        BOT.add_view(NotificationView("email", new_rule["id"]))
        
        await save_config_async(CONFIG)
        
    return redirect(url_for('index'))

@WEB_APP.route('/delete_rule/<int:rule_index>', methods=['POST'])
async def delete_rule(rule_index):
    """Supprime une règle de tri via son index dans la liste."""
    if "rules" in CONFIG["email"] and 0 <= rule_index < len(CONFIG["email"]["rules"]):
        CONFIG["email"]["rules"].pop(rule_index)
        await save_config_async(CONFIG)
    return redirect(url_for('index'))