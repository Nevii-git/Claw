import asyncio
import discord
import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv('TOKEN')
TWITCH_NOTIFICATION_CHANNEL = int(os.getenv('TWITCH_NOTIFICATION_CHANNEL'))
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
TWITCH_USERNAMES = os.getenv('TWITCH_USERNAMES', '').replace('\\', '').split(',')
TWITCH_USERNAMES = [username.strip() for username in TWITCH_USERNAMES if username.strip()]
BOT_NAME = os.getenv('BOT_NAME', 'DiscordBot')

LOG_DIR = f"/home/cordo/{BOT_NAME}/logs/"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),  # Logs dans le fichier
        logging.StreamHandler()         # Logs dans la console
    ]
)

if not DISCORD_TOKEN:
    logging.critical("Le token Discord est manquant dans le fichier .env !")
    raise ValueError("TOKEN manquant dans le fichier .env")
if not TWITCH_NOTIFICATION_CHANNEL:
    logging.critical("L'ID du canal Discord est manquant ou invalide dans le fichier .env !")
    raise ValueError("NOTIFICATION_CHANNEL manquant ou invalide dans le fichier .env")
if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
    logging.critical("Les identifiants Twitch sont manquants dans le fichier .env !")
    raise ValueError("TWITCH_CLIENT_ID ou TWITCH_CLIENT_SECRET manquant dans le fichier .env")
if not TWITCH_USERNAMES or TWITCH_USERNAMES == ['']:
    logging.warning("Aucun streamer n'a été spécifié dans le fichier .env. La liste est vide.")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

async def fetch_twitch_access_token():
    """Obtenir un token d'accès OAuth pour Twitch"""
    try:
        url = "https://id.twitch.tv/oauth2/token"
        payload = {
            "client_id": TWITCH_CLIENT_ID,
            "client_secret": TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials"
        }
        response = requests.post(url, data=payload)
        response.raise_for_status()
        logging.info("Token d'accès Twitch récupéré avec succès.")
        return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
        logging.error(f"Erreur lors de la récupération du token Twitch : {e}")
        raise

async def get_live_streams(usernames, access_token):
    """Récupère les informations de streaming pour une liste d'utilisateurs"""
    try:
        url = "https://api.twitch.tv/helix/streams"
        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {access_token}"
        }
        params = [("user_login", username.strip()) for username in usernames if username.strip()]
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        logging.info(f"Requête réussie pour {len(usernames)} streamers. Streamers en direct : {len(data['data'])}")
        return {stream["user_login"]: stream for stream in data["data"]}
    except requests.exceptions.RequestException as e:
        logging.error(f"Erreur lors de la récupération des données Twitch : {e}")
        return {}

async def check_stream_status():
    """Vérifie régulièrement le statut des streamers"""
    try:
        access_token = await fetch_twitch_access_token()
        notified = set()

        while True:
            try:
                live_streams = await get_live_streams(TWITCH_USERNAMES, access_token)
                channel = client.get_channel(TWITCH_NOTIFICATION_CHANNEL)
                if not channel:
                    logging.error(f"Impossible de trouver le canal avec l'ID {TWITCH_NOTIFICATION_CHANNEL}")
                    return

                for username in TWITCH_USERNAMES:
                    username = username.strip()  # Nettoyer les espaces inutiles
                    if username in live_streams and username not in notified:
                        stream = live_streams[username]
                        await channel.send(
                            f"🚨 **{username}** est en direct ! Titre : *{stream['title']}*\n"
                            f"Regardez ici : https://www.twitch.tv/{username}"
                        )
                        logging.info(f"Notification envoyée pour {username}.")
                        notified.add(username)

                notified = {username for username in notified if username in live_streams}

            except Exception as e:
                logging.error(f"Erreur lors de la vérification des statuts Twitch : {e}")
            await asyncio.sleep(60)
    except Exception as e:
        logging.critical(f"Erreur critique dans la boucle de vérification : {e}")
        raise

@client.event
async def on_ready():
    logging.info(f"Bot connecté comme {client.user}")
    client.loop.create_task(check_stream_status())

def run():
    try:
        client.run(DISCORD_TOKEN)
    except Exception as e:
        logging.critical(f"Erreur lors de l'exécution du bot Discord : {e}")
        raise

if __name__=='__main__':
    run()
