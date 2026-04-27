import pyautogui
import time
import sys
from datetime import datetime, timedelta

def delayed_press_enter(hours=4, minutes=10):
    total_seconds = (hours * 3600) + (minutes * 60)
    target_time = datetime.now() + timedelta(seconds=total_seconds)
    
    print(f"Démarrage du compte à rebours.")
    print(f"Heure actuelle : {datetime.now().strftime('%H:%M:%S')}")
    print(f"Action prévue à : {target_time.strftime('%H:%M:%S')} (dans {hours}h {minutes}min)")
    print("Appuyez sur Ctrl+C pour annuler.")
    
    try:
        # Attente jusqu'à l'heure cible
        # On utilise une boucle avec un petit sleep pour permettre l'interruption par Ctrl+C facilement
        while datetime.now() < target_time:
            remaining = target_time - datetime.now()
            # On affiche le temps restant toutes les minutes pour information
            sys.stdout.write(f"\rTemps restant : {str(remaining).split('.')[0]}    ")
            sys.stdout.flush()
            time.sleep(1)
            
        print("\n\nTemps écoulé !")
        # Simule l'appui sur la touche 'enter'
        pyautogui.press('enter')
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Touche 'Entrée' pressée avec succès.")
        
    except KeyboardInterrupt:
        print("\n\nOpération annulée par l'utilisateur.")
        sys.exit(0)

if __name__ == "__main__":
    # Paramètres : 4 heures et 10 minutes
    delayed_press_enter(4, 10)
