import discord
from globals import CONFIG
from config import save_config_async

class NotificationView(discord.ui.View):
    def __init__(self, target_type, target_id):
        super().__init__(timeout=None)
        self.target_type = target_type
        self.target_id = target_id
        
        custom_id = f"notif_{target_type}_{target_id}"
        
        btn = discord.ui.Button(
            label="🔔 Toggle Notifications", 
            style=discord.ButtonStyle.secondary, 
            custom_id=custom_id
        )
        btn.callback = self.toggle
        self.add_item(btn)

    async def toggle(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        added = False
        
        # Logique pour Nextcloud
        if self.target_type == "nextcloud":
            if "subscribers" not in CONFIG["nextcloud"]:
                CONFIG["nextcloud"]["subscribers"] = []
                
            if user_id in CONFIG["nextcloud"]["subscribers"]:
                CONFIG["nextcloud"]["subscribers"].remove(user_id)
            else:
                CONFIG["nextcloud"]["subscribers"].append(user_id)
                added = True
                
        # Logique pour les E-mails
        elif self.target_type == "email":
            for rule in CONFIG["email"]["rules"]:
                if rule.get("id") == self.target_id:
                    if "subscribers" not in rule:
                        rule["subscribers"] = []
                        
                    if user_id in rule["subscribers"]:
                        rule["subscribers"].remove(user_id)
                    else:
                        rule["subscribers"].append(user_id)
                        added = True
                    break
        
        # Sauvegarde sur le disque dur
        await save_config_async(CONFIG)
        
        # Réponse éphémère
        msg = "✅ Notifications **activées** pour cette alerte." if added else "🔕 Notifications **désactivées** pour cette alerte."
        await interaction.response.send_message(msg, ephemeral=True)