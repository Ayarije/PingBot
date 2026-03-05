# PingBot - Le pont entre vos outils et Discord

PingBot est un bot Discord asynchrone conçu pour centraliser vos alertes professionnelles et scolaires directement dans vos salons Discord. Il surveille en temps réel vos boîtes e-mail (IMAP) et vos dossiers partagés Nextcloud, avec un système de filtrage puissant et une interface d'administration Web intégrée.

## Fonctionnalités

* **Surveillance Nextcloud :** Surveille les ajouts et suppressions de fichiers sur un lien de partage public Nextcloud. Utilise une architecture de requêtes "hybride" (WebDAV + Session PHP) capable de contourner les pare-feux institutionnels stricts (WAF, Fail2Ban).
* **Routage d'E-mails (IMAP) :** Lit les e-mails entrants via IMAP SSL et les transfère sur Discord.
* **Moteur de Filtrage par Regex :** Triez vos e-mails avec une précision chirurgicale grâce aux Expressions Régulières (Regex). Routez les messages vers des salons spécifiques en fonction de l'expéditeur, du destinataire ou de l'objet du mail.
* **Panel d'Administration Web :** Une interface utilisateur claire, inspirée de Google Forms, pour configurer les identifiants et les règles de tri sans jamais toucher au code. Sécurisée par un système de session chiffrée.
* **Commandes Slash Interactives :** * `/nextcloud_list` : Affiche instantanément le contenu du dossier surveillé.
    * `/status` : Réalise un diagnostic silencieux des connexions IMAP et Nextcloud en temps réel.
* **Abonnements aux Notifications :** Les utilisateurs peuvent s'abonner (bouton "🔔 Toggle Notifications") pour être mentionnés (`@User`) lorsqu'une nouvelle alerte tombe dans un salon.

## Prérequis

* **Python 3.8+** (Testé sur Python 3.14)
* Un compte développeur Discord et un Bot Token.
* **(Optionnel mais recommandé) Miniconda** pour isoler l'environnement Python.

## Installation & Lancement (Environnement Linux / VM)

PingBot est conçu pour fonctionner en "User Space", c'est-à-dire **sans nécessiter les droits administrateur (`sudo`)**, ce qui le rend idéal pour les environnements partagés.

### 1. Clonage et Environnement Virtuel

``` bash
git clone https://github.com/Ayarije/PingBot.git
cd PingBot

# Création d'un environnement Conda isolé
conda create -n pingbot python=3.11 -y
conda activate pingbot
pip install -r requirement.txt
```

### 2. Lancement

``` bash
conda activate pingbot
python main.py
```