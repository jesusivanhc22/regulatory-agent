"""
Entry point para el dashboard web.
Ejecutar: python run_web.py
Acceder: http://localhost:5000
"""

import os
import sys

# Asegurar que el directorio raiz este en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from web.app import create_app

if __name__ == "__main__":
    app = create_app()
    debug = os.environ.get("FLASK_ENV", "production") == "development"
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=debug,
    )
