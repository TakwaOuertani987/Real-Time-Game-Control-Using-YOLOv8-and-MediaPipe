import tkinter as tk
import subprocess
import time
import threading

def lancer_jeu_et_detection():
    def run_scripts():
        try:
            print("🎮 Lancement du jeu...")
            subprocess.Popen(["python", "test5.py"])
            time.sleep(0.0000005)
            print("👀 Lancement du script de détection...")
            subprocess.Popen(["python", "detection_client3.py"])
        except Exception as e:
            print(f"❌ Erreur lors du lancement : {e}")

    # Exécuter les scripts dans un thread séparé pour ne pas bloquer l'interface
    threading.Thread(target=run_scripts, daemon=True).start()

# === Interface Tkinter ===
fenetre = tk.Tk()
fenetre.title("🎮 Lanceur du Jeu")
fenetre.geometry("400x200")
fenetre.configure(bg="#282c34")

# Label
label = tk.Label(fenetre, text="Lancer le jeu interactif", font=("Arial", 14), bg="#282c34", fg="white")
label.pack(pady=20)

# Bouton de lancement
bouton_lancer = tk.Button(fenetre, text="▶ Lancer le jeu", font=("Arial", 14), bg="#4CAF50", fg="white", command=lancer_jeu_et_detection)
bouton_lancer.pack(pady=20)

# Boucle Tkinter
fenetre.mainloop()
