import os
import json
import psutil
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

GAMES_FILE = "games.json"


class GameLauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ----- Grundkonfiguration -----
        ctk.set_appearance_mode("dark")       # Startmodus
        ctk.set_default_color_theme("dark-blue")

        self.title("Game Launcher")
        self.geometry("950x600")      # Startgröße
        self.minsize(950, 600)        # Mindestgröße

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
    # Header-Bar
    # --------------------------
    def create_header_bar(self):
        header = ctk.CTkFrame(self, height=40, corner_radius=0)
        header.grid(row=0, column=0, columnspan=2, sticky="nsew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        title_label = ctk.CTkLabel(
            header,
            text="🎮 Game Launcher  •  System Monitor",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_label.grid(row=0, column=0, padx=15, pady=5, sticky="w")

        self.appearance_mode_var = ctk.StringVar(value="dark")
        appearance_menu = ctk.CTkOptionMenu(
            header,
            values=["dark", "light", "system"],
            variable=self.appearance_mode_var,
            command=self.change_appearance_mode,
            width=120
        )
        appearance_menu.grid(row=0, column=1, padx=15, pady=5, sticky="e")

    def change_appearance_mode(self, mode: str):
        ctk.set_appearance_mode(mode)

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
        self.games_scroll = ctk.CTkScrollableFrame(self.left_frame, height=380)
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

        launchers = getattr(self, "launchers_status", self.detect_launchers())

        for name, found in launchers.items():
            status = "✅ Gefunden" if found else "❌ Nicht gefunden"
            label = ctk.CTkLabel(
                self.launchers_frame,
                text=f"{name}: {status}"
            )
            label.pack(anchor="w", padx=5, pady=2)
            
    # Bekannte Launcher erkennen
    def detect_launchers(self):
        """Prüft ein paar Standard-Pfade für bekannte Launcher."""
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get(
            "ProgramFiles(x86)", r"C:\Program Files (x86)")

        candidates = {
            "Steam": [
                os.path.join(program_files_x86, "Steam", "steam.exe"),
                os.path.join(program_files, "Steam", "steam.exe"),
            ],
            "Epic Games": [
                os.path.join(program_files_x86, "Epic Games", "Launcher",
                             "Portal", "Binaries", "Win64", "EpicGamesLauncher.exe"),
            ],
            "EA App": [
                os.path.join(program_files, "Electronic Arts",
                             "EA Desktop", "EA Desktop", "EADesktop.exe"),
            ],
            "Ubisoft Connect": [
                os.path.join(program_files_x86, "Ubisoft",
                             "Ubisoft Game Launcher", "upc.exe"),
            ],
            "Battle.net": [
                os.path.join(program_files_x86,
                             "Battle.net", "Battle.net.exe"),
            ],
            "GOG Galaxy": [
                os.path.join(program_files_x86, "GOG Galaxy",
                             "GalaxyClient.exe"),
            ],
        }

        result = {}
        for name, paths in candidates.items():
            found = any(os.path.exists(p) for p in paths)
            result[name] = found
        return result

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

        # Steam-Import-Button nur wenn Steam installiert ist
        if self.launchers_status.get("Steam", False):
            self.steam_import_btn = ctk.CTkButton(
                self.system_tab,
                text="Steam-Bibliothek importieren",
                command=self.add_steam_library_dialog
            )
            self.steam_import_btn.grid(row=6, column=0, sticky="ew", padx=10, pady=(10, 10))

        # Inhalte füllen
        self.refresh_disk_info()
        self.refresh_launcher_info()
        self.update_games_count_label()

    # --------------------------
    # Settings-Tab
    # --------------------------
    def create_settings_tab_content(self):
        self.settings_tab.grid_rowconfigure(0, weight=0)
        self.settings_tab.grid_columnconfigure(0, weight=1)

        label = ctk.CTkLabel(
            self.settings_tab,
            text="Settings (coming soon)\nHier kommen später Theme-, Pfad- und andere Optionen hin.",
            justify="left"
        )
        label.grid(row=0, column=0, sticky="nw", pady=10, padx=10)


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
