import os
import json
import psutil
import customtkinter as ctk
import tkinter as tk
import winreg
import sys
from tkinter import filedialog, messagebox
from PIL import Image

GAMES_FILE = "games.json"

# Pfad zu einer Ressource (für PyInstaller)
def resource_path(relative_path: str) -> str:
    try:
        # PyInstaller packt alles nach _MEIPASS
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        # normaler Python-Run: Verzeichnis der aktuellen Datei
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

# Den Pfad für die Anzeige normalisieren (Backslashes zu Slashes ändern, Kleinbuchstaben zu Großbuchstaben etc.)
def normalize_path(p):
    if not p:
        return p

    # Erst normalisieren: Slashes und .. usw.
    p = os.path.normpath(p)

    # Laufwerk explizit groß schreiben
    drive, tail = os.path.splitdrive(p)   # z.B. ('c:', '\\program files\\steam\\steam.exe')
    if drive:
        drive = drive.upper()             # 'C:' statt 'c:'

    return drive + tail                   # 'C:\program files\steam\steam.exe'

# Registry-Lesehilfe
def read_reg_str(root, subkey, value_name):
    try:
        with winreg.OpenKey(root, subkey) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            return str(value)
    except OSError:
        return None

# Erste Value aus Registry lesen
def read_first_existing_reg_value(candidates):
    for root, subkey, value_name in candidates:
        val = read_reg_str(root, subkey, value_name)
        if val:
            return val
    return None

class GameLauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        icon_path = resource_path("assets/game_launcher.ico")
        self.iconbitmap(icon_path)

        # ----- Grundkonfiguration -----
        ctk.set_appearance_mode("dark")       # Startmodus
        ctk.set_default_color_theme("dark-blue")

        self.title("Game Launcher")

        # Fenster zentrale Größe und Position
        window_width = 1000
        window_height = 700
        self.geometry(f"{window_width}x{window_height}")
        self.center_window(window_width, window_height)

        # Spiele laden
        self.games = []
        self.load_games()

        self.grid_rowconfigure(0, weight=0)   # Header
        self.grid_rowconfigure(1, weight=1)   # Tabs-Bereich
        self.grid_columnconfigure(0, weight=1)  # nur eine Spalte

        # Panels
        self.create_header_bar()
        self.create_main_tabs()               # NEU statt left/right panel

    # --------------------------
    # Fenster zentrieren
    # --------------------------
    def center_window(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

    # --------------------------
    # Header-Bar
    # --------------------------
    def create_header_bar(self):
        self.header_frame = ctk.CTkFrame(self, corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)

        logo_path = resource_path("assets/game_launcher.png")

        logo_image = ctk.CTkImage(
            light_image=Image.open(logo_path),
            dark_image=Image.open(logo_path),
            size=(32, 32)
        )

        self.logo_label = ctk.CTkLabel(
            self.header_frame,
            image=logo_image,
            text=""
        )
        self.logo_label.grid(row=0, column=0, pady=(5, 0))

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="Game Launcher - Alpha",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.grid(row=1, column=0)

    # --------------------------
    # Main-Tabs
    # --------------------------
    def create_main_tabs(self):
        # Haupt-Tabview unter dem Header
        self.main_tabview = ctk.CTkTabview(self)
        self.main_tabview.grid(
            row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Tabs anlegen
        self.games_tab = self.main_tabview.add("Games")
        self.system_tab = self.main_tabview.add("System")
        self.settings_tab = self.main_tabview.add("Settings")

        # Inhalte aufbauen
        self.create_games_tab_content()
        self.create_system_tab_content()
        self.create_settings_tab_content()

    # --------------------------
    # Games-Tab
    # --------------------------
    def create_games_tab_content(self):
        # Games-Tab: eine Zeile, eine Spalte → komplette Breite für die Liste
        self.games_tab.grid_rowconfigure(0, weight=1)
        self.games_tab.grid_columnconfigure(0, weight=1)

        # Rahmen für die gesamte Liste
        self.left_frame = ctk.CTkFrame(self.games_tab, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew")

        title_label = ctk.CTkLabel(
            self.left_frame,
            text="Games",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title_label.pack(padx=10, pady=(10, 5), anchor="w")

        # Scrollbare Liste – keine feste width mehr, damit sie die Breite nutzen kann
        self.games_scroll = ctk.CTkScrollableFrame(self.left_frame)
        self.games_scroll.pack(padx=10, pady=(0, 10), fill="both", expand=True)

        self.render_game_buttons()

        add_game_btn = ctk.CTkButton(
            self.left_frame,
            text="Manuel Spiel hinzufügen",
            command=self.add_game_dialog
        )
        add_game_btn.pack(padx=10, pady=(0, 10), fill="x")

    # --------------------------
    # System-Tab
    # --------------------------
    def update_games_count_label(self):
        if hasattr(self, "games_count_label"):
            self.games_count_label.configure(
                text=f"Installierte Spiele: {len(self.games)}"
            )

    def refresh_disk_info(self):
        # Frame leeren
        for child in self.disks_frame.winfo_children():
            child.destroy()

        for part in psutil.disk_partitions(all=False):
            if "cdrom" in part.opts.lower() or part.fstype == "":
                continue

            try:
                usage = psutil.disk_usage(part.mountpoint)
            except PermissionError:
                continue

            total_gb = usage.total / (1024 ** 3)
            used_percent = usage.percent

            label = ctk.CTkLabel(
                self.disks_frame,
                text=f"{part.device} ({part.mountpoint}) – {total_gb:.1f} GB, benutzt: {used_percent:.1f} %"
            )
            label.pack(anchor="w", padx=5, pady=2)

    def refresh_launcher_info(self):
        # Frame leeren
        for child in self.launchers_frame.winfo_children():
            child.destroy()

        # Wenn wir schon gescannt haben, reuse – sonst neu scannen
        launchers = getattr(self, "launchers_status", self.detect_launchers())

        for name, info in launchers.items():
            found = info.get("installed", False)
            path = info.get("install_path") or "Pfad unbekannt"

            status = "✅ Gefunden" if found else "❌ Nicht gefunden"
            text = f"{name}: {status}"
            if found and path != "Pfad unbekannt":
                nice_path = normalize_path(path)
                text += f"\n  → {nice_path}"

            label = ctk.CTkLabel(
                self.launchers_frame,
                text=text,
                justify="left"
            )
            label.pack(anchor="w", padx=5, pady=2)

    # Bekannte Launcher erkennen
    def detect_launchers(self):
        launchers = {}

        # ---- Steam ----
        steam_path = read_first_existing_reg_value([
            (winreg.HKEY_CURRENT_USER,
            r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        ])

        if steam_path:
            steam_exe = os.path.join(steam_path, "steam.exe")
            installed = os.path.exists(steam_exe)
            launchers["Steam"] = {
                "installed": installed,
                "install_path": steam_exe if installed else steam_path,
            }
        else:
            launchers["Steam"] = {"installed": False, "install_path": None}

        # ---- Epic Games Launcher ----
        epic_dir = read_first_existing_reg_value([
            (winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Epic Games\EpicGamesLauncher", "InstallLocation"),
            (winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Epic Games\EpicGamesLauncher", "InstallLocation"),
        ])

        if epic_dir:
            epic_exe = os.path.join(epic_dir, "Launcher", "Portal", "Binaries", "Win64", "EpicGamesLauncher.exe")
            installed = os.path.exists(epic_exe)
            launchers["Epic Games"] = {
                "installed": installed,
                "install_path": epic_exe if installed else epic_dir,
            }
        else:
            launchers["Epic Games"] = {"installed": False, "install_path": None}

        # ---- EA App ----
        ea_path = (
            read_reg_str(winreg.HKEY_LOCAL_MACHINE, 
                              r"SOFTWARE\Electronic Arts\EA Desktop", "LauncherAppPath")
            or read_reg_str(winreg.HKEY_LOCAL_MACHINE, 
                                 r"SOFTWARE\WOW6432Node\Electronic Arts\EA Desktop", "LauncherAppPath")
        )
        if ea_path:
            installed = os.path.exists(ea_path)
            launchers["EA App"] = {
                "installed": installed,
                "install_path": ea_path if installed else None,
            }
        else:
            launchers["EA App"] = {"installed": False, "install_path": None}

        # ---- Ubisoft Connect ----
        ubi_dir = read_first_existing_reg_value([
            (winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Ubisoft\Launcher", "InstallDir"),
            (winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Ubisoft\Launcher", "InstallDir"),
        ])

        if ubi_dir:
            ubi_exe = os.path.join(ubi_dir, "UbisoftConnect.exe")
            installed = os.path.exists(ubi_exe)
            launchers["Ubisoft Connect"] = {
                "installed": installed,
                "install_path": ubi_exe if installed else ubi_dir,
            }
        else:
            launchers["Ubisoft Connect"] = {"installed": False, "install_path": None}

        # ---- Battle.net ----
        bnet_dir = read_first_existing_reg_value([
            (winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Blizzard Entertainment\Battle.net", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Blizzard Entertainment\Battle.net", "InstallPath"),
        ])

        if bnet_dir:
            bnet_exe = os.path.join(bnet_dir, "Battle.net.exe")
            installed = os.path.exists(bnet_exe)
            launchers["Battle.net"] = {
                "installed": installed,
                "install_path": bnet_exe if installed else bnet_dir,
            }
        else:
            launchers["Battle.net"] = {"installed": False, "install_path": None}

        # ---- GOG Galaxy ----
        gog_dir = read_first_existing_reg_value([
            (winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\GOG.com\GalaxyClient", "path"),
            (winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\GOG.com\GalaxyClient", "path"),
        ])

        if gog_dir:
            gog_exe = os.path.join(gog_dir, "GalaxyClient.exe")
            installed = os.path.exists(gog_exe)
            launchers["GOG Galaxy"] = {
                "installed": installed,
                "install_path": gog_exe if installed else gog_dir,
            }
        else:
            launchers["GOG Galaxy"] = {"installed": False, "install_path": None}

        return launchers

    def create_system_tab_content(self):
        self.system_tab.grid_rowconfigure(0, weight=0)
        self.system_tab.grid_rowconfigure(1, weight=0)
        self.system_tab.grid_rowconfigure(2, weight=0)
        self.system_tab.grid_rowconfigure(3, weight=1)
        self.system_tab.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            self.system_tab,
            text="System Übersicht",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title_label.grid(row=0, column=0, sticky="w", pady=(0, 10))

        # Spieleanzahl
        self.games_count_label = ctk.CTkLabel(
            self.system_tab,
            text=f"Installierte Spiele: {len(self.games)}"
        )
        self.games_count_label.grid(row=1, column=0, sticky="w", pady=(0, 5))

        # Laufwerks-Infos
        disks_title = ctk.CTkLabel(
            self.system_tab,
            text="Laufwerke:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        disks_title.grid(row=2, column=0, sticky="w", pady=(10, 5))

        self.disks_frame = ctk.CTkScrollableFrame(self.system_tab, height=150)
        self.disks_frame.grid(row=3, column=0, sticky="nsew")

        # Launcher-Infos unten drunter
        launchers_title = ctk.CTkLabel(
            self.system_tab,
            text="Launcher auf diesem System:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        launchers_title.grid(row=4, column=0, sticky="w", pady=(10, 5))

        self.launchers_frame = ctk.CTkFrame(self.system_tab)
        self.launchers_frame.grid(row=5, column=0, sticky="nw")

        # Launcher einmal erkennen und merken
        self.launchers_status = self.detect_launchers()

        # Steam-Import-Button nur, wenn Steam installiert ist
        if self.launchers_status.get("Steam", {}).get("installed"):
            self.steam_import_btn = ctk.CTkButton(
            self.system_tab,
            text="Steam-Bibliothek importieren",
            command=self.add_steam_library_dialog,
        )
        self.steam_import_btn.grid(row=6, column=0, sticky="ew", padx=10, pady=(10, 10))

        self.refresh_disk_info()
        self.refresh_launcher_info()
        self.update_games_count_label()

    # --------------------------
    # Settings-Tab
    # --------------------------
    def change_appearance_mode(self, new_mode: str):
        # customtkinter akzeptiert "System", "Dark", "Light"
        ctk.set_appearance_mode(new_mode)

    def create_settings_tab_content(self):
        self.settings_tab.grid_rowconfigure(0, weight=0)
        self.settings_tab.grid_rowconfigure(1, weight=0)
        self.settings_tab.grid_rowconfigure(2, weight=1)
        self.settings_tab.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            self.settings_tab,
            text="Settings",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title_label.grid(row=0, column=0, sticky="w", pady=(10, 10), padx=10)

        # Theme-Auswahl
        theme_label = ctk.CTkLabel(
            self.settings_tab,
            text="Theme:"
        )
        theme_label.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 5))

        self.theme_var = ctk.StringVar(value="Dark")  # Startwert

        self.theme_optionmenu = ctk.CTkOptionMenu(
            self.settings_tab,
            values=["System", "Dark", "Light"],
            variable=self.theme_var,
            command=self.change_appearance_mode
        )
        self.theme_optionmenu.grid(row=1, column=0, sticky="w", padx=80, pady=(0, 5))


    # --------------------------
    # Games speichern / laden
    # --------------------------
    def load_games(self):
        if os.path.exists(GAMES_FILE):
            try:
                with open(GAMES_FILE, "r", encoding="utf-8") as f:
                    self.games = json.load(f)
            except Exception as e:
                print(f"Fehler beim Laden von {GAMES_FILE}: {e}")
                self.games = []
        else:
            self.games = []

    def save_games(self):
        try:
            with open(GAMES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.games, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Fehler beim Speichern von {GAMES_FILE}: {e}")

    # --------------------------
    # Functions für Games-Tab
    # --------------------------
    def add_steam_library_dialog(self):
        folder = filedialog.askdirectory(
            title="Steam Library Ordner auswählen (z.B. steamapps/common)"
        )
        if not folder:
            return

        self.import_steam_games(folder)

    def import_steam_games(self, common_path: str):
        common_path = os.path.normpath(common_path)

        if not os.path.isdir(common_path):
            messagebox.showerror(
                "Fehler", "Der ausgewählte Pfad ist kein Verzeichnis.")
            return

        added = 0

        # Jeder Unterordner in steamapps/common ist typischerweise ein Spiel
        for game_dir_name in os.listdir(common_path):
            game_dir = os.path.join(common_path, game_dir_name)
            if not os.path.isdir(game_dir):
                continue

            exe_path = None

            # Suche nach .exe-Dateien im Spielordner
            for root, _, files in os.walk(game_dir):
                for file in files:
                    if file.lower().endswith(".exe"):
                        exe_path = os.path.join(root, file)
                        break
                if exe_path:
                    break

            # Wenn keine .exe gefunden wurde, überspringe
            if not exe_path:
                continue

            # Duplikate vermeiden
            if any(g["path"] == exe_path for g in self.games):
                continue

            # Spiel hinzufügen
            game_name = os.path.splitext(os.path.basename(exe_path))[0]
            self.games.append({"name": game_name, "path": exe_path})
            added += 1

        self.save_games()
        self.render_game_buttons()

        # Info anzeigen
        messagebox.showinfo(
            "Import abgeschlossen",
            f"{added} Spiele aus der Steam Library wurden hinzugefügt."
        )

    def render_game_buttons(self):
        if not hasattr(self, "games"):
            self.games = []

        # Weiter machen
        for child in self.games_scroll.winfo_children():
            child.destroy()

        if not self.games:
            empty_label = ctk.CTkLabel(
                self.games_scroll,
                text="Noch keine Spiele.\nKlick auf 'System'.",
                justify="left"
            )
            empty_label.pack(padx=10, pady=10, anchor="w")
            return

        for game in self.games:
            btn = ctk.CTkButton(
                self.games_scroll,
                text=game["name"],
                anchor="w",
                command=lambda g=game: self.launch_game(g)
            )
            btn.pack(padx=5, pady=4, fill="x")

            # Rechtsklick-Menü für den Button
            btn.bind("<Button-3>", lambda event,
                     g=game: self.show_game_context_menu(event, g))

        self.update_games_count_label()

    def show_game_context_menu(self, event, game):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Starten", command=lambda g=game: self.launch_game(g))
        menu.add_separator()
        menu.add_command(label="Entfernen",
                         command=lambda g=game: self.remove_game(g))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def remove_game(self, game):
        if messagebox.askyesno("Spiel entfernen", f"'{game['name']}' wirklich löschen?"):
            self.games = [g for g in self.games if g is not game]
            self.save_games()
            self.render_game_buttons()

    def add_game_dialog(self):
        file_path = filedialog.askopenfilename(
            title="Spiel auswählen",
            filetypes=[("Executable", "*.exe"), ("Alle Dateien", "*.*")]
        )
        if not file_path:
            return

        name = os.path.splitext(os.path.basename(file_path))[0]
        new_game = {"name": name, "path": file_path}
        self.games.append(new_game)
        self.save_games()
        self.render_game_buttons()

    def launch_game(self, game):
        path = game["path"]
        if not os.path.exists(path):
            messagebox.showerror(
                "Fehler", f"Datei wurde nicht gefunden:\n{path}")
            return

        try:
            os.startfile(path)   # Windows only
        except Exception as e:
            messagebox.showerror("Fehler beim Starten", str(e))


if __name__ == "__main__":
    app = GameLauncherApp()
    app.mainloop()
