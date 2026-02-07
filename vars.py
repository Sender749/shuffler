import os
from typing import List

API_ID = int(os.getenv("API_ID", "25208597"))
API_HASH = os.getenv("API_HASH", "e99c3c5693d6d23a143b6ce760b7a6de")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://gd3251791:tvTkKkoJFybHhB5w@cluster0.b2a0n.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

# Support multiple database channels - can be single or multiple IDs separated by space
DATABASE_CHANNEL_ID = os.getenv("DATABASE_CHANNEL_ID", "-1003136895050")
if " " in DATABASE_CHANNEL_ID:
    DATABASE_CHANNEL_IDS = [int(x.strip()) for x in DATABASE_CHANNEL_ID.split() if x.strip()]
else:
    DATABASE_CHANNEL_IDS = [int(DATABASE_CHANNEL_ID)]
DATABASE_CHANNEL_ID = DATABASE_CHANNEL_IDS[0]

ADMIN_ID = int(os.getenv("ADMIN_ID", "6541030917"))
PICS = (os.environ.get("PICS", "https://envs.sh/iKu.jpg https://envs.sh/iKE.jpg https://envs.sh/iKe.jpg https://envs.sh/iKi.jpg https://envs.sh/iKb.jpg")).split()
LOG_CHNL = int(os.getenv("LOG_CHNL", "-1003137381162"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Navex_69") # Without @
IS_FSUB = bool(os.environ.get("FSUB", False))
AUTH_CHANNELS = list(map(int, os.environ.get("AUTH_CHANNEL", "").split()))
DATABASE_CHANNEL_LOG = int(os.getenv("DATABASE_CHANNEL_LOG", "-1003137381162"))
FREE_VIDEO_DURATION = int(os.getenv("FREE_VIDEO_DURATION", "240"))
PROTECT_CONTENT  = bool(os.environ.get("PROTECT_CONTENT ", True))

# Verification Settings
IS_VERIFY = os.environ.get("IS_VERIFY", "True").lower() in ["true", "yes", "1", "enable"]
FREE_VIDEOS_COUNT = int(os.getenv("FREE_VIDEOS_COUNT", "3"))  # Free videos before verification
VERIFY_EXPIRE_TIME = int(os.getenv("VERIFY_EXPIRE_TIME", "21600"))  # 6 hours in seconds

# Three Shortlink APIs for verification
SHORTENER_API1 = os.getenv("SHORTENER_API1", "fb4812435a09dcca63276a47da3c8ac5c23239ef")
SHORTENER_WEBSITE1 = os.getenv("SHORTENER_WEBSITE1", "instantlinks.co")
TUTORIAL1 = os.getenv("TUTORIAL1", "https://t.me/Navexdisscussion/33")

SHORTENER_API2 = os.getenv("SHORTENER_API2", "fb4812435a09dcca63276a47da3c8ac5c23239ef")
SHORTENER_WEBSITE2 = os.getenv("SHORTENER_WEBSITE2", "instantlinks.co")
TUTORIAL2 = os.getenv("TUTORIAL2", "https://t.me/Navexdisscussion/33")

SHORTENER_API3 = os.getenv("SHORTENER_API3", "fb4812435a09dcca63276a47da3c8ac5c23239ef")
SHORTENER_WEBSITE3 = os.getenv("SHORTENER_WEBSITE3", "instantlinks.co")
TUTORIAL3 = os.getenv("TUTORIAL3", "https://t.me/Navexdisscussion/33")

LOG_VR_CHANNEL = int(os.getenv("LOG_VR_CHANNEL", "-1003137381162"))  # Verification log channel
VERIFY_IMG = os.getenv("VERIFY_IMG", "https://envs.sh/iKu.jpg")
