import os
import json
import psutil
import customtkinter as ctk
import tkinter as tk
import winreg
import sys
import win32gui
import win32ui
import win32con
import win32api
import re
import threading
from tkinter import filedialog, messagebox
from PIL import Image
from typing import cast
from threading import Thread
import hashlib

GAMES_FILE = "games.json"
SETTINGS_FILE = "settings.json"

# Gibt den korrekten Pfad zu einer Ressource zurück (für PyInstaller-Kompatibilität)
def resource_path(relative_path: str) -> str:
    try:
        # PyInstaller packt alles nach _MEIPASS
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        # normaler Python-Run: Verzeichnis der aktuellen Datei
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

# Normalisiert einen Dateipfad (Backslashes → Slashes, Laufwerksbuchstaben groß)
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

# Liest einen String-Wert aus der Windows-Registry
def read_reg_str(root, subkey, value_name):
    try:
        with winreg.OpenKey(root, subkey) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            return str(value)
    except OSError:
        return None

# Liest den ersten existierenden Wert aus einer Liste von Registry-Kandidaten
def read_first_existing_reg_value(candidates):
    for root, subkey, value_name in candidates:
        val = read_reg_str(root, subkey, value_name)
        if val:
            return val
    return None

class GameLauncherApp(ctk.CTk):
    # Initialisiert die Hauptanwendung und alle UI-Komponenten
    def __init__(self):
        super().__init__()
        self._steam_import_running = False
        icon_path = resource_path("assets/game_launcher.ico")
        self.iconbitmap(icon_path)
        # Icon caches
        self._icon_pil_cache: dict[str, "Image.Image | None"] = {}          # exe_path -> PIL image (or None)
        self._icon_ctk_cache: dict[tuple[str, int, int], "ctk.CTkImage | None"] = {}  # (exe_path, w, h) -> CTkImage
        self._fallback_pil_image: "Image.Image | None" = None  # Cached fallback PIL image
        self._fallback_icon_ctk: "ctk.CTkImage | None" = None
        self._ui_image_refs = []  # Verhindert Garbage Collection von CTkImages
        self._icon_load_inflight: set[str] = set()  # currently loading exe paths
        self._resize_after_id: str | None = None
        self._is_resizing = False
        self._last_width = 0
        self._last_height = 0

        # ----- Grundkonfiguration -----
        ctk.set_appearance_mode("dark")       # Startmodus
        ctk.set_default_color_theme("dark-blue")

        self.title("Alpha Game Launcher")

        # Vorab Fonts erstellen (vermeidet wiederholte Objekterstellung)
        self.font_title = ctk.CTkFont(size=20, weight="bold")
        self.font_section = ctk.CTkFont(size=16, weight="bold")
        self.font_subsection = ctk.CTkFont(size=14, weight="bold")
        self.font_card_title = ctk.CTkFont(size=14, weight="bold")

        # Fenster zentrale Größe und Position
        window_width = 1200
        window_height = 800
        self.geometry(f"{window_width}x{window_height}")
        self.center_window(window_width, window_height)
        
        # Fenster nicht skalierbar machen (feste Größe für optimale Darstellung)
        self.resizable(False, False)

        # Settings laden
        self.settings = self.load_settings()
        
        # Spiele laden
        self.games = []
        self.load_games()

        self.grid_rowconfigure(0, weight=0)   # Header
        self.grid_rowconfigure(1, weight=1)   # Tabs-Bereich
        self.grid_columnconfigure(0, weight=1)  # nur eine Spalte

        # Panels
        self.create_header_bar()
        self.create_main_tabs()               # NEU statt left/right panel
        
        # Bind resize detection to pause expensive operations
        self.bind("<Configure>", self._detect_resize_start, add="+")

        # Schedule idle icon pre-warm shortly after startup
        try:
            self.after(800, self._start_idle_icon_prewarm)
        except Exception:
            pass

    # --------------------------
    # Zentriert das Fenster auf dem Bildschirm
    # --------------------------
    def center_window(self, width, height):
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")
    # --------------------------
    # Erstellt die obere Header-Leiste mit Logo und Titel
    # --------------------------
    def create_header_bar(self):
        self.header_frame = ctk.CTkFrame(self, corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)

        logo_path = resource_path("assets/game_launcher.png")

        # Einmalig laden und referenzieren, um GC zu vermeiden
        pil_logo = Image.open(logo_path)
        self.logo_image = ctk.CTkImage(
            light_image=pil_logo,
            dark_image=pil_logo,
            size=(32, 32)
        )

        self.logo_label = ctk.CTkLabel(
            self.header_frame,
            image=self.logo_image,
            text=""
        )
        self.logo_label.grid(row=0, column=0, pady=(5, 0))

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="Game Launcher - Alpha",
            font=self.font_title
        )
        self.title_label.grid(row=1, column=0)

    # --------------------------
    # Erstellt die Haupt-Tab-Ansicht (Games, System, Settings, About)
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
        self.about_tab = self.main_tabview.add("Über")

        # Inhalte aufbauen
        self.create_games_tab_content()
        self.create_system_tab_content()
        self.create_settings_tab_content()
        self.create_about_tab_content()

    # --------------------------
    # Extrahiert das Icon aus einer EXE-Datei und gibt es als PIL-Image zurück
    # --------------------------
    def extract_icon_pil(self, exe_path: str) -> Image.Image | None:
        try:
            exe_path = os.path.normpath(exe_path)
            if not os.path.exists(exe_path):
                return None

            # Disk cache: try load cached PNG first
            cache_path = self._icon_cache_file(exe_path)
            if cache_path and os.path.exists(cache_path):
                try:
                    return Image.open(cache_path).convert("RGBA")
                except Exception:
                    pass

            # Extrahiert Icon-Handles aus Datei
            large, small = win32gui.ExtractIconEx(exe_path, 0)
            hicons = large if large else small
            if not hicons:
                return None

            hicon = hicons[0]

            # Icon-Größe bestimmen
            info = win32gui.GetIconInfo(hicon)
            hbmColor = getattr(info, "hbmColor", None)
            hbmMask  = getattr(info, "hbmMask", None)

            width = height = 0
            if hbmColor:
                bmp = win32gui.GetObject(hbmColor)
                width, height = bmp.bmWidth, bmp.bmHeight
            elif hbmMask:
                bmp = win32gui.GetObject(hbmMask)
                width, height = bmp.bmWidth, bmp.bmHeight

            if width <= 0 or height <= 0:
                width = height = 256  # fallback

            # Device Contexts erstellen
            hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            hdc_mem = hdc.CreateCompatibleDC()

            # Bitmap erstellen und auswählen
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, width, height)
            hdc_mem.SelectObject(hbmp)

            # Hintergrund brush (echter GDI handle, Pylance-friendly)
            hbr = win32gui.CreateSolidBrush(win32api.RGB(0, 0, 0))
            hdc_screen = win32gui.GetDC(0)

            try:
                hdc = win32ui.CreateDCFromHandle(hdc_screen)

                # Icon zeichnen
                win32gui.DrawIconEx(
                    hdc_mem.GetSafeHdc(),
                    0, 0,
                    hicon,
                    width, height,
                    0,
                    hbr,
                    win32con.DI_NORMAL
                )

                # Bitmap -> raw bytes (BGRA)
                bmpinfo = hbmp.GetInfo()
                bmpstr = hbmp.GetBitmapBits(True)

                img = Image.frombuffer(
                    "RGB",
                    (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
                    bmpstr,
                    "raw",
                    "BGRX",
                    0,
                    1
                ).convert("RGBA")

                # Save to disk cache for future runs
                try:
                    if cache_path:
                        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                        img.save(cache_path, format="PNG")
                except Exception:
                    pass

                return img

            finally:
                # Ressourcen sauber freigeben
                win32gui.DeleteObject(hbr)
                hdc_mem.DeleteDC()
                hdc.DeleteDC()
                win32gui.ReleaseDC(0, hdc_screen)

                # Icon-Handles freigeben
                for ico in large:
                    try:
                        win32gui.DestroyIcon(ico)
                    except Exception:
                        pass
                for ico in small:
                    try:
                        win32gui.DestroyIcon(ico)
                    except Exception:
                        pass

                # Bitmaps aus IconInfo freigeben
                try:
                    if hbmColor:
                        win32gui.DeleteObject(hbmColor)
                except Exception:
                    pass
                try:
                    if hbmMask:
                        win32gui.DeleteObject(hbmMask)
                except Exception:
                    pass

        except Exception as e:
            print(f"Icon extraction failed for {exe_path}: {e}")
            return None

    # --- Icon disk cache helpers ---
    # Gibt das Verzeichnis für den Icon-Cache zurück
    def _get_icon_cache_dir(self) -> str:
        base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "AlphaGameLauncher", "IconCache")

    # Erstellt einen eindeutigen Cache-Schlüssel für eine EXE-Datei (basierend auf Pfad und Änderungszeit)
    def _icon_cache_key(self, exe_path: str) -> str:
        try:
            mtime = int(os.path.getmtime(exe_path))
        except Exception:
            mtime = 0
        h = hashlib.sha1()
        h.update((exe_path + "|" + str(mtime)).encode("utf-8", errors="ignore"))
        return h.hexdigest()

    # Gibt den vollständigen Pfad zur Cache-Datei für ein Icon zurück
    def _icon_cache_file(self, exe_path: str) -> str:
        return os.path.join(self._get_icon_cache_dir(), self._icon_cache_key(exe_path) + ".png")

    # Invalidate Icon Cache (z.B. nach Spiel-Änderung)
    def invalidate_icon_cache(self, exe_path: str):
        exe_path = os.path.normpath(exe_path)
        self._icon_pil_cache.pop(exe_path, None)

        # alle Größenvarianten entfernen
        keys_to_delete = [k for k in self._icon_ctk_cache.keys() if k[0] == exe_path]
        for k in keys_to_delete:
            self._icon_ctk_cache.pop(k, None)

    # Gibt ein Standard-Fallback-Icon als CTkImage zurück
    def get_fallback_icon(self, size=(48, 48)) -> ctk.CTkImage:
        w, h = size
        key = ("__fallback__", w, h)

        # Cache nutzen
        if key in self._icon_ctk_cache and self._icon_ctk_cache[key] is not None:
            return self._icon_ctk_cache[key]  # type: ignore

        # Load fallback PIL image only once
        if self._fallback_pil_image is None:
            try:
                p = resource_path("assets/game_launcher.png")
                self._fallback_pil_image = Image.open(p).convert("RGBA")
            except Exception:
                # Notfall: placeholder erzeugen
                self._fallback_pil_image = Image.new("RGBA", (256, 256), (50, 50, 50, 255))

        img = ctk.CTkImage(light_image=self._fallback_pil_image, dark_image=self._fallback_pil_image, size=size)
        self._icon_ctk_cache[key] = img
        return img

    # Gibt das Icon eines Spiels als CTkImage zurück (mit Caching)
    def get_game_icon_image(self, exe_path: str, size=(48, 48)) -> ctk.CTkImage:
        if not exe_path:
            return self.get_fallback_icon(size)

        exe_path = os.path.normpath(exe_path)
        w, h = size
        key = (exe_path, w, h)

        # 1) CTkImage Cache
        if key in self._icon_ctk_cache:
            return self._icon_ctk_cache[key] or self.get_fallback_icon(size)

        # 2) PIL Cache (Icon-Extraktion nur 1x pro EXE)
        if exe_path not in self._icon_pil_cache:
            pil_icon = self.extract_icon_pil(exe_path)  # <-- diese Funktion muss existieren
            self._icon_pil_cache[exe_path] = pil_icon  # kann None sein

        pil_icon = self._icon_pil_cache.get(exe_path)
        if pil_icon is None:
            self._icon_ctk_cache[key] = None
            return self.get_fallback_icon(size)

        try:
            ctk_img = ctk.CTkImage(light_image=pil_icon, dark_image=pil_icon, size=size)
            self._icon_ctk_cache[key] = ctk_img
            return ctk_img
        except Exception:
            self._icon_ctk_cache[key] = None
            return self.get_fallback_icon(size)
    
    # Erstellt den Inhalt des Games-Tabs (Spieleliste)
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
            font=self.font_section
        )
        title_label.pack(padx=10, pady=(10, 5), anchor="w")

        # Scrollbare Liste – keine feste width mehr, damit sie die Breite nutzen kann
        self.games_scroll = ctk.CTkScrollableFrame(self.left_frame)
        self.games_scroll.pack(padx=10, pady=(0, 10), fill="both", expand=True)

        # Fixe Spaltenanzahl einmal konfigurieren (vermeidet wiederholte grid-Konfiguration)
        self._games_columns = 3

        # Virtualized/progressive rendering state
        self._games_columns = 3
        self._games_chunk_size = self.settings.get("chunk_size", 12)
        self._rendered_games_count = 0
        self._scroll_poll_after_id: str | None = None

        self.render_game_buttons()

        add_game_btn = ctk.CTkButton(
            self.left_frame,
            text="Manuell Spiel hinzufügen",
            command=self.add_game_dialog
        )
        add_game_btn.pack(padx=10, pady=(0, 10), fill="x")

    # Aktualisiert die Anzeige der Spieleanzahl im System-Tab
    def update_games_count_label(self):
        if hasattr(self, "games_count_label"):
            self.games_count_label.configure(
                text=f"Installierte Spiele: {len(self.games)}"
            )

    # Aktualisiert die Laufwerksinformationen im System-Tab
    def refresh_disk_info(self):
        # Frame leeren
        for child in self.disks_frame.winfo_children():
            child.destroy()

        # Cache partitions call (expensive on some systems)
        try:
            partitions = psutil.disk_partitions(all=False)
        except Exception:
            return
            
        for part in partitions:
            if "cdrom" in part.opts.lower() or part.fstype == "":
                continue

            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue

            total_gb = usage.total / (1024 ** 3)
            used_percent = usage.percent

            label = ctk.CTkLabel(
                self.disks_frame,
                text=f"{part.device} ({part.mountpoint}) – {total_gb:.1f} GB, benutzt: {used_percent:.1f} %"
            )
            label.pack(anchor="w", padx=5, pady=2)

    # Aktualisiert die Launcher-Informationen im System-Tab
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

    # Startet den Steam-Import-Prozess in einem separaten Thread
    def import_steam_games(self):
        if getattr(self, "_steam_import_running", False):
            return  # Double-Click Schutz

        self._steam_import_running = True

        # Button sperren + Spinner zeigen
        self.steam_import_btn.configure(state="disabled", text="Import läuft...")
        self.import_progress.grid()
        self.import_progress.start()

        # Worker-Thread starten (UI bleibt responsive)
        t = Thread(target=self._steam_import_worker, daemon=True)
        t.start()

    # Worker-Thread für den Steam-Import (läuft im Hintergrund)
    def _steam_import_worker(self):
        try:
            steam_games = self.scan_steam_games()
            # Deduplicate immediately in worker
            existing_paths = {g.get("path") for g in self.games if g.get("path")}
            new_games = [g for g in steam_games if g.get("path") and g.get("path") not in existing_paths]
            result = ("ok", new_games, None)
        except Exception as e:
            result = ("err", [], str(e))

        # UI-Update MUSS im Main Thread passieren
        self.after(0, lambda: self._steam_import_done(*result))

    # Wird aufgerufen, wenn der Steam-Import abgeschlossen ist
    def _steam_import_done(self, status: str, new_games: list[dict], err: str | None):
        try:
            if status == "err":
                messagebox.showerror("Steam Import", f"Fehler beim Import:\n\n{err}")
                return

            # Add new games (already deduplicated in worker)
            self.games.extend(new_games)
            self.save_games()
            self.render_game_buttons()

            messagebox.showinfo(
                "Steam Import",
                f"Import abgeschlossen!\n\nHinzugefügt: {len(new_games)}"
            )

        finally:
            # Spinner stoppen + Button wieder aktivieren (immer)
            self.import_progress.stop()
            self.import_progress.grid_remove()
            self.steam_import_btn.configure(state="normal", text="Steam-Bibliothek importieren")
            self._steam_import_running = False

    # ----------------------------
    # Steam Scan / Detection
    # ----------------------------
    # Scannt die Steam-Bibliotheken und gibt eine Liste gefundener Spiele zurück
    def scan_steam_games(self) -> list[dict]:
        steam_path = self.get_steam_install_path()
        if not steam_path:
            return []

        libraries = self.get_steam_library_paths(steam_path)
        found_games: list[dict] = []
        # Track already found game roots to avoid duplicates early
        seen_roots: set[str] = set()

        for lib in libraries:
            steamapps = os.path.join(lib, "steamapps")
            if not os.path.isdir(steamapps):
                continue

            for file in os.listdir(steamapps):
                if not (file.startswith("appmanifest_") and file.endswith(".acf")):
                    continue

                acf_path = os.path.join(steamapps, file)
                meta = self.parse_acf_manifest(acf_path)

                name = meta.get("name")
                installdir = meta.get("installdir")

                if not name or not installdir:
                    continue

                game_root = os.path.join(lib, "steamapps", "common", installdir)
                game_root_norm = os.path.normpath(game_root).lower()
                
                # Skip if we've already processed this game root
                if game_root_norm in seen_roots:
                    continue
                seen_roots.add(game_root_norm)
                
                exe_path = self.find_game_exe(game_root, name)

                if not exe_path:
                    continue

                found_games.append({
                    "name": name,
                    "path": exe_path,
                    "source": "Steam"
                })

        return found_games
    
    # Ermittelt den Steam-Installationspfad aus der Windows-Registry
    def get_steam_install_path(self) -> str | None:
        steam_path = (
            read_reg_str(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath")
            or read_reg_str(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")
            or read_reg_str(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")
        )
        return os.path.normpath(steam_path) if steam_path else None
    
    # Liest alle Steam-Bibliothekspfade aus der libraryfolders.vdf Datei
    def get_steam_library_paths(self, steam_path: str) -> list[str]:
        paths = [os.path.normpath(steam_path)]  # Hauptlibrary immer dabei

        vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
        if not os.path.exists(vdf_path):
            return paths

        try:
            content = open(vdf_path, "r", encoding="utf-8", errors="ignore").read()

            # Findet: "path"  "D:\\SteamLibrary"
            found = re.findall(r'"path"\s*"([^"]+)"', content)
            for p in found:
                p = p.replace("\\\\", "\\")
                paths.append(os.path.normpath(p))

        except Exception as e:
            print("Failed to parse libraryfolders.vdf:", e)

        # Duplikate entfernen
        unique = []
        for p in paths:
            if p and p not in unique:
                unique.append(p)
        return unique

    # Parst eine Steam ACF-Manifest-Datei und extrahiert Spiel-Informationen
    def parse_acf_manifest(self, acf_path: str) -> dict:
        try:
            content = open(acf_path, "r", encoding="utf-8", errors="ignore").read()
            name = re.search(r'"name"\s*"([^"]+)"', content)
            installdir = re.search(r'"installdir"\s*"([^"]+)"', content)

            return {
                "name": name.group(1) if name else None,
                "installdir": installdir.group(1) if installdir else None,
            }
        except Exception as e:
            print("Failed to parse ACF:", e)
            return {"name": None, "installdir": None}
        
    # Findet die Haupt-EXE-Datei eines Spiels im angegebenen Verzeichnis (mit intelligentem Scoring)
    def find_game_exe(self, game_root: str, game_name: str = "") -> str | None:
        if not os.path.isdir(game_root):
            return None

        # Normalize game name for comparison
        game_name_clean = re.sub(r'[^a-z0-9]', '', game_name.lower()) if game_name else ""
        folder_name = os.path.basename(game_root).lower()
        folder_clean = re.sub(r'[^a-z0-9]', '', folder_name)

        candidates: list[str] = []

        # 1) Root-level .exe bevorzugen
        try:
            for f in os.listdir(game_root):
                if f.lower().endswith(".exe"):
                    candidates.append(os.path.join(game_root, f))
        except Exception:
            pass

        # 2) Rekursiv suchen in bin/binaries folders if no good root candidates
        if len(candidates) < 3:
            for root, dirs, files in os.walk(game_root):
                low = root.lower()
                # Skip common non-game folders
                if any(x in low for x in ["_commonredist", "redist", "redistributable", "vcredist", 
                                          "directx", "dotnet", "installers", "support", "_data"]):
                    continue

                for f in files:
                    if f.lower().endswith(".exe"):
                        candidates.append(os.path.join(root, f))

                # nicht komplett eskalieren
                if len(candidates) > 50:
                    break

        if not candidates:
            return None

        def score(p: str) -> int:
            n = os.path.basename(p).lower()
            n_clean = re.sub(r'[^a-z0-9]', '', n)
            
            # Immediate disqualifiers (return negative to sort to bottom)
            bad_words = ["unins", "setup", "installer", "install", "crash", "crashreport", 
                        "report", "helper", "support", "redist", "vc_redist", "vcredist",
                        "directx", "dotnet", "handler", "crs-handler", "connectinstaller",
                        "uplay", "ubisoft", "ea", "origin", "battlenet", "epicgames",
                        "steam", "launcher", "update", "patcher", "config", "settings",
                        "unreal", "unity", "activation", "register"]
            
            if any(w in n for w in bad_words):
                return -100
            
            points = 10
            
            # Bonus: exe name matches game name
            if game_name_clean and game_name_clean in n_clean:
                points += 50
            
            # Bonus: exe name matches folder name
            if folder_clean and len(folder_clean) > 3 and folder_clean in n_clean:
                points += 40
            
            # Bonus: in root directory
            if os.path.dirname(p) == os.path.normpath(game_root):
                points += 20
            
            # Bonus: in bin/binaries folder (common for actual game exe)
            parent = os.path.basename(os.path.dirname(p)).lower()
            if parent in ["bin", "binaries", "bin64", "binary"]:
                points += 15
            
            # Bonus: has x64/win64 in name (usually main game exe)
            if any(x in n for x in ["x64", "win64", "64bit"]):
                points += 5
            
            # Penalty: deeply nested
            depth = p.count(os.sep) - game_root.count(os.sep)
            if depth > 2:
                points -= (depth - 2) * 5
            
            return points

        # Sort by score (highest first)
        candidates.sort(key=score, reverse=True)
        
        # Only return if score is positive (not disqualified)
        if candidates and score(candidates[0]) > 0:
            return candidates[0]
        
        return None

    # Erkennt installierte Game-Launcher (Steam, etc.) auf dem System
    def detect_launchers(self):
        launchers = {}

        # ---- Steam ----
        steam_path = self.get_steam_install_path()
        if steam_path:
            steam_exe = os.path.join(steam_path, "Steam.exe")
            installed = os.path.exists(steam_exe)
            launchers["Steam"] = {
                "installed": installed,
                "install_path": steam_exe if installed else steam_path,
            }
        else:
            launchers["Steam"] = {"installed": False, "install_path": None}

        return launchers

    def create_system_tab_content(self):
        # Scrollbarer Container, damit Buttons bei kleiner Höhe sichtbar bleiben
        self.system_tab.grid_rowconfigure(0, weight=1)
        self.system_tab.grid_columnconfigure(0, weight=1)

        self.system_scroll = ctk.CTkScrollableFrame(self.system_tab)
        self.system_scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.system_scroll.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            self.system_scroll,
            text="System Übersicht",
            font=self.font_section
        )
        title_label.grid(row=0, column=0, sticky="w", pady=(0, 10), padx=10)

        # Spieleanzahl
        self.games_count_label = ctk.CTkLabel(
            self.system_scroll,
            text=f"Installierte Spiele: {len(self.games)}"
        )
        self.games_count_label.grid(row=1, column=0, sticky="w", pady=(0, 5), padx=10)

        # Laufwerks-Infos
        disks_title = ctk.CTkLabel(
            self.system_scroll,
            text="Laufwerke:",
            font=self.font_subsection
        )
        disks_title.grid(row=2, column=0, sticky="w", pady=(10, 5), padx=10)

        # Einfacher Frame statt verschachtelter Scrollbars, um doppelte Scrollleisten zu vermeiden
        self.disks_frame = ctk.CTkFrame(self.system_scroll)
        self.disks_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))

        # Launcher-Infos DIREKT nach den Laufwerken
        launchers_title = ctk.CTkLabel(
            self.system_scroll,
            text="Launcher auf diesem System:",
            font=self.font_subsection
        )
        launchers_title.grid(row=4, column=0, sticky="w", pady=(5, 5), padx=10)

        self.launchers_frame = ctk.CTkFrame(self.system_scroll)
        self.launchers_frame.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 10))

        # Launcher einmal erkennen und merken
        self.launchers_status = self.detect_launchers()

        # --- Steam Import Button ---
        self.steam_import_btn = ctk.CTkButton(
            self.system_scroll,
            text="Steam-Bibliothek importieren",
            command=self.import_steam_games
        )
        self.steam_import_btn.grid(row=6, column=0, sticky="ew", padx=10, pady=(10, 6))

        # --- Remove All Games Button ---
        self.remove_all_btn = ctk.CTkButton(
            self.system_scroll,
            text="Alle Spiele entfernen",
            command=self.remove_all_games,
            fg_color="#aa4444",
            hover_color="#883333"
        )
        self.remove_all_btn.grid(row=7, column=0, sticky="ew", padx=10, pady=(0, 6))

        # --- Progressbar / Spinner (indeterminate) ---
        self.import_progress = ctk.CTkProgressBar(
            self.system_scroll,
            mode="indeterminate"
        )
        self.import_progress.grid(row=8, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.import_progress.grid_remove()  # standardmäßig verstecken

        self.refresh_disk_info()
        self.refresh_launcher_info()
        self.update_games_count_label()

    # --------------------------
    # Settings-Tab
    # --------------------------
    # Ändert das Erscheinungsbild der Anwendung (Dark/Light/System)
    def change_appearance_mode(self, new_mode: str):
        # customtkinter akzeptiert "System", "Dark", "Light"
        ctk.set_appearance_mode(new_mode)

    def create_settings_tab_content(self):
        self.settings_tab.grid_rowconfigure(0, weight=0)
        self.settings_tab.grid_rowconfigure(1, weight=0)
        self.settings_tab.grid_rowconfigure(2, weight=0)  # Kein Weight
        self.settings_tab.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            self.settings_tab,
            text="Settings",
            font=self.font_section
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
        self.theme_optionmenu.grid(row=1, column=0, sticky="w", padx=80, pady=(0, 15))

        # Performance Settings - DIREKT nach Theme
        perf_label = ctk.CTkLabel(
            self.settings_tab,
            text="Performance:",
            font=self.font_subsection
        )
        perf_label.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 10))

        # Chunk Size
        chunk_label = ctk.CTkLabel(
            self.settings_tab,
            text=f"Games per Chunk: {self.settings.get('chunk_size', 12)}"
        )
        chunk_label.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 5))

        self.chunk_slider = ctk.CTkSlider(
            self.settings_tab,
            from_=6,
            to=48,
            number_of_steps=14,
            command=lambda v: self._on_chunk_size_change(int(v), chunk_label)
        )
        self.chunk_slider.set(self.settings.get("chunk_size", 12))
        self.chunk_slider.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 10))

        # Cache Size
        cache_label = ctk.CTkLabel(
            self.settings_tab,
            text=f"Icon Cache Size: {self.settings.get('cache_size_mb', 200)} MB"
        )
        cache_label.grid(row=5, column=0, sticky="w", padx=10, pady=(0, 5))

        self.cache_slider = ctk.CTkSlider(
            self.settings_tab,
            from_=50,
            to=500,
            number_of_steps=18,
            command=lambda v: self._on_cache_size_change(int(v), cache_label)
        )
        self.cache_slider.set(self.settings.get("cache_size_mb", 200))
        self.cache_slider.grid(row=6, column=0, sticky="ew", padx=10, pady=(0, 10))

        # Clear Cache Button
        clear_cache_btn = ctk.CTkButton(
            self.settings_tab,
            text="Clear Icon Cache",
            command=self._clear_icon_cache
        )
        clear_cache_btn.grid(row=7, column=0, sticky="w", padx=10, pady=(0, 10))

    # --------------------------
    # About-Tab mit App-Informationen
    # --------------------------
    def create_about_tab_content(self):
        # Scrollbarer Container für den gesamten Inhalt
        self.about_tab.grid_rowconfigure(0, weight=1)
        self.about_tab.grid_columnconfigure(0, weight=1)

        about_scroll = ctk.CTkScrollableFrame(self.about_tab)
        about_scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        about_scroll.grid_columnconfigure(0, weight=1)

        # Container-Frame für zentrierten Inhalt
        about_container = ctk.CTkFrame(about_scroll, fg_color="transparent")
        about_container.grid(row=0, column=0, sticky="", pady=10)

        # Großes App-Logo
        try:
            logo_path = resource_path("assets/game_launcher.png")
            pil_logo = Image.open(logo_path)
            self.about_logo = ctk.CTkImage(
                light_image=pil_logo,
                dark_image=pil_logo,
                size=(128, 128)
            )
            logo_label = ctk.CTkLabel(
                about_container,
                image=self.about_logo,
                text=""
            )
            logo_label.pack(pady=(20, 15))
        except Exception:
            pass

        # App-Name mit großer Schrift
        app_name = ctk.CTkLabel(
            about_container,
            text="Alpha Game Launcher",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        app_name.pack(pady=(0, 5))

        # Version
        version_label = ctk.CTkLabel(
            about_container,
            text="Version 1.0.0 Alpha",
            font=ctk.CTkFont(size=14),
            text_color="#888888"
        )
        version_label.pack(pady=(0, 20))

        # Trennlinie (visuell)
        separator = ctk.CTkFrame(about_container, height=2, fg_color="#444444")
        separator.pack(fill="x", padx=40, pady=10)

        # Beschreibung
        description = ctk.CTkLabel(
            about_container,
            text="Ein moderner Game-Launcher für Windows.\nVerwalte und starte all deine Spiele von einem Ort.",
            font=ctk.CTkFont(size=13),
            justify="center"
        )
        description.pack(pady=(10, 20))

        # Features-Box
        features_frame = ctk.CTkFrame(about_container, corner_radius=10)
        features_frame.pack(padx=20, pady=10, fill="x")

        features_title = ctk.CTkLabel(
            features_frame,
            text="✨ Features",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        features_title.pack(pady=(15, 10))

        features = [
            "✅ Steam-Bibliothek automatisch importieren",
            "✅ Manuelle Spiele hinzufügen",
            "✅ Automatische Icon-Extraktion",
            "✅ Dark/Light Theme Support",
            "✅ Icon-Cache für schnelles Laden"
        ]
        for feature in features:
            f_label = ctk.CTkLabel(
                features_frame,
                text=feature,
                font=ctk.CTkFont(size=12),
                anchor="w"
            )
            f_label.pack(pady=2, padx=20, anchor="w")

        # Spacer
        spacer = ctk.CTkLabel(features_frame, text="")
        spacer.pack(pady=5)

        # Entwickler-Info
        dev_frame = ctk.CTkFrame(about_container, corner_radius=10, fg_color="#1a1a2e")
        dev_frame.pack(padx=20, pady=(20, 10), fill="x")

        dev_title = ctk.CTkLabel(
            dev_frame,
            text="👨‍💻 Entwickelt von",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        dev_title.pack(pady=(15, 5))

        dev_name = ctk.CTkLabel(
            dev_frame,
            text="KaroqDave",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#4da6ff"
        )
        dev_name.pack(pady=(0, 5))

        github_label = ctk.CTkLabel(
            dev_frame,
            text="github.com/KaroqDave",
            font=ctk.CTkFont(size=11),
            text_color="#888888"
        )
        github_label.pack(pady=(0, 15))

        # Copyright
        copyright_label = ctk.CTkLabel(
            about_container,
            text="© 2024-2025 Alpha Game Launcher. Alle Rechte vorbehalten.",
            font=ctk.CTkFont(size=10),
            text_color="#666666"
        )
        copyright_label.pack(pady=(20, 10))


    # --------------------------
    # Settings handlers
    # --------------------------
    # Wird aufgerufen wenn die Chunk-Größe im Slider geändert wird
    def _on_chunk_size_change(self, value: int, label: ctk.CTkLabel):
        self.settings["chunk_size"] = value
        self._games_chunk_size = value
        label.configure(text=f"Games per Chunk: {value}")
        self.save_settings()

    # Wird aufgerufen wenn die Cache-Größe im Slider geändert wird
    def _on_cache_size_change(self, value: int, label: ctk.CTkLabel):
        self.settings["cache_size_mb"] = value
        label.configure(text=f"Icon Cache Size: {value} MB")
        self.save_settings()
        # Note: Pruning happens on next app start to avoid thread issues

    # Löscht den gesamten Icon-Cache (Festplatte und Speicher)
    def _clear_icon_cache(self):
        def worker():
            try:
                cache_dir = self._get_icon_cache_dir()
                if os.path.isdir(cache_dir):
                    for name in os.listdir(cache_dir):
                        path = os.path.join(cache_dir, name)
                        try:
                            os.remove(path)
                        except Exception:
                            pass
                # Clear memory caches too
                self._icon_pil_cache.clear()
                self._icon_ctk_cache.clear()
                self.after(0, lambda: messagebox.showinfo(
                    "Cache Cleared",
                    "Icon cache has been cleared successfully."
                ))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror(
                    "Error",
                    f"Failed to clear cache: {e}"
                ))
        Thread(target=worker, daemon=True).start()

    # --------------------------
    # Games speichern / laden
    # --------------------------
    # Lädt die Spieleliste aus der games.json Datei
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

    # Speichert die Spieleliste in die games.json Datei
    def save_games(self):
        try:
            with open(GAMES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.games, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Fehler beim Speichern von {GAMES_FILE}: {e}")

    # Lädt die Einstellungen aus der settings.json Datei
    def load_settings(self) -> dict:
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Fehler beim Laden von {SETTINGS_FILE}: {e}")
        return {"chunk_size": 12, "cache_size_mb": 200, "cache_max_files": 2000}

    # Speichert die Einstellungen in die settings.json Datei
    def save_settings(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Fehler beim Speichern von {SETTINGS_FILE}: {e}")

    # --------------------------
    # Functions für Games-Tab
    # --------------------------
    # Rendert die Spiele-Karten in der Games-Tab-Ansicht (progressiv in Chunks)
    def render_game_buttons(self):
        # Skip rendering if resizing for better performance
        if getattr(self, "_is_resizing", False):
            return
        
        # Scroll-Frame leeren
        # Bild-Referenzen freigeben, um unkontrolliertes Wachstum zu verhindern
        self._ui_image_refs.clear()

        for widget in self.games_scroll.winfo_children():
            widget.destroy()

        # Grid-Spalten konfigurieren (einmalig, siehe create_games_tab_content)
        columns = getattr(self, "_games_columns", 3)
        for col in range(columns):
            self.games_scroll.grid_columnconfigure(col, weight=1, uniform="games")

        if not self.games:
            # Hinweis-Label über die gesamte Breite
            label = ctk.CTkLabel(
                self.games_scroll,
                text="Noch keine Spiele.\nKlick auf 'Manuell Spiel hinzufügen' oder \ngehe auf 'System -> Bibliothek importieren'.",
            )
            label.grid(row=0, column=0, columnspan=columns, pady=10, padx=10, sticky="nsew")
            # Sicherstellen, dass evtl. Poller gestoppt ist
            self._cancel_games_scroll_poll()
            return

        # Reset progressive rendering counters
        self._rendered_games_count = 0
        # Render first chunk immediately for fast initial paint
        self._render_next_game_chunk()
        # Start polling scroll to auto-load further chunks
        self._setup_games_scroll_poll()

        # Counter aktualisieren
        self.update_games_count_label()

    # Entfernt ein einzelnes Spiel aus der Liste nach Bestätigung
    def remove_game(self, game):
        if messagebox.askyesno("Spiel entfernen", f"'{game['name']}' wirklich löschen?"):
            # Clear icon cache (memory and disk)
            if game.get("path"):
                exe_path = os.path.normpath(game["path"])
                self.invalidate_icon_cache(exe_path)
                # Delete disk cache file
                try:
                    cache_file = self._icon_cache_file(exe_path)
                    if os.path.exists(cache_file):
                        os.remove(cache_file)
                except Exception:
                    pass
            
            self.games = [g for g in self.games if g is not game]
            self.save_games()
            self.render_game_buttons()
            self.update_games_count_label()

    # Entfernt alle Spiele aus der Liste nach Bestätigung
    def remove_all_games(self):
        if not self.games:
            messagebox.showinfo("Keine Spiele", "Es sind keine Spiele zum Entfernen vorhanden.")
            return
        
        if messagebox.askyesno(
            "Alle Spiele entfernen",
            f"Möchten Sie wirklich alle {len(self.games)} Spiele entfernen?\n\nDiese Aktion kann nicht rückgängig gemacht werden."
        ):
            # Clear icon caches for all games
            for game in self.games:
                if game.get("path"):
                    exe_path = os.path.normpath(game["path"])
                    # Clear memory cache
                    self.invalidate_icon_cache(exe_path)
                    # Clear disk cache file
                    try:
                        cache_file = self._icon_cache_file(exe_path)
                        if os.path.exists(cache_file):
                            os.remove(cache_file)
                    except Exception:
                        pass
            
            self.games = []
            self.save_games()
            self.render_game_buttons()
            self.update_games_count_label()
            messagebox.showinfo("Erfolgreich", "Alle Spiele und deren Icon-Cache wurden entfernt.")

    # Öffnet einen Dialog zum manuellen Hinzufügen eines Spiels
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

    # Startet ein Spiel über die Windows startfile-Funktion
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

    # Lädt ein Icon asynchron im Hintergrund ohne die UI zu blockieren
    def _set_icon_async(self, exe_path: str | None, size: tuple[int, int], label: ctk.CTkLabel):
        # Skip während Resize für bessere Performance
        if self._is_resizing:
            return
        
        # Sofort Fallback setzen
        fallback = self.get_fallback_icon(size)
        label.configure(image=fallback)
        self._ui_image_refs.append(fallback)

        if not exe_path:
            return

        exe_path = os.path.normpath(exe_path)
        w, h = size
        key = (exe_path, w, h)

        # Wenn bereits vorbereitet im Cache → direkt setzen
        cached = self._icon_ctk_cache.get(key)
        if cached is not None:
            img = cached or fallback
            label.configure(image=img)
            self._ui_image_refs.append(img)
            return

        # Doppelte Ladevorgänge vermeiden
        if exe_path in self._icon_load_inflight:
            return

        def worker():
            try:
                self._icon_load_inflight.add(exe_path)
                # Nur die teure Extraktion vorbereiten (PIL), NICHT Tk-Objekte im Thread erstellen
                if exe_path not in self._icon_pil_cache:
                    pil_icon = self.extract_icon_pil(exe_path)
                    self._icon_pil_cache[exe_path] = pil_icon
            finally:
                # UI-Update im Main-Thread anfordern (skip if resizing for better performance)
                if not self._is_resizing:
                    self.after(0, lambda: self._on_icon_ready(exe_path, size, label))
                else:
                    self._icon_load_inflight.discard(exe_path)

        t = Thread(target=worker, daemon=True)
        t.start()

    # Wird aufgerufen wenn ein Icon fertig geladen wurde (im Main-Thread)
    def _on_icon_ready(self, exe_path: str, size: tuple[int, int], label: ctk.CTkLabel):
        # Markierung entfernen
        self._icon_load_inflight.discard(exe_path)
        # Erzeuge (oder hole) CTkImage jetzt im Main-Thread
        img = self.get_game_icon_image(exe_path, size)
        if label.winfo_exists():
            label.configure(image=img)
            self._ui_image_refs.append(img)

    # --- Progressive rendering helpers ---
    # Erstellt eine einzelne Spiele-Karte im Grid-Layout
    def _create_game_card(self, parent: ctk.CTkScrollableFrame, index: int, game: dict):
        columns = getattr(self, "_games_columns", 3)
        row, col = divmod(index, columns)

        card = ctk.CTkFrame(parent, corner_radius=0)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        icon_label = ctk.CTkLabel(card, text="")
        icon_label.pack(side="top", pady=(8, 4))
        self._set_icon_async(game.get("path"), (56, 56), icon_label)

        name_label = ctk.CTkLabel(
            card,
            text=game.get("name", "Unknown"),
            font=self.font_card_title,
            wraplength=150,
        )
        name_label.pack(side="top", padx=8, pady=(0, 4))

        button_frame = ctk.CTkFrame(card, fg_color="transparent")
        button_frame.pack(side="top", pady=(0, 8))

        play_btn = ctk.CTkButton(
            button_frame,
            text="Play",
            width=70,
            command=lambda g=game: self.launch_game(g)
        )
        play_btn.pack(side="left", padx=4)

        del_btn = ctk.CTkButton(
            button_frame,
            text="X",
            width=30,
            fg_color="#aa4444",
            hover_color="#883333",
            command=lambda g=game: self.remove_game(g)
        )
        del_btn.pack(side="left", padx=4)

    # Rendert den nächsten Chunk an Spiele-Karten
    def _render_next_game_chunk(self):
        # Skip rendering during resize for better performance
        if self._is_resizing:
            return
        if not self.games:
            return
        start = self._rendered_games_count
        end = min(start + getattr(self, "_games_chunk_size", 12), len(self.games))
        for idx in range(start, end):
            self._create_game_card(self.games_scroll, idx, self.games[idx])
        self._rendered_games_count = end
        # Trigger idle pre-warm when the first chunk is rendered
        if start == 0:
            try:
                self.after(500, self._start_idle_icon_prewarm)
            except Exception:
                pass

    # Startet den Polling-Loop für automatisches Nachladen beim Scrollen
    def _setup_games_scroll_poll(self):
        self._cancel_games_scroll_poll()
        # Periodically check if we are near the bottom of the scroll and load more
        def poll():
            try:
                # Skip expensive checks during resize
                if not self._is_resizing:
                    canvas = getattr(self.games_scroll, "_parent_canvas", None)
                    if canvas and hasattr(canvas, "yview"):
                        y1, y2 = canvas.yview()
                        # When near bottom, render next chunk
                        if y2 > 0.96 and self._rendered_games_count < len(self.games):
                            self._render_next_game_chunk()
                            # Use shorter interval when actively loading
                            next_delay = 150
                        else:
                            # Use longer interval when idle
                            next_delay = 300
                    else:
                        next_delay = 300
                else:
                    next_delay = 400  # Even longer during resize
                    
                # Keep polling while the widget exists
                if self.games_scroll.winfo_exists():
                    self._scroll_poll_after_id = self.after(next_delay, poll)
            except Exception:
                # Fail-safe: stop polling on unexpected errors
                self._scroll_poll_after_id = None
        self._scroll_poll_after_id = self.after(200, poll)

    # Stoppt den Scroll-Polling-Loop
    def _cancel_games_scroll_poll(self):
        if self._scroll_poll_after_id:
            try:
                self.after_cancel(self._scroll_poll_after_id)
            except Exception:
                pass
            self._scroll_poll_after_id = None

    # --- Resize optimization: pause expensive operations during resize ---
    # Erkennt den Start einer Fenster-Größenänderung
    def _detect_resize_start(self, event):
        # Only track main window resize
        if event.widget != self:
            return
        
        curr_w = event.width
        curr_h = event.height
        
        # Check if size actually changed
        if curr_w != self._last_width or curr_h != self._last_height:
            if not self._is_resizing:
                self._is_resizing = True

            self._last_width = curr_w
            self._last_height = curr_h

            # Cancel any pending resize-end detection
            if self._resize_after_id:
                try:
                    self.after_cancel(self._resize_after_id)
                except Exception:
                    pass

            # Schedule resize end detection with shorter delay for faster recovery
            self._resize_after_id = self.after(100, self._detect_resize_end)
    
    # Erkennt das Ende einer Fenster-Größenänderung
    def _detect_resize_end(self):
        self._is_resizing = False
        self._resize_after_id = None
        # Trigger a single update after resize ends
        try:
            self.update_idletasks()
        except Exception:
            pass

    # --- Idle icon cache pre-warm and pruning ---
    # Startet das Vorwärmen des Icon-Caches im Leerlauf
    def _start_idle_icon_prewarm(self):
        # Avoid multiple schedules
        if getattr(self, "_prewarm_started", False):
            return
        self._prewarm_started = True

        def worker():
            try:
                # Pre-warm a subset first (up to 50)
                for game in self.games[:50]:
                    p = game.get("path")
                    if not p:
                        continue
                    p = os.path.normpath(p)
                    if p not in self._icon_pil_cache:
                        img = self.extract_icon_pil(p)
                        self._icon_pil_cache[p] = img
                # Light pruning after pre-warm
                self._prune_icon_cache(
                    max_size_mb=self.settings.get("cache_size_mb", 200),
                    max_files=self.settings.get("cache_max_files", 2000)
                )
            finally:
                # No UI update needed; icons will be used on demand
                pass

        try:
            Thread(target=worker, daemon=True).start()
        except Exception:
            pass

    # Bereinigt den Icon-Cache basierend auf Größen- und Dateilimits
    def _prune_icon_cache(self, max_size_mb: int = 300, max_files: int = 5000):
        try:
            cache_dir = self._get_icon_cache_dir()
            if not os.path.isdir(cache_dir):
                return
            entries = []
            total_size = 0
            try:
                files = list(os.listdir(cache_dir))
            except Exception:
                return
            
            for name in files:
                path = os.path.join(cache_dir, name)
                try:
                    if not os.path.isfile(path):
                        continue
                    st = os.stat(path)
                    entries.append((path, st.st_mtime, st.st_size))
                    total_size += st.st_size
                except (OSError, PermissionError):
                    continue
            
            if not entries:
                return
            
            # Sort oldest first
            entries.sort(key=lambda x: x[1])
            # Prune if exceeding thresholds
            size_limit = max_size_mb * 1024 * 1024
            removed_count = 0
            while (total_size > size_limit or len(entries) > max_files) and entries:
                if removed_count > 1000:  # Safety limit
                    break
                path, _, sz = entries.pop(0)
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                        total_size -= sz
                        removed_count += 1
                except (OSError, PermissionError):
                    continue
        except Exception as e:
            print(f"Cache pruning error: {e}")

if __name__ == "__main__":
    app = GameLauncherApp()
    app.mainloop()
