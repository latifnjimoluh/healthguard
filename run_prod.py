import sys
import os

# Ajoute le répertoire courant au PYTHONPATH
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

if __name__ == "__main__":
    import uvicorn
    # Importation retardée pour s'assurer que le sys.path est à jour
    from src.api.app import app
    uvicorn.run(app, host="127.0.0.1", port=8000)
