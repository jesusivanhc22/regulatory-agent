import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

KEYWORDS = [
    "farmacia",
    "medicamento",
    "CFDI",
    "IVA",
    "ISR",
    "NOM",
    "COFEPRIS",
    "receta",
    "controlado"
]
