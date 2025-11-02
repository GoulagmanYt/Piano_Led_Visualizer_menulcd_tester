# PianoLCDExactPreview

**Objectif** : Afficher sous Windows exactement le rendu LCD du projet **onlaj/Piano-LED-Visualizer**, en réutilisant *lib/menulcd.py* (même rendu Pillow, sans réimplémentation), avec navigation clavier/souris et **hot-reload** des fichiers de config.

---

## ✅ Points clés

- **Aucune réimplémentation du rendu** : on importe `lib/menulcd.py` depuis le repo local et on récupère l’image PIL finale (framebuffer).
- **Résolution native auto** (ex. 320×240, 480×320) – upscale **nearest-neighbor** 1x/2x/3x… (aucun lissage).
- **Ressources à l’identique** : mêmes polices/assets que dans le repo. Si des ressources sont manquantes, l’erreur apparaît dans le panneau *Status*.
- **Navigation identique** : flèches/Enter/Backspace/molette mappées vers les actions du menu (via *stubs* GPIO), avec *fallback* si l’API diffère.
- **Hot-reload** des fichiers `config/menu.xml`, `config/settings.xml`, `config/default_settings.xml`, ainsi que `fonts/` et `assets/` (debounce 200 ms). Un cadre vert clignote pour signaler le rechargement.
- **Captures** : PNG natifs et GIF 5s@10fps (optionnel, nécessite `imageio`).

---

## 📦 Structure du projet

```
PianoLCDExactPreview/
├─ app.py                         # Entrée PySide6 (fenêtre, toolbar, dock Status)
├─ build_win.bat                  # Packaging PyInstaller → dist/PianoLCDExactPreview.exe
├─ requirements.txt
├─ README.md
├─ Snapshots/                     # Exports PNG/GIF
├─ logs/                          # Fichier logs/previewer.log
└─ lcd_preview/
   ├─ bootstrap_repo.py           # Sélection et validation du dossier du repo
   ├─ stubs_gpio.py               # Faux RPi.GPIO (callbacks & simulateur d’edges)
   ├─ fake_platform.py            # Force l’usage de drivers neutres si besoin
   ├─ menulcd_bridge.py           # Création/gestion MenuLCD + actions + captures + reload
   ├─ menu_controller.py          # Mapping clavier/souris → actions
   └─ qimage_from_pil.py          # Conversion PIL → QImage (RGB888)
   └─ watcher.py                  # Watchdog + debounce
```

---

## 🖥️ Installation (Windows 10/11, Python 3.11 recommandé)

1. **Cloner** le repo original localement (ou récupérer votre archive) :  
   `onlaj/Piano-LED-Visualizer`

2. **Créer un venv** et installer les dépendances :

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

3. **Lancer l’application** :

```powershell
python app.py
```

Au premier lancement, une boîte de dialogue vous demandera le **dossier du repo**. Le chemin est mémorisé dans `settings.json` à la racine du projet.

---

## ⌨️ Raccourcis

- **Ctrl+R** : Reload complet (réimport + réinstanciation `MenuLCD`)
- **Ctrl+S** : Snapshot PNG (résolution native, sans upscale)
- **Ctrl+G** : Enregistrement GIF (5s @ 10fps)
- **Esc** : Retour Home
- **Molette** : Encodeur ± (avec *fallback* sur ↑/↓)
- **Flèches / Enter / Backspace** : Navigation

---

## 🧠 Comment ça marche

- On **n’instrumente pas** `menulcd.py`. On l’importe tel quel (`import lib.menulcd`), on instancie `MenuLCD` (plusieurs signatures testées), puis on **récupère directement** l’image PIL du framebuffer via :
  - `get_frame()` / `get_framebuffer()` / attributs `framebuffer`/`image`/`frame` (détection auto), ou
  - scan des attributs d’instance pour trouver un `PIL.Image`.
- Pour les **actions**, on cherche dynamiquement des méthodes usuelles (`on_up`, `button_up`, `select`, `back`, `home`, etc.). Si rien ne correspond, on tente un `handle_key(<nom>)`.  
  > Cela permet de s’adapter aux variations d’API sans modifier le code original.
- Les **stubs GPIO** (`lcd_preview/stubs_gpio.py`) remplacent `RPi.GPIO` afin que l’import `import RPi.GPIO as GPIO` fonctionne et que les callbacks puissent s’enregistrer.

---

## 🔁 Hot-reload

Le watcher surveille :

- `config/menu.xml`
- `config/settings.xml`
- `config/default_settings.xml`
- `fonts/` et `assets/`

Après modification, l’appli **réimportera** `lib.menulcd`, **réinstanciera** `MenuLCD` et rafraîchira l’affichage. Un **cadre vert** s’affiche brièvement.

> Préservation exacte de l’écran courant : **best-effort** (selon les API disponibles). En cas d’impossibilité, on revient au menu principal.

---

## 🧪 Tests manuels (critères d’acceptation)

- Je pointe l’app vers le repo → le **menu racine s’affiche** identique au LCD matériel.
- Les **flèches/Enter/Backspace/molette** naviguent comme sur l’appareil.
- Je modifie `config/menu.xml` (ex. renommer un item) → **l’affichage se met à jour** automatiquement.
- Le **PNG exporté** correspond **pixel‑pour‑pixel** au rendu natif (sans upscale).

---

## 🏗️ Build Windows (PyInstaller)

Exécuter :

```powershell
.\build_win.bat
```

Cela génère `dist/PianoLCDExactPreview.exe` (mode `--windowed`, sans console).

---

## ❗Dépannage

- **Polices/assets manquants** : vérifiez les chemins dans votre repo. Les erreurs s’affichent dans le panneau *Status* et dans `logs/previewer.log`.
- **ImportError / AttributeError** : selon les versions du repo, certains noms de méthodes peuvent différer. Le bridge tente plusieurs signatures et fournit un *fallback* `handle_key()` si présent.
- **Pas de rendu** : ouvrez `logs/previewer.log` et vérifiez que `lib/menulcd.py` expose bien une image (`frame`, `image`, `framebuffer`, etc.).
```

