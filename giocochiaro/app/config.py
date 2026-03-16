import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "lotterie.db")
DATA_DIR = os.path.join(BASE_DIR, "data")
API_KEY = os.getenv("API_KEY", "")
if not API_KEY:
    raise RuntimeError("Variabile d'ambiente API_KEY non configurata!")

MAX_TENTATIVI = 15
INTERVALLO_RETRY = 60

TABELLE_VALIDE = {
    "millionday", "superenalotto", "lotto", "diecelotto",
    "vincicasa", "eurojackpot", "sivincetutto", "winforlife"
}