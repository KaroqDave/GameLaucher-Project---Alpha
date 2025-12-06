import os
import json
import subprocess
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

        self.title("Game Launcher & System Monitor - Alpha v0.0.1")
        self.geometry("1080x520")
        self.minsize(850, 450)

        # Grid: Zeile 0 = Header, Zeile 1 = Inhalt
        self.grid_rowconfigure(0, weight=0)   # Header
        self.grid_rowconfigure(1, weight=1)   # Hauptbereich
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        # System-Infos (statisch)
        self.total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        self.physical_cores = psutil.cpu_count(logical=False)
        self.logical_cores = psutil.cpu_count(logical=True)

        # Daten
        self.games = []
        self.load_games()

        # UI
        self.create_header_bar()
        self.create_left_panel()
        self.create_right_panel()

        # System-Monitor starten
        self.update_system_stats()

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

        #self.appearance_mode_var = ctk.StringVar(value="dark")
        #appearance_menu = ctk.CTkOptionMenu(
            #header,
            #values=["dark", "light", "system"],
            #variable=self.appearance_mode_var,
            #command=self.change_appearance_mode,
            #width=120
        #)
        #appearance_menu.grid(row=0, column=1, padx=15, pady=5, sticky="e")

    def change_appearance_mode(self, mode: str):
        ctk.set_appearance_mode(mode)

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
    # Linkes Panel – Game Liste
    # --------------------------
    def create_left_panel(self):
        self.left_frame = ctk.CTkFrame(self, corner_radius=0)
        self.left_frame.grid(row=1, column=0, sticky="nsw")

        title_label = ctk.CTkLabel(
            self.left_frame, text="Games", font=ctk.CTkFont(size=16, weight="bold")
        )
        title_label.pack(padx=10, pady=(10, 5), anchor="w")

        self.games_scroll = ctk.CTkScrollableFrame(self.left_frame, width=260, height=380)
        self.games_scroll.pack(padx=10, pady=(0, 10), fill="both", expand=True)

        self.render_game_buttons()

        add_game_btn = ctk.CTkButton(
            self.left_frame,
            text="+ Spiel hinzufügen",
            command=self.add_game_dialog
        )
        add_game_btn.pack(padx=10, pady=(0, 10), fill="x")

    def render_game_buttons(self):
        for child in self.games_scroll.winfo_children():
            child.destroy()

        if not self.games:
            empty_label = ctk.CTkLabel(
                self.games_scroll,
                # text="Noch keine Spiele.\nKlick auf '+ Spiel hinzufügen'.", // DEPRECATED
                text="Noch keine Spiele vorhanden. \nKlicke auf '+ Spiel hinzufügen', um manuel Spiele hinzuzufügen.",
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
            btn.bind("<Button-3>", lambda event, g=game: self.show_game_context_menu(event, g))

    def show_game_context_menu(self, event, game):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Starten", command=lambda g=game: self.launch_game(g))
        menu.add_separator()
        menu.add_command(label="Umbenennen", command=lambda g=game: self.rename_game(g))
        menu.add_command(label="Entfernen", command=lambda g=game: self.remove_game(g))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def rename_game(self, game):
        dialog = ctk.CTkInputDialog(
            title="Spiel umbenennen",
            text=f"Neuer Name für:\n{game['name']}"
        )
        new_name = dialog.get_input()
        if new_name:
            game["name"] = new_name.strip()
            self.save_games()
            self.render_game_buttons()

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
            messagebox.showerror("Fehler", f"Datei wurde nicht gefunden:\n{path}")
            return

        try:
            os.startfile(path)   # Windows only
        except Exception as e:
            messagebox.showerror("Fehler beim Starten", str(e))

    # --------------------------
    # Rechtes Panel – System Monitor
    # --------------------------
    def create_right_panel(self):
        self.right_frame = ctk.CTkFrame(self, corner_radius=0)
        self.right_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=10)

        self.right_frame.grid_rowconfigure(0, weight=0)
        self.right_frame.grid_rowconfigure(1, weight=0)
        self.right_frame.grid_rowconfigure(2, weight=0)
        self.right_frame.grid_rowconfigure(3, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            self.right_frame,
            text="System Monitor",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.cpu_label = ctk.CTkLabel(self.right_frame, text="CPU: - %")
        self.cpu_label.grid(row=1, column=0, sticky="w", pady=2)

        self.ram_label = ctk.CTkLabel(self.right_frame, text="RAM: - %")
        self.ram_label.grid(row=2, column=0, sticky="w", pady=2)

        # Zusatzinfos (statischer Text)
        extra_text = (
            f"Gesamt-RAM: {self.total_ram_gb:.1f} GB\n"
            f"CPU-Cores: {self.physical_cores} physisch / {self.logical_cores} logisch"
        )
        self.extra_info = ctk.CTkLabel(
            self.right_frame,
            text=extra_text,
            justify="left"
        )
        self.extra_info.grid(row=3, column=0, sticky="nw", pady=(5, 0))

    def update_system_stats(self):
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent

            self.cpu_label.configure(text=f"CPU: {cpu_percent:.1f} %")
            self.ram_label.configure(text=f"RAM: {ram:.1f} %")
        except Exception as e:
            self.cpu_label.configure(text=f"CPU: Fehler ({e})")

        # alle 1000ms (1 Sekunde) neu updaten
        self.after(1000, self.update_system_stats)


if __name__ == "__main__":
    app = GameLauncherApp()
    app.mainloop()
