import os
import json
import customtkinter as ctk
import winreg
import sys
import win32gui  # type: ignore
import win32ui  # type: ignore
import win32con  # type: ignore
import win32api  # type: ignore
import re
import hashlib
import tempfile
import shutil
from io import BytesIO
from threading import RLock, Thread
from tkinter import filedialog, messagebox
from urllib.parse import quote
from PIL import Image
import ssl

_requests_import_error: str | None = None
try:
    import requests

    try:
        import certifi
        os.environ['SSL_CERT_FILE'] = certifi.where()
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    except ImportError:
        pass
except ImportError as e:
    requests = None
    _requests_import_error = str(e)

GAMES_FILE = "games.json"
SETTINGS_FILE = "settings.json"
USER_DATA_DIR_NAME = "Alpha Game Launcher"
CACHE_DIR_NAME = "Cache"
APP_VERSION = "1.0.0.0"
DEFAULT_SETTINGS = {
    "chunk_size": 12,
    "cache_size_mb": 200,
    "cache_max_files": 2000,
    "steamgriddb_api_key": "",
    "rawg_api_key": "",
    "artwork_provider": "steamgriddb",
    "language": "de",
}
UI = {
    "bg": ("#f5f7fb", "#070b12"),
    "sidebar": ("#e9edf5", "#0b111c"),
    "surface": ("#ffffff", "#101827"),
    "surface_alt": ("#edf2f8", "#151f30"),
    "surface_hover": ("#dfe7f2", "#1b2840"),
    "border": ("#ccd6e3", "#22314a"),
    "border_hover": ("#8fb7ff", "#3d8bff"),
    "text": ("#111827", "#f6f8fb"),
    "muted": ("#5f6b7a", "#8f9caf"),
    "accent": ("#1668dc", "#2f8cff"),
    "accent_hover": ("#0f56bd", "#1f73d1"),
    "success": ("#18864b", "#28a768"),
    "success_hover": ("#126b3b", "#208452"),
    "danger": ("#c43c3c", "#d95353"),
    "danger_hover": ("#9f2d2d", "#b63f3f"),
    "warning": ("#b7791f", "#f4b942"),
}
STEAMGRIDDB_BASE_URL = "https://www.steamgriddb.com/api/v2"
LANGUAGE_NAMES = {
    "de": "Deutsch",
    "en": "English",
}
LANGUAGE_CODES = {label: code for code, label in LANGUAGE_NAMES.items()}
TRANSLATIONS = {
    "de": {
        "app_title": "Alpha Game Launcher",
        "window_title": "Alpha Game Launcher",
        "header_title": "Game Launcher - Alpha",
        "tab_games": "Spiele",
        "tab_settings": "Einstellungen",
        "tab_about": "Über",
        "games_title": "Spiele",
        "search_placeholder": "🔍 Spiele suchen...",
        "sort_label": "Sortieren:",
        "sort_name": "Name",
        "sort_favorites": "⭐ Favoriten",
        "sort_added": "Hinzugefügt",
        "scrolling": "⚡ Scrolling...",
        "add_game": "➕ Manuell Spiel hinzufügen",
        "installed_games": "Installierte Spiele: {count}",
        "system_overview": "System Übersicht",
        "launchers_on_system": "Launcher auf diesem System:",
        "steam_import": "Steam-Bibliothek importieren",
        "steam_import_running": "Import läuft...",
        "remove_all_games": "Alle Spiele entfernen",
        "path_unknown": "Pfad unbekannt",
        "found": "✅ Gefunden",
        "not_found": "❌ Nicht gefunden",
        "steam_import_error": "Fehler beim Import:\n\n{error}",
        "steam_import_done": "Import abgeschlossen!\n\nHinzugefügt: {count}",
        "settings_title": "Einstellungen",
        "language": "Sprache:",
        "theme": "Theme:",
        "performance": "Performance:",
        "steamgriddb_key": "SteamGridDB API Key:",
        "steamgriddb_placeholder": "Optional; alternativ STEAMGRIDDB_API_KEY nutzen",
        "rawg_key": "RAWG API Key:",
        "rawg_placeholder": "Optional; alternativ RAWG_API_KEY nutzen",
        "rawg_missing": "RAWG API Key fehlt",
        "library_tools": "Bibliothek:",
        "data_location": "Datenordner:",
        "cache_location": "Cache-Ordner:",
        "change_artwork": "Bild ändern",
        "refresh_artwork": "Online-Bild aktualisieren",
        "select_artwork": "Artwork auswählen",
        "artwork_files": "Bilddateien",
        "artwork_saved_title": "Artwork gespeichert",
        "artwork_saved": "Das Artwork wurde aktualisiert.",
        "artwork_failed_title": "Artwork Fehler",
        "artwork_failed": "Artwork konnte nicht gespeichert werden: {error}",
        "save_settings": "💾 Einstellungen speichern",
        "clear_image_cache": "Bild Cache leeren",
        "settings_saved_title": "✅ Gespeichert",
        "settings_saved": "Einstellungen wurden erfolgreich gespeichert!",
        "cache_cleared_title": "Cache geleert",
        "cache_cleared": "Bild Cache wurde erfolgreich geleert.",
        "cache_clear_failed_title": "Fehler",
        "cache_clear_failed": "Cache konnte nicht geleert werden: {error}",
        "about_description": "Alpha Game Launcher bündelt deine Windows-Spiele in einer schnellen, lokalen Bibliothek.\nArtwork, Einstellungen und Bibliotheksdaten bleiben transparent auf deinem PC.",
        "features": "✨ Features",
        "feature_steam": "✅ Steam-Bibliothek automatisch importieren",
        "feature_manual": "✅ Manuelle Spiele hinzufügen",
        "feature_artwork": "✅ SteamGridDB Artwork mit manuellem Override",
        "feature_theme": "✅ Dark/Light Theme Support",
        "feature_cache": "✅ Daten und Cache im Dokumente-Ordner",
        "developed_by": "👨‍💻 Entwickelt von",
        "copyright": "© 2025-2026 Alpha Game Launcher. Alle Rechte vorbehalten.",
        "no_games_found": "Keine Spiele gefunden.",
        "no_games_empty": "Noch keine Spiele.\nKlick auf '➕ Manuell Spiel hinzufügen' oder \ngehe auf 'System -> Bibliothek importieren'.",
        "remove_game_title": "Spiel entfernen",
        "remove_game_confirm": "'{name}' wirklich löschen?",
        "no_games_title": "Keine Spiele",
        "no_games_remove": "Es sind keine Spiele zum Entfernen vorhanden.",
        "remove_all_title": "Alle Spiele entfernen",
        "remove_all_confirm": "Möchten Sie wirklich alle {count} Spiele entfernen?\n\nDiese Aktion kann nicht rückgängig gemacht werden.",
        "remove_all_done_title": "Erfolgreich",
        "remove_all_done": "Alle Spiele und deren Bild-Cache wurden entfernt.",
        "back_to_list": "← Zurück zur Liste",
        "source": "📚 Quelle: {source}",
        "manual_source": "Manuell",
        "play_game": "▶ Spiel starten",
        "loading_game_info": "⏳ Lade Spiel-Informationen...",
        "game_info_error": "⚠️ {error}\n\nSpiel-Informationen konnten nicht geladen werden.",
        "rating": "⭐ Bewertung",
        "average_playtime": "⏱️ Durchschn. Spielzeit",
        "hours": "~{hours} Stunden",
        "description": "📝 Beschreibung",
        "select_game": "Spiel auswählen",
        "file_not_found_title": "Fehler",
        "file_not_found": "Datei wurde nicht gefunden:\n{path}",
        "launch_error_title": "Fehler beim Starten",
        "info_available": "ℹ Infos verfügbar",
        "play": "▶ Spielen",
        "save_games_failed": "Die Spieleliste konnte nicht gespeichert werden.",
        "save_settings_failed": "Die Einstellungen konnten nicht gespeichert werden.",
        "save_failed_title": "Speichern fehlgeschlagen",
    },
    "en": {
        "app_title": "Alpha Game Launcher",
        "window_title": "Alpha Game Launcher",
        "header_title": "Game Launcher - Alpha",
        "tab_games": "Games",
        "tab_settings": "Settings",
        "tab_about": "About",
        "games_title": "Games",
        "search_placeholder": "🔍 Search games...",
        "sort_label": "Sort:",
        "sort_name": "Name",
        "sort_favorites": "⭐ Favorites",
        "sort_added": "Added",
        "scrolling": "⚡ Scrolling...",
        "add_game": "➕ Add game manually",
        "installed_games": "Installed games: {count}",
        "system_overview": "System Overview",
        "launchers_on_system": "Launchers on this system:",
        "steam_import": "Import Steam library",
        "steam_import_running": "Importing...",
        "remove_all_games": "Remove all games",
        "path_unknown": "Path unknown",
        "found": "✅ Found",
        "not_found": "❌ Not found",
        "steam_import_error": "Import failed:\n\n{error}",
        "steam_import_done": "Import complete!\n\nAdded: {count}",
        "settings_title": "Settings",
        "language": "Language:",
        "theme": "Theme:",
        "performance": "Performance:",
        "steamgriddb_key": "SteamGridDB API key:",
        "steamgriddb_placeholder": "Optional; can also use STEAMGRIDDB_API_KEY",
        "rawg_key": "RAWG API key:",
        "rawg_placeholder": "Optional; can also use RAWG_API_KEY",
        "rawg_missing": "RAWG API key is missing",
        "library_tools": "Library:",
        "data_location": "Data folder:",
        "cache_location": "Cache folder:",
        "change_artwork": "Change artwork",
        "refresh_artwork": "Refresh online artwork",
        "select_artwork": "Select artwork",
        "artwork_files": "Image files",
        "artwork_saved_title": "Artwork saved",
        "artwork_saved": "Artwork has been updated.",
        "artwork_failed_title": "Artwork error",
        "artwork_failed": "Artwork could not be saved: {error}",
        "save_settings": "💾 Save settings",
        "clear_image_cache": "Clear image cache",
        "settings_saved_title": "✅ Saved",
        "settings_saved": "Settings saved successfully!",
        "cache_cleared_title": "Cache cleared",
        "cache_cleared": "Image cache cleared successfully.",
        "cache_clear_failed_title": "Error",
        "cache_clear_failed": "Failed to clear cache: {error}",
        "about_description": "Alpha Game Launcher keeps your Windows games in a fast local library.\nArtwork, settings, and library data stay transparent on your PC.",
        "features": "✨ Features",
        "feature_steam": "✅ Automatically import Steam library",
        "feature_manual": "✅ Add games manually",
        "feature_artwork": "✅ SteamGridDB artwork with manual override",
        "feature_theme": "✅ Dark/Light theme support",
        "feature_cache": "✅ Documents-based data and cache",
        "developed_by": "👨‍💻 Developed by",
        "copyright": "© 2025-2026 Alpha Game Launcher. All rights reserved.",
        "no_games_found": "No games found.",
        "no_games_empty": "No games yet.\nClick '➕ Add game manually' or \ngo to 'System -> Import library'.",
        "remove_game_title": "Remove game",
        "remove_game_confirm": "Really remove '{name}'?",
        "no_games_title": "No games",
        "no_games_remove": "There are no games to remove.",
        "remove_all_title": "Remove all games",
        "remove_all_confirm": "Do you really want to remove all {count} games?\n\nThis action cannot be undone.",
        "remove_all_done_title": "Success",
        "remove_all_done": "All games and their image cache were removed.",
        "back_to_list": "← Back to list",
        "source": "📚 Source: {source}",
        "manual_source": "Manual",
        "play_game": "▶ Launch game",
        "loading_game_info": "⏳ Loading game information...",
        "game_info_error": "⚠️ {error}\n\nGame information could not be loaded.",
        "rating": "⭐ Rating",
        "average_playtime": "⏱️ Average playtime",
        "hours": "~{hours} hours",
        "description": "📝 Description",
        "select_game": "Select game",
        "file_not_found_title": "Error",
        "file_not_found": "File was not found:\n{path}",
        "launch_error_title": "Launch failed",
        "info_available": "ℹ Info available",
        "play": "▶ Play",
        "save_games_failed": "The game list could not be saved.",
        "save_settings_failed": "Settings could not be saved.",
        "save_failed_title": "Save failed",
    },
}
CLEAN_TRANSLATIONS = {
    "de": {
        "app_title": "Alpha Game Launcher",
        "window_title": "Alpha Game Launcher",
        "header_title": "Alpha Game Launcher",
        "tab_games": "Bibliothek",
        "tab_settings": "Einstellungen",
        "tab_about": "Info",
        "games_title": "Bibliothek",
        "search_placeholder": "Spiele suchen...",
        "sort_label": "Sortieren",
        "sort_name": "Name",
        "sort_favorites": "Favoriten",
        "sort_added": "Hinzugefuegt",
        "scrolling": "Scrolling...",
        "add_game": "Spiel hinzufuegen",
        "installed_games": "Installierte Spiele: {count}",
        "system_overview": "Systemuebersicht",
        "launchers_on_system": "Launcher auf diesem System:",
        "steam_import": "Steam-Bibliothek importieren",
        "steam_import_running": "Import laeuft...",
        "remove_all_games": "Alle Spiele entfernen",
        "path_unknown": "Pfad unbekannt",
        "found": "Gefunden",
        "not_found": "Nicht gefunden",
        "settings_title": "Einstellungen",
        "language": "Sprache",
        "theme": "Theme",
        "library_tools": "Bibliothek",
        "data_location": "Datenordner:",
        "cache_location": "Cache-Ordner:",
        "change_artwork": "Bild aendern",
        "refresh_artwork": "Online-Bild aktualisieren",
        "save_settings": "Einstellungen speichern",
        "clear_image_cache": "Bild-Cache leeren",
        "about_description": "Alpha Game Launcher buendelt deine Windows-Spiele in einer schnellen, lokalen Bibliothek.\nArtwork, Einstellungen und Bibliotheksdaten bleiben transparent auf deinem PC.",
        "features": "Features",
        "feature_steam": "Steam-Bibliothek automatisch importieren",
        "feature_manual": "Manuelle Spiele hinzufuegen",
        "feature_artwork": "SteamGridDB Artwork mit manuellem Override",
        "feature_theme": "Dark/Light Theme Support",
        "feature_cache": "Daten und Cache im Dokumente-Ordner",
        "developed_by": "Entwickelt von",
        "no_games_found": "Keine Spiele gefunden.",
        "no_games_empty": "Noch keine Spiele.\nFuege ein Spiel hinzu oder importiere deine Steam-Bibliothek.",
        "back_to_list": "Zurueck zur Bibliothek",
        "source": "Quelle: {source}",
        "manual_source": "Manuell",
        "play_game": "Spiel starten",
        "loading_game_info": "Lade Spiel-Informationen...",
        "game_info_error": "{error}\n\nSpiel-Informationen konnten nicht geladen werden.",
        "rating": "Bewertung",
        "average_playtime": "Durchschn. Spielzeit",
        "description": "Beschreibung",
        "info_available": "Infos verfuegbar",
        "play": "Spielen",
    },
    "en": {
        "app_title": "Alpha Game Launcher",
        "window_title": "Alpha Game Launcher",
        "header_title": "Alpha Game Launcher",
        "tab_games": "Library",
        "tab_settings": "Settings",
        "tab_about": "About",
        "games_title": "Library",
        "search_placeholder": "Search games...",
        "sort_label": "Sort",
        "sort_name": "Name",
        "sort_favorites": "Favorites",
        "sort_added": "Added",
        "scrolling": "Scrolling...",
        "add_game": "Add game",
        "installed_games": "Installed games: {count}",
        "system_overview": "System overview",
        "launchers_on_system": "Launchers on this system:",
        "steam_import": "Import Steam library",
        "steam_import_running": "Importing...",
        "remove_all_games": "Remove all games",
        "path_unknown": "Path unknown",
        "found": "Found",
        "not_found": "Not found",
        "settings_title": "Settings",
        "language": "Language",
        "theme": "Theme",
        "library_tools": "Library",
        "data_location": "Data folder:",
        "cache_location": "Cache folder:",
        "change_artwork": "Change artwork",
        "refresh_artwork": "Refresh online artwork",
        "save_settings": "Save settings",
        "clear_image_cache": "Clear image cache",
        "about_description": "Alpha Game Launcher keeps your Windows games in a fast local library.\nArtwork, settings, and library data stay transparent on your PC.",
        "features": "Features",
        "feature_steam": "Automatically import Steam library",
        "feature_manual": "Add games manually",
        "feature_artwork": "SteamGridDB artwork with manual override",
        "feature_theme": "Dark/Light theme support",
        "feature_cache": "Documents-based data and cache",
        "developed_by": "Developed by",
        "no_games_found": "No games found.",
        "no_games_empty": "No games yet.\nAdd a game or import your Steam library.",
        "back_to_list": "Back to library",
        "source": "Source: {source}",
        "manual_source": "Manual",
        "play_game": "Launch game",
        "loading_game_info": "Loading game information...",
        "game_info_error": "{error}\n\nGame information could not be loaded.",
        "rating": "Rating",
        "average_playtime": "Average playtime",
        "description": "Description",
        "info_available": "Info available",
        "play": "Play",
    },
}
for _language, _values in CLEAN_TRANSLATIONS.items():
    TRANSLATIONS.setdefault(_language, {}).update(_values)

def app_data_dir() -> str:
    documents = os.path.join(os.path.expanduser("~"), "Documents")
    base = documents if os.path.isdir(documents) else os.path.expanduser("~")
    return os.path.join(base, USER_DATA_DIR_NAME)

def cache_data_dir() -> str:
    return os.path.join(app_data_dir(), CACHE_DIR_NAME)

def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

def normalize_path(p):
    if not p:
        return p

    p = os.path.normpath(p)

    drive, tail = os.path.splitdrive(p)
    if drive:
        drive = drive.upper()

    return drive + tail

def read_reg_str(root, subkey, value_name):
    try:
        with winreg.OpenKey(root, subkey) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            return str(value)
    except OSError:
        return None

def read_first_existing_reg_value(candidates):
    for root, subkey, value_name in candidates:
        val = read_reg_str(root, subkey, value_name)
        if val:
            return val
    return None

class GameLauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._steam_import_running = False
        icon_path = resource_path("assets/game_launcher.ico")
        self.iconbitmap(icon_path)

        self._icon_cache_lock = RLock()
        self._icon_pil_cache: dict[str, "Image.Image | None"] = {}
        self._icon_ctk_cache: dict[tuple[str, int, int], "ctk.CTkImage | None"] = {}
        self._fallback_pil_image: "Image.Image | None" = None
        self._fallback_icon_ctk: "ctk.CTkImage | None" = None
        self._ui_image_refs = []
        self._icon_load_inflight: set[str] = set()
        self._artwork_pil_cache: dict[tuple[str, str], "Image.Image | None"] = {}
        self._artwork_ctk_cache: dict[tuple[str, str, int, int], "ctk.CTkImage | None"] = {}
        self._artwork_load_inflight: set[tuple[str, str]] = set()
        self._resize_after_id: str | None = None
        self._is_resizing = False
        self._last_width = 0
        self._last_height = 0

        self._search_term = ""
        self._sort_mode = "name"
        self._current_game_detail = None
        self._is_scrolling = False
        self._scroll_idle_after_id: str | None = None
        self._scroll_poll_after_id: str | None = None
        self._pending_icon_updates: list[tuple[str, tuple[int, int], ctk.CTkLabel]] = []
        self._hovered_card: ctk.CTkFrame | None = None
        self._active_view = "library"
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._last_library_width = 0

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title(TRANSLATIONS[DEFAULT_SETTINGS["language"]]["window_title"])

        self.font_title = ctk.CTkFont(size=22, weight="bold")
        self.font_section = ctk.CTkFont(size=24, weight="bold")
        self.font_subsection = ctk.CTkFont(size=15, weight="bold")
        self.font_card_title = ctk.CTkFont(size=14, weight="bold")
        self.font_body = ctk.CTkFont(size=13)
        self.font_caption = ctk.CTkFont(size=11)

        window_width = 1280
        window_height = 820
        self.geometry(f"{window_width}x{window_height}")
        self.center_window(window_width, window_height)

        self.minsize(980, 680)
        self.resizable(True, True)

        self.settings = self.load_settings()

        self.games = []
        self.load_games()

        self.configure(fg_color=UI["bg"])
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.create_main_tabs()

        self.bind("<Configure>", self._detect_resize_start, add="+")

        try:
            self.after(800, self._start_idle_icon_prewarm)
        except Exception:
            pass

    def t(self, key: str, **kwargs) -> str:
        language = self.settings.get("language", DEFAULT_SETTINGS["language"])
        text = TRANSLATIONS.get(language, TRANSLATIONS["de"]).get(key, TRANSLATIONS["de"].get(key, key))
        return text.format(**kwargs) if kwargs else text

    def _language_label(self, code: str) -> str:
        return LANGUAGE_NAMES.get(code, LANGUAGE_NAMES[DEFAULT_SETTINGS["language"]])

    def _language_code(self, label: str) -> str:
        return LANGUAGE_CODES.get(label, DEFAULT_SETTINGS["language"])

    def rebuild_ui(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.title(self.t("window_title"))
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.create_main_tabs()

    def center_window(self, width, height):
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

    def _button_style(self, kind: str = "secondary") -> dict:
        styles = {
            "primary": {"fg_color": UI["accent"], "hover_color": UI["accent_hover"], "text_color": "white"},
            "success": {"fg_color": UI["success"], "hover_color": UI["success_hover"], "text_color": "white"},
            "danger": {"fg_color": UI["danger"], "hover_color": UI["danger_hover"], "text_color": "white"},
            "secondary": {"fg_color": UI["surface_alt"], "hover_color": UI["surface_hover"], "text_color": UI["text"]},
            "ghost": {"fg_color": "transparent", "hover_color": UI["surface_hover"], "text_color": UI["text"]},
        }
        return styles.get(kind, styles["secondary"])

    def _create_panel(self, parent, **kwargs):
        options = {
            "fg_color": UI["surface"],
            "border_color": UI["border"],
            "border_width": 1,
            "corner_radius": 14,
        }
        options.update(kwargs)
        return ctk.CTkFrame(parent, **options)

    def _clear_content(self):
        self._cancel_games_scroll_poll()
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def create_header_bar(self):
        self.header_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent", corner_radius=0)
        self.header_frame.pack(fill="x", padx=18, pady=(20, 16))

        logo_path = resource_path("assets/game_launcher.png")

        pil_logo = Image.open(logo_path)
        self.logo_image = ctk.CTkImage(
            light_image=pil_logo,
            dark_image=pil_logo,
            size=(42, 42)
        )

        self.logo_label = ctk.CTkLabel(
            self.header_frame,
            image=self.logo_image,
            text=""
        )
        self.logo_label.pack(side="left", padx=(0, 10))

        brand_text = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        brand_text.pack(side="left", fill="x", expand=True)

        self.title_label = ctk.CTkLabel(
            brand_text,
            text="Alpha",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=UI["text"],
            anchor="w"
        )
        self.title_label.pack(anchor="w")

        subtitle_label = ctk.CTkLabel(
            brand_text,
            text="Game Launcher",
            font=ctk.CTkFont(size=11),
            text_color=UI["muted"],
            anchor="w"
        )
        subtitle_label.pack(anchor="w")

    def _create_nav_button(self, key: str, text: str):
        btn = ctk.CTkButton(
            self.nav_frame,
            text=text,
            anchor="w",
            height=42,
            corner_radius=10,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda view=key: self.show_view(view),
            **self._button_style("ghost")
        )
        btn.pack(fill="x", pady=4)
        self._nav_buttons[key] = btn

    def _refresh_nav_state(self):
        for key, btn in self._nav_buttons.items():
            btn.configure(**self._button_style("primary" if key == self._active_view else "ghost"))

    def create_main_tabs(self):
        self.shell_frame = ctk.CTkFrame(self, fg_color=UI["bg"], corner_radius=0)
        self.shell_frame.grid(row=0, column=0, sticky="nsew")
        self.shell_frame.grid_rowconfigure(0, weight=1)
        self.shell_frame.grid_columnconfigure(1, weight=1)

        self.sidebar_frame = ctk.CTkFrame(
            self.shell_frame,
            fg_color=UI["sidebar"],
            corner_radius=0,
            width=240
        )
        self.sidebar_frame.grid(row=0, column=0, sticky="nsw")
        self.sidebar_frame.grid_propagate(False)

        self.create_header_bar()

        self.nav_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.nav_frame.pack(fill="x", padx=14, pady=(0, 12))
        self._create_nav_button("library", self.t("tab_games"))
        self._create_nav_button("settings", self.t("tab_settings"))
        self._create_nav_button("about", self.t("tab_about"))

        self.sidebar_footer = self._create_panel(self.sidebar_frame, fg_color=UI["surface_alt"], corner_radius=12)
        self.sidebar_footer.pack(side="bottom", fill="x", padx=14, pady=16)
        self.sidebar_count_label = ctk.CTkLabel(
            self.sidebar_footer,
            text=self.t("installed_games", count=len(self.games)),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=UI["text"],
            anchor="w"
        )
        self.sidebar_count_label.pack(fill="x", padx=12, pady=(12, 2))
        ctk.CTkLabel(
            self.sidebar_footer,
            text=f"Version {APP_VERSION}",
            font=self.font_caption,
            text_color=UI["muted"],
            anchor="w"
        ).pack(fill="x", padx=12, pady=(0, 12))

        self.content_frame = ctk.CTkFrame(self.shell_frame, fg_color=UI["bg"], corner_radius=0)
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=18, pady=18)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        self.show_view(getattr(self, "_active_view", "library"))

    def show_view(self, view: str):
        self._active_view = view
        self._refresh_nav_state()
        self._clear_content()

        if view == "settings":
            self.settings_tab = self.content_frame
            self.create_settings_tab_content()
        elif view == "about":
            self.about_tab = self.content_frame
            self.create_about_tab_content()
        else:
            self.games_tab = self.content_frame
            self.create_games_tab_content()

    def _create_view_header(self, parent, title: str, subtitle: str = ""):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(0, 14))
        text_frame = ctk.CTkFrame(header, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            text_frame,
            text=title,
            font=self.font_section,
            text_color=UI["text"],
            anchor="w"
        ).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(
                text_frame,
                text=subtitle,
                font=self.font_body,
                text_color=UI["muted"],
                anchor="w"
            ).pack(anchor="w", pady=(2, 0))
        return header

    def extract_icon_pil(self, exe_path: str) -> Image.Image | None:
        large = []
        small = []
        hbmColor = None
        hbmMask = None
        hdc_screen = None
        hdc = None
        hdc_mem = None
        hbr = None
        try:
            exe_path = os.path.normpath(exe_path)
            if not os.path.exists(exe_path):
                return None

            cache_path = self._icon_cache_file(exe_path)
            if cache_path and os.path.exists(cache_path):
                try:
                    return Image.open(cache_path).convert("RGBA")
                except Exception:
                    pass

            large, small = win32gui.ExtractIconEx(exe_path, 0)
            hicons = large if large else small
            if not hicons:
                return None

            hicon = hicons[0]

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
                width = height = 256

            hdc_screen = win32gui.GetDC(0)
            hdc = win32ui.CreateDCFromHandle(hdc_screen)
            hdc_mem = hdc.CreateCompatibleDC()

            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, width, height)
            hdc_mem.SelectObject(hbmp)

            hbr = win32gui.CreateSolidBrush(win32api.RGB(0, 0, 0))
            try:
                win32gui.DrawIconEx(
                    hdc_mem.GetSafeHdc(),
                    0, 0,
                    hicon,
                    width, height,
                    0,
                    hbr,
                    win32con.DI_NORMAL
                )

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

                try:
                    if cache_path:
                        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                        img.save(cache_path, format="PNG")
                except Exception:
                    pass

                return img
            finally:
                win32gui.DeleteObject(hbr)
                hdc_mem.DeleteDC()
                hdc.DeleteDC()
                win32gui.ReleaseDC(0, hdc_screen)

                for ico in large + small:
                    try:
                        win32gui.DestroyIcon(ico)
                    except Exception:
                        pass

                for bmp in [hbmColor, hbmMask]:
                    if bmp:
                        try:
                            win32gui.DeleteObject(bmp)
                        except Exception:
                            pass
        except Exception:
            return None

    def _get_icon_cache_dir(self) -> str:
        return os.path.join(cache_data_dir(), "IconCache")

    def _icon_cache_key(self, exe_path: str) -> str:
        try:
            mtime = int(os.path.getmtime(exe_path))
        except Exception:
            mtime = 0
        h = hashlib.sha1()
        h.update((exe_path + "|" + str(mtime)).encode("utf-8", errors="ignore"))
        return h.hexdigest()

    def _icon_cache_file(self, exe_path: str) -> str:
        return os.path.join(self._get_icon_cache_dir(), self._icon_cache_key(exe_path) + ".png")

    def _get_artwork_cache_dir(self) -> str:
        return os.path.join(cache_data_dir(), "ArtworkCache")

    def _get_custom_artwork_dir(self) -> str:
        return os.path.join(app_data_dir(), "Artwork")

    def _game_artwork_id(self, game: dict) -> str:
        steam_appid = str(game.get("steam_appid") or "").strip()
        if steam_appid:
            return f"steam-{steam_appid}"
        name = str(game.get("name") or game.get("path") or "unknown").strip().lower()
        h = hashlib.sha1()
        h.update(name.encode("utf-8", errors="ignore"))
        return f"name-{h.hexdigest()}"

    def _artwork_cache_file(self, game: dict, asset_type: str) -> str:
        return os.path.join(self._get_artwork_cache_dir(), f"{self._game_artwork_id(game)}-{asset_type}.png")

    def _get_steamgriddb_api_key(self) -> str:
        return (self.settings.get("steamgriddb_api_key") or os.getenv("STEAMGRIDDB_API_KEY") or "").strip()

    def _get_rawg_api_key(self) -> str:
        return (self.settings.get("rawg_api_key") or os.getenv("RAWG_API_KEY") or "").strip()

    def _steamgriddb_get(self, endpoint: str, params: dict | None = None):
        if not requests:
            return None
        api_key = self._get_steamgriddb_api_key()
        if not api_key:
            return None
        response = requests.get(
            f"{STEAMGRIDDB_BASE_URL}{endpoint}",
            headers={"Authorization": f"Bearer {api_key}"},
            params=params,
            timeout=12
        )
        if response.status_code != 200:
            return None
        data = response.json()
        if not data.get("success"):
            return None
        return data.get("data")

    def _fetch_steamgriddb_artwork_url(self, game: dict, asset_type: str = "grid") -> str | None:
        params = {
            "types": "static",
            "nsfw": "false",
            "mimes": "image/png,image/jpeg",
        }
        endpoint_kind = "grids" if asset_type == "grid" else "heroes"
        if asset_type == "grid":
            params["dimensions"] = "460x215,920x430"
        elif asset_type == "hero":
            params["dimensions"] = "1920x620,3840x1240,1600x650"

        steam_appid = str(game.get("steam_appid") or "").strip()
        if steam_appid:
            data = self._steamgriddb_get(f"/{endpoint_kind}/steam/{quote(steam_appid)}", params)
            if isinstance(data, list) and data:
                return data[0].get("url")

        name = str(game.get("name") or "").strip()
        if not name:
            return None

        matches = self._steamgriddb_get(f"/search/autocomplete/{quote(name)}")
        if not isinstance(matches, list) or not matches:
            return None

        game_id = matches[0].get("id")
        if not game_id:
            return None

        data = self._steamgriddb_get(f"/{endpoint_kind}/game/{game_id}", params)
        if isinstance(data, list) and data:
            return data[0].get("url")
        return None

    def _load_game_artwork_pil(self, game: dict, asset_type: str = "grid") -> Image.Image | None:
        override_path = game.get("artwork_path")
        if override_path and os.path.exists(override_path):
            try:
                return Image.open(override_path).convert("RGBA")
            except Exception:
                pass

        cache_file = self._artwork_cache_file(game, asset_type)
        if os.path.exists(cache_file):
            try:
                return Image.open(cache_file).convert("RGBA")
            except Exception:
                pass

        if self.settings.get("artwork_provider", "steamgriddb") != "steamgriddb":
            return None

        artwork_url = self._fetch_steamgriddb_artwork_url(game, asset_type)
        if not artwork_url or not requests:
            return None

        try:
            response = requests.get(artwork_url, timeout=15)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content)).convert("RGBA")
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            img.save(cache_file, format="PNG")
            return img
        except Exception:
            return None

    def get_game_artwork_image(self, game: dict, size=(180, 84), asset_type: str = "grid") -> ctk.CTkImage:
        artwork_id = self._game_artwork_id(game)
        w, h = size
        ctk_key = (artwork_id, asset_type, w, h)
        pil_key = (artwork_id, asset_type)

        with self._icon_cache_lock:
            if ctk_key in self._artwork_ctk_cache:
                cached = self._artwork_ctk_cache[ctk_key]
                return cached or self.get_game_icon_image(game.get("path", ""), (min(w, h), min(w, h)))
            pil_cache_hit = pil_key in self._artwork_pil_cache
            pil_artwork = self._artwork_pil_cache.get(pil_key)

        if not pil_cache_hit:
            pil_artwork = self._load_game_artwork_pil(game, asset_type)
            with self._icon_cache_lock:
                self._artwork_pil_cache[pil_key] = pil_artwork

        if pil_artwork is None:
            with self._icon_cache_lock:
                self._artwork_ctk_cache[ctk_key] = None
            return self.get_game_icon_image(game.get("path", ""), (min(w, h), min(w, h)))

        try:
            ctk_img = ctk.CTkImage(light_image=pil_artwork, dark_image=pil_artwork, size=size)
            with self._icon_cache_lock:
                self._artwork_ctk_cache[ctk_key] = ctk_img
            return ctk_img
        except Exception:
            with self._icon_cache_lock:
                self._artwork_ctk_cache[ctk_key] = None
            return self.get_game_icon_image(game.get("path", ""), (min(w, h), min(w, h)))

    def invalidate_icon_cache(self, exe_path: str):
        exe_path = os.path.normpath(exe_path)
        with self._icon_cache_lock:
            self._icon_pil_cache.pop(exe_path, None)
            self._icon_load_inflight.discard(exe_path)

            for k in [k for k in self._icon_ctk_cache if k[0] == exe_path]:
                self._icon_ctk_cache.pop(k, None)

    def invalidate_artwork_cache(self, game: dict):
        artwork_id = self._game_artwork_id(game)
        with self._icon_cache_lock:
            for key in [k for k in self._artwork_pil_cache if k[0] == artwork_id]:
                self._artwork_pil_cache.pop(key, None)
            for key in [k for k in self._artwork_ctk_cache if k[0] == artwork_id]:
                self._artwork_ctk_cache.pop(key, None)
            for key in [k for k in self._artwork_load_inflight if k[0] == artwork_id]:
                self._artwork_load_inflight.discard(key)

    def get_fallback_icon(self, size=(48, 48)) -> ctk.CTkImage:
        w, h = size
        key = ("__fallback__", w, h)

        with self._icon_cache_lock:
            cached = self._icon_ctk_cache.get(key)
            if cached is not None:
                return cached

        with self._icon_cache_lock:
            if self._fallback_pil_image is None:
                try:
                    p = resource_path("assets/game_launcher.png")
                    self._fallback_pil_image = Image.open(p).convert("RGBA")
                except Exception:
                    self._fallback_pil_image = Image.new("RGBA", (256, 256), (50, 50, 50, 255))
            fallback_pil = self._fallback_pil_image

        img = ctk.CTkImage(light_image=fallback_pil, dark_image=fallback_pil, size=size)
        with self._icon_cache_lock:
            self._icon_ctk_cache[key] = img
        return img

    def get_game_icon_image(self, exe_path: str, size=(48, 48)) -> ctk.CTkImage:
        if not exe_path:
            return self.get_fallback_icon(size)

        exe_path = os.path.normpath(exe_path)
        w, h = size
        key = (exe_path, w, h)

        with self._icon_cache_lock:
            if key in self._icon_ctk_cache:
                return self._icon_ctk_cache[key] or self.get_fallback_icon(size)
            pil_cache_hit = exe_path in self._icon_pil_cache
            pil_icon = self._icon_pil_cache.get(exe_path)

        if not pil_cache_hit:
            pil_icon = self.extract_icon_pil(exe_path)
            with self._icon_cache_lock:
                self._icon_pil_cache[exe_path] = pil_icon

        if pil_icon is None:
            with self._icon_cache_lock:
                self._icon_ctk_cache[key] = None
            return self.get_fallback_icon(size)

        try:
            ctk_img = ctk.CTkImage(light_image=pil_icon, dark_image=pil_icon, size=size)
            with self._icon_cache_lock:
                self._icon_ctk_cache[key] = ctk_img
            return ctk_img
        except Exception:
            with self._icon_cache_lock:
                self._icon_ctk_cache[key] = None
            return self.get_fallback_icon(size)

    def create_games_tab_content(self):
        self.games_tab.grid_rowconfigure(0, weight=1)
        self.games_tab.grid_columnconfigure(0, weight=1)

        self.left_frame = ctk.CTkFrame(self.games_tab, fg_color="transparent", corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        self.left_frame.grid_rowconfigure(1, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)

        header_frame = self._create_view_header(
            self.left_frame,
            self.t("games_title"),
            self.t("installed_games", count=len(self.games))
        )

        actions_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        actions_frame.pack(side="right")

        import_btn = ctk.CTkButton(
            actions_frame,
            text=self.t("steam_import"),
            height=36,
            corner_radius=10,
            command=self.import_steam_games,
            **self._button_style("secondary")
        )
        import_btn.pack(side="left", padx=(0, 8))
        self.steam_import_btn = import_btn

        add_game_btn = ctk.CTkButton(
            actions_frame,
            text=self.t("add_game"),
            command=self.add_game_dialog,
            height=36,
            corner_radius=10,
            **self._button_style("primary")
        )
        add_game_btn.pack(side="left")

        command_panel = self._create_panel(self.left_frame, fg_color=UI["surface"], corner_radius=14)
        command_panel.pack(fill="x", pady=(0, 14))
        command_panel.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            command_panel,
            placeholder_text=self.t("search_placeholder"),
            height=38,
            border_color=UI["border"],
            fg_color=UI["surface_alt"]
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        self.search_entry.bind("<KeyRelease>", self._on_search_changed)
        if self._search_term:
            self.search_entry.insert(0, self._search_term)

        sort_frame = ctk.CTkFrame(command_panel, fg_color=UI["surface_alt"], corner_radius=10)
        sort_frame.grid(row=0, column=1, sticky="e", padx=(0, 12), pady=12)

        sort_label = ctk.CTkLabel(sort_frame, text=self.t("sort_label"), text_color=UI["muted"], font=self.font_caption)
        sort_label.pack(side="left", padx=(10, 6))

        self.sort_name_btn = ctk.CTkButton(
            sort_frame,
            text=self.t("sort_name"),
            width=76,
            height=30,
            corner_radius=8,
            command=lambda: self._set_sort_mode("name")
        )
        self.sort_name_btn.pack(side="left", padx=2, pady=4)

        self.sort_fav_btn = ctk.CTkButton(
            sort_frame,
            text=self.t("sort_favorites"),
            width=104,
            height=30,
            corner_radius=8,
            command=lambda: self._set_sort_mode("favorite")
        )
        self.sort_fav_btn.pack(side="left", padx=2, pady=4)

        self.sort_date_btn = ctk.CTkButton(
            sort_frame,
            text=self.t("sort_added"),
            width=104,
            height=30,
            corner_radius=8,
            command=lambda: self._set_sort_mode("date_added")
        )
        self.sort_date_btn.pack(side="left", padx=(2, 4), pady=4)
        self._refresh_sort_buttons()

        scroll_container = self._create_panel(self.left_frame, fg_color=UI["surface"], corner_radius=16)
        scroll_container.pack(fill="both", expand=True)

        self.games_scroll = ctk.CTkScrollableFrame(scroll_container, fg_color="transparent")
        self.games_scroll.pack(fill="both", expand=True, padx=8, pady=8)

        self._scroll_canvas = self.games_scroll._parent_canvas

        self.scroll_overlay = ctk.CTkFrame(
            scroll_container,
            fg_color=UI["surface_alt"],
            corner_radius=14
        )
        self.scroll_overlay_label = ctk.CTkLabel(
            self.scroll_overlay,
            text=self.t("scrolling"),
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=UI["muted"]
        )
        self.scroll_overlay_label.pack(expand=True)

        self.scroll_overlay.place_forget()

        def _forward_scroll(e):
            scroll_amount = int(-1 * (e.delta / 120)) * 6
            self._scroll_canvas.yview_scroll(scroll_amount, "units")
            _scroll_started()
            return "break"

        self.scroll_overlay.bind("<MouseWheel>", _forward_scroll)
        self.scroll_overlay_label.bind("<MouseWheel>", _forward_scroll)

        self._last_scroll_pos = 0.0

        def _check_scroll_position():
            if hasattr(self, '_scroll_canvas') and self._scroll_canvas.winfo_exists():
                try:
                    current_pos = self._scroll_canvas.yview()[0]
                    if abs(current_pos - self._last_scroll_pos) > 0.001:
                        self._last_scroll_pos = current_pos
                        _scroll_started()
                except Exception:
                    pass
            self.after(50, _check_scroll_position)

        def _scroll_started(e=None):
            if not self._is_scrolling:
                self._is_scrolling = True

                if self._hovered_card is not None:
                    try:
                        self._hovered_card.configure(border_color=UI["border"], border_width=1)
                    except Exception:
                        pass
                    self._hovered_card = None

                self.scroll_overlay.place(x=0, y=0, relwidth=0.98, relheight=1)
                self.scroll_overlay.lift()
            if self._scroll_idle_after_id:
                try:
                    self.after_cancel(self._scroll_idle_after_id)
                except Exception:
                    pass
            self._scroll_idle_after_id = self.after(350, _scroll_stopped)

        def _scroll_stopped():
            self._is_scrolling = False
            self._scroll_idle_after_id = None

            self.scroll_overlay.place_forget()

            self.after(10, self._process_pending_icons)

        self.games_scroll.bind("<MouseWheel>", _scroll_started, add="+")
        self._scroll_canvas.bind("<MouseWheel>", _scroll_started, add="+")

        self.after(100, _check_scroll_position)

        self._games_columns = self._calculate_game_columns()
        self._games_chunk_size = self.settings.get("chunk_size", 12)
        self._rendered_games_count = 0
        self._scroll_poll_after_id: str | None = None

        self.render_game_buttons()

    def _on_search_changed(self, event=None):
        self._search_term = self.search_entry.get().lower()
        self.render_game_buttons()

    def _set_sort_mode(self, mode: str):
        self._sort_mode = mode
        self._refresh_sort_buttons()
        self.render_game_buttons()

    def _refresh_sort_buttons(self):
        if not all(hasattr(self, attr) for attr in ("sort_name_btn", "sort_fav_btn", "sort_date_btn")):
            return
        buttons = {
            "name": self.sort_name_btn,
            "favorite": self.sort_fav_btn,
            "date_added": self.sort_date_btn,
        }
        for mode, button in buttons.items():
            button.configure(**self._button_style("primary" if self._sort_mode == mode else "ghost"))

    def _calculate_game_columns(self) -> int:
        width = 0
        if hasattr(self, "games_scroll") and self.games_scroll.winfo_exists():
            try:
                width = self.games_scroll.winfo_width()
            except Exception:
                width = 0
        if width <= 1 and hasattr(self, "content_frame"):
            try:
                width = self.content_frame.winfo_width()
            except Exception:
                width = 0
        if width <= 1:
            width = self.winfo_width() - 300
        return max(2, min(5, width // 285))

    def _get_filtered_sorted_games(self) -> list[dict]:
        filtered = self.games
        if self._search_term:
            filtered = [g for g in filtered if self._search_term in g.get("name", "").lower()]

        if self._sort_mode == "name":
            filtered = sorted(filtered, key=lambda g: g.get("name", "").lower())
        elif self._sort_mode == "favorite":
            filtered = sorted(filtered, key=lambda g: (not g.get("favorite", False), g.get("name", "").lower()))
        elif self._sort_mode == "date_added":
            filtered = list(reversed(filtered))

        return filtered

    def _toggle_favorite(self, game: dict):
        game["favorite"] = not game.get("favorite", False)
        self.save_games()
        self.render_game_buttons()

    def update_games_count_label(self):
        if hasattr(self, "games_count_label"):
            self.games_count_label.configure(text=self.t("installed_games", count=len(self.games)))
        if hasattr(self, "sidebar_count_label"):
            self.sidebar_count_label.configure(text=self.t("installed_games", count=len(self.games)))

    def refresh_launcher_info(self):
        for child in self.launchers_frame.winfo_children():
            child.destroy()

        launchers = getattr(self, "launchers_status", self.detect_launchers())

        for name, info in launchers.items():
            found = info.get("installed", False)
            unknown_path = self.t("path_unknown")
            path = info.get("install_path") or unknown_path

            status = self.t("found") if found else self.t("not_found")
            text = f"{name}: {status}"
            if found and path != unknown_path:
                nice_path = normalize_path(path)
                text += f"\n  → {nice_path}"

            label = ctk.CTkLabel(
                self.launchers_frame,
                text=text,
                justify="left"
            )
            label.pack(anchor="w", padx=5, pady=2)

    def create_library_settings_content(self, parent, start_row: int) -> int:
        library_label = ctk.CTkLabel(
            parent,
            text=self.t("library_tools"),
            font=self.font_subsection
        )
        library_label.grid(row=start_row, column=0, sticky="w", padx=10, pady=(15, 10))

        self.games_count_label = ctk.CTkLabel(
            parent,
            text=self.t("installed_games", count=len(self.games))
        )
        self.games_count_label.grid(row=start_row + 1, column=0, sticky="w", padx=10, pady=(0, 6))

        data_label = ctk.CTkLabel(
            parent,
            text=f"{self.t('data_location')} {app_data_dir()}",
            font=ctk.CTkFont(size=11),
            text_color=UI["muted"]
        )
        data_label.grid(row=start_row + 2, column=0, sticky="w", padx=10, pady=(0, 4))

        cache_label = ctk.CTkLabel(
            parent,
            text=f"{self.t('cache_location')} {cache_data_dir()}",
            font=ctk.CTkFont(size=11),
            text_color=UI["muted"]
        )
        cache_label.grid(row=start_row + 3, column=0, sticky="w", padx=10, pady=(0, 10))

        launchers_title = ctk.CTkLabel(
            parent,
            text=self.t("launchers_on_system"),
            font=self.font_subsection
        )
        launchers_title.grid(row=start_row + 4, column=0, sticky="w", pady=(5, 5), padx=10)

        self.launchers_frame = ctk.CTkFrame(parent, fg_color=UI["surface_alt"], corner_radius=10)
        self.launchers_frame.grid(row=start_row + 5, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.launchers_status = self.detect_launchers()

        self.steam_import_btn = ctk.CTkButton(
            parent,
            text=self.t("steam_import"),
            command=self.import_steam_games,
            height=36,
            corner_radius=10,
            **self._button_style("secondary")
        )
        self.steam_import_btn.grid(row=start_row + 6, column=0, sticky="ew", padx=10, pady=(10, 6))

        self.remove_all_btn = ctk.CTkButton(
            parent,
            text=self.t("remove_all_games"),
            command=self.remove_all_games,
            height=36,
            corner_radius=10,
            **self._button_style("danger")
        )
        self.remove_all_btn.grid(row=start_row + 7, column=0, sticky="ew", padx=10, pady=(0, 6))

        self.import_progress = ctk.CTkProgressBar(parent, mode="indeterminate")
        self.import_progress.grid(row=start_row + 8, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.import_progress.grid_remove()

        self.refresh_launcher_info()
        self.update_games_count_label()
        return start_row + 9

    def import_steam_games(self):
        if getattr(self, "_steam_import_running", False):
            return

        self._steam_import_running = True

        self.steam_import_btn.configure(state="disabled", text=self.t("steam_import_running"))
        self.import_progress.grid()
        self.import_progress.start()

        t = Thread(target=self._steam_import_worker, daemon=True)
        t.start()

    def _steam_import_worker(self):
        try:
            steam_games = self.scan_steam_games()

            existing_paths = {g.get("path") for g in self.games if g.get("path")}
            new_games = [g for g in steam_games if g.get("path") and g.get("path") not in existing_paths]
            result = ("ok", new_games, None)
        except Exception as e:
            result = ("err", [], str(e))

        self.after(0, lambda: self._steam_import_done(*result))

    def _steam_import_done(self, status: str, new_games: list[dict], err: str | None):
        try:
            if status == "err":
                messagebox.showerror("Steam Import", self.t("steam_import_error", error=err))
                return

            self.games.extend(new_games)
            self.save_games()
            self.render_game_buttons()

            messagebox.showinfo(
                "Steam Import",
                self.t("steam_import_done", count=len(new_games))
            )
        finally:
            self.import_progress.stop()
            self.import_progress.grid_remove()
            self.steam_import_btn.configure(state="normal", text=self.t("steam_import"))
            self._steam_import_running = False

    def scan_steam_games(self) -> list[dict]:
        steam_path = self.get_steam_install_path()
        if not steam_path:
            return []

        libraries = self.get_steam_library_paths(steam_path)
        found_games: list[dict] = []

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
                steam_appid = meta.get("steam_appid") or os.path.splitext(file)[0].replace("appmanifest_", "")

                if not name or not installdir:
                    continue

                game_root = os.path.join(lib, "steamapps", "common", installdir)
                game_root_norm = os.path.normpath(game_root).lower()

                if game_root_norm in seen_roots:
                    continue
                seen_roots.add(game_root_norm)

                exe_path = self.find_game_exe(game_root, name)

                if not exe_path:
                    continue

                found_games.append({
                    "name": name,
                    "path": exe_path,
                    "source": "Steam",
                    "steam_appid": steam_appid
                })

        return found_games

    def get_steam_install_path(self) -> str | None:
        steam_path = (
            read_reg_str(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath")
            or read_reg_str(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")
            or read_reg_str(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")
        )
        return os.path.normpath(steam_path) if steam_path else None

    def get_steam_library_paths(self, steam_path: str) -> list[str]:
        paths = [os.path.normpath(steam_path)]

        vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
        if not os.path.exists(vdf_path):
            return paths

        try:
            with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            for p in re.findall(r'"path"\s*"([^"]+)"', content):
                paths.append(os.path.normpath(p.replace("\\\\", "\\")))
        except Exception:
            pass

        return list(dict.fromkeys(p for p in paths if p))

    def parse_acf_manifest(self, acf_path: str) -> dict:
        try:
            with open(acf_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            name = re.search(r'"name"\s*"([^"]+)"', content)
            installdir = re.search(r'"installdir"\s*"([^"]+)"', content)
            appid = re.search(r'"appid"\s*"([^"]+)"', content)

            return {
                "name": name.group(1) if name else None,
                "installdir": installdir.group(1) if installdir else None,
                "steam_appid": appid.group(1) if appid else None,
            }
        except Exception:
            return {"name": None, "installdir": None, "steam_appid": None}

    def find_game_exe(self, game_root: str, game_name: str = "") -> str | None:
        if not os.path.isdir(game_root):
            return None

        game_name_clean = re.sub(r'[^a-z0-9]', '', game_name.lower()) if game_name else ""
        folder_name = os.path.basename(game_root).lower()
        folder_clean = re.sub(r'[^a-z0-9]', '', folder_name)

        candidates: list[str] = []

        try:
            for f in os.listdir(game_root):
                if f.lower().endswith(".exe"):
                    candidates.append(os.path.join(game_root, f))
        except Exception:
            pass

        if len(candidates) < 3:
            for root, dirs, files in os.walk(game_root):
                low = root.lower()

                if any(x in low for x in ["_commonredist", "redist", "redistributable", "vcredist",
                                          "directx", "dotnet", "installers", "support", "_data"]):
                    continue

                for f in files:
                    if f.lower().endswith(".exe"):
                        candidates.append(os.path.join(root, f))

                if len(candidates) > 50:
                    break

        if not candidates:
            return None

        def score(p: str) -> int:
            n = os.path.basename(p).lower()
            n_clean = re.sub(r'[^a-z0-9]', '', n)

            bad_words = ["unins", "setup", "installer", "install", "crash", "crashreport",
                        "report", "helper", "support", "redist", "vc_redist", "vcredist",
                        "directx", "dotnet", "handler", "crs-handler", "connectinstaller",
                        "uplay", "ubisoft", "ea", "origin", "battlenet", "epicgames",
                        "steam", "launcher", "update", "patcher", "config", "settings",
                        "unreal", "unity", "activation", "register"]

            if any(w in n for w in bad_words):
                return -100

            points = 10

            if game_name_clean and game_name_clean in n_clean:
                points += 50

            if folder_clean and len(folder_clean) > 3 and folder_clean in n_clean:
                points += 40

            if os.path.dirname(p) == os.path.normpath(game_root):
                points += 20

            parent = os.path.basename(os.path.dirname(p)).lower()
            if parent in ["bin", "binaries", "bin64", "binary"]:
                points += 15

            if any(x in n for x in ["x64", "win64", "64bit"]):
                points += 5

            depth = p.count(os.sep) - game_root.count(os.sep)
            if depth > 2:
                points -= (depth - 2) * 5

            return points

        candidates.sort(key=score, reverse=True)

        if candidates and score(candidates[0]) > 0:
            return candidates[0]

        return None

    def detect_launchers(self):
        launchers = {}

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

    def change_appearance_mode(self, new_mode: str):
        ctk.set_appearance_mode(new_mode)

    def create_settings_tab_content(self):
        self.settings_tab.grid_rowconfigure(0, weight=1)
        self.settings_tab.grid_columnconfigure(0, weight=1)

        settings_scroll = ctk.CTkScrollableFrame(self.settings_tab, fg_color="transparent")
        settings_scroll.grid(row=0, column=0, sticky="nsew")
        settings_scroll.grid_columnconfigure(0, weight=1)

        self._create_view_header(
            settings_scroll,
            self.t("settings_title"),
            "Theme, language, API keys, cache, and library tools."
        )

        appearance_panel = self._create_panel(settings_scroll)
        appearance_panel.pack(fill="x", pady=(0, 12))
        appearance_panel.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            appearance_panel,
            text="Appearance",
            font=self.font_subsection,
            text_color=UI["text"]
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 10))

        theme_label = ctk.CTkLabel(
            appearance_panel,
            text=self.t("theme"),
            text_color=UI["muted"]
        )
        theme_label.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 10))

        saved_theme = self.settings.get("theme", "Dark")
        self.theme_var = ctk.StringVar(value=saved_theme)
        ctk.set_appearance_mode(saved_theme)

        self.theme_optionmenu = ctk.CTkOptionMenu(
            appearance_panel,
            values=["System", "Dark", "Light"],
            variable=self.theme_var,
            command=self.change_appearance_mode
        )
        self.theme_optionmenu.grid(row=1, column=1, sticky="ew", padx=(10, 16), pady=(0, 10))

        language_label = ctk.CTkLabel(
            appearance_panel,
            text=self.t("language"),
            text_color=UI["muted"]
        )
        language_label.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 16))

        self.language_var = ctk.StringVar(value=self._language_label(self.settings.get("language", DEFAULT_SETTINGS["language"])))
        self.language_optionmenu = ctk.CTkOptionMenu(
            appearance_panel,
            values=list(LANGUAGE_NAMES.values()),
            variable=self.language_var
        )
        self.language_optionmenu.grid(row=2, column=1, sticky="ew", padx=(10, 16), pady=(0, 16))

        api_panel = self._create_panel(settings_scroll)
        api_panel.pack(fill="x", pady=(0, 12))
        api_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            api_panel,
            text="Artwork and game info",
            font=self.font_subsection,
            text_color=UI["text"]
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 10))

        steamgriddb_label = ctk.CTkLabel(
            api_panel,
            text=self.t("steamgriddb_key"),
            text_color=UI["muted"]
        )
        steamgriddb_label.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 5))

        self.steamgriddb_key_entry = ctk.CTkEntry(
            api_panel,
            show="*",
            placeholder_text=self.t("steamgriddb_placeholder"),
            height=36,
            fg_color=UI["surface_alt"],
            border_color=UI["border"]
        )
        self.steamgriddb_key_entry.insert(0, self.settings.get("steamgriddb_api_key", ""))
        self.steamgriddb_key_entry.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))

        rawg_label = ctk.CTkLabel(
            api_panel,
            text=self.t("rawg_key"),
            text_color=UI["muted"]
        )
        rawg_label.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 5))

        self.rawg_key_entry = ctk.CTkEntry(
            api_panel,
            show="*",
            placeholder_text=self.t("rawg_placeholder"),
            height=36,
            fg_color=UI["surface_alt"],
            border_color=UI["border"]
        )
        self.rawg_key_entry.insert(0, self.settings.get("rawg_api_key", ""))
        self.rawg_key_entry.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 16))

        save_settings_btn = ctk.CTkButton(
            api_panel,
            text=self.t("save_settings"),
            command=self._save_all_settings,
            height=38,
            corner_radius=10,
            **self._button_style("success")
        )
        save_settings_btn.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 16))

        library_panel = self._create_panel(settings_scroll)
        library_panel.pack(fill="x", pady=(0, 12))
        library_panel.grid_columnconfigure(0, weight=1)

        clear_cache_btn = ctk.CTkButton(
            library_panel,
            text=self.t("clear_image_cache"),
            command=self._clear_icon_cache,
            height=34,
            corner_radius=10,
            **self._button_style("secondary")
        )
        clear_cache_btn.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))

        self.create_library_settings_content(library_panel, 1)

    def create_about_tab_content(self):
        self.about_tab.grid_rowconfigure(0, weight=1)
        self.about_tab.grid_columnconfigure(0, weight=1)

        about_scroll = ctk.CTkScrollableFrame(self.about_tab, fg_color="transparent")
        about_scroll.grid(row=0, column=0, sticky="nsew")
        about_scroll.grid_columnconfigure(0, weight=1)

        self._create_view_header(
            about_scroll,
            "Alpha Game Launcher",
            "A local Windows launcher for a clean, artwork-forward game library."
        )

        about_container = self._create_panel(about_scroll, fg_color=UI["surface"], corner_radius=18)
        about_container.pack(fill="x", pady=(0, 12))
        about_container.grid_columnconfigure(1, weight=1)

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
            logo_label.grid(row=0, column=0, rowspan=3, padx=24, pady=24)
        except Exception:
            pass

        app_name = ctk.CTkLabel(
            about_container,
            text="Alpha Game Launcher",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=UI["text"],
            anchor="w"
        )
        app_name.grid(row=0, column=1, sticky="sw", padx=(0, 24), pady=(28, 2))

        version_label = ctk.CTkLabel(
            about_container,
            text=f"Version {APP_VERSION}",
            font=ctk.CTkFont(size=14),
            text_color=UI["muted"],
            anchor="w"
        )
        version_label.grid(row=1, column=1, sticky="w", padx=(0, 24), pady=(0, 10))

        description = ctk.CTkLabel(
            about_container,
            text=self.t("about_description"),
            font=ctk.CTkFont(size=13),
            text_color=UI["muted"],
            justify="left",
            anchor="w"
        )
        description.grid(row=2, column=1, sticky="new", padx=(0, 24), pady=(0, 24))

        features_frame = self._create_panel(about_scroll, fg_color=UI["surface"])
        features_frame.pack(fill="x", pady=(0, 12))

        features_title = ctk.CTkLabel(
            features_frame,
            text=self.t("features"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=UI["text"]
        )
        features_title.pack(anchor="w", padx=16, pady=(14, 10))

        features = [
            self.t("feature_steam"),
            self.t("feature_manual"),
            self.t("feature_artwork"),
            self.t("feature_theme"),
            self.t("feature_cache"),
        ]
        for feature in features:
            f_label = ctk.CTkLabel(
                features_frame,
                text=feature,
                font=ctk.CTkFont(size=12),
                text_color=UI["muted"],
                anchor="w"
            )
            f_label.pack(fill="x", pady=2, padx=16)

        spacer = ctk.CTkLabel(features_frame, text="")
        spacer.pack(pady=3)

        dev_frame = self._create_panel(about_scroll, fg_color=UI["surface_alt"])
        dev_frame.pack(fill="x")

        dev_title = ctk.CTkLabel(
            dev_frame,
            text=self.t("developed_by"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=UI["muted"]
        )
        dev_title.pack(pady=(15, 5))

        dev_name = ctk.CTkLabel(
            dev_frame,
            text="KaroqDave",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=UI["accent"]
        )
        dev_name.pack(pady=(0, 5))

        github_label = ctk.CTkLabel(
            dev_frame,
            text="github.com/KaroqDave",
            font=ctk.CTkFont(size=11),
            text_color=UI["muted"]
        )
        github_label.pack(pady=(0, 15))

        copyright_label = ctk.CTkLabel(
            about_scroll,
            text=self.t("copyright"),
            font=ctk.CTkFont(size=10),
            text_color=UI["muted"]
        )
        copyright_label.pack(anchor="w", pady=(16, 0))

    def _save_all_settings(self):
        self.settings["theme"] = self.theme_var.get()
        self.settings["chunk_size"] = DEFAULT_SETTINGS["chunk_size"]
        self.settings["cache_size_mb"] = DEFAULT_SETTINGS["cache_size_mb"]
        self.settings["steamgriddb_api_key"] = self.steamgriddb_key_entry.get().strip()
        self.settings["rawg_api_key"] = self.rawg_key_entry.get().strip()
        self.settings["artwork_provider"] = "steamgriddb"
        previous_language = self.settings.get("language", DEFAULT_SETTINGS["language"])
        self.settings["language"] = self._language_code(self.language_var.get())

        self._games_chunk_size = self.settings["chunk_size"]

        self.save_settings()

        messagebox.showinfo(self.t("settings_saved_title"), self.t("settings_saved"))
        if self.settings["language"] != previous_language:
            self.rebuild_ui()

    def _clear_icon_cache(self):
        def worker():
            try:
                for cache_dir in [self._get_icon_cache_dir(), self._get_artwork_cache_dir()]:
                    if os.path.isdir(cache_dir):
                        for name in os.listdir(cache_dir):
                            path = os.path.join(cache_dir, name)
                            try:
                                os.remove(path)
                            except Exception:
                                pass

                def finish_clear():
                    with self._icon_cache_lock:
                        self._icon_pil_cache.clear()
                        self._icon_ctk_cache.clear()
                        self._icon_load_inflight.clear()
                        self._artwork_pil_cache.clear()
                        self._artwork_ctk_cache.clear()
                        self._artwork_load_inflight.clear()
                    messagebox.showinfo(
                        self.t("cache_cleared_title"),
                        self.t("cache_cleared")
                    )

                self.after(0, finish_clear)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror(
                    self.t("cache_clear_failed_title"),
                    self.t("cache_clear_failed", error=e)
                ))
        Thread(target=worker, daemon=True).start()

    def _state_file_path(self, filename: str) -> str:
        return os.path.join(app_data_dir(), filename)

    def _legacy_state_candidates(self, filename: str) -> list[str]:
        candidates = [
            os.path.abspath(filename),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), filename),
        ]
        seen = set()
        result = []
        for path in candidates:
            norm = os.path.normcase(os.path.abspath(path))
            if norm not in seen:
                seen.add(norm)
                result.append(path)
        return result

    def _load_json_state(self, filename: str, default):
        state_path = self._state_file_path(filename)
        paths_to_try = [state_path]
        if not os.path.exists(state_path):
            paths_to_try.extend(self._legacy_state_candidates(filename))

        for path in paths_to_try:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if path != state_path:
                    self._write_json_state(filename, data)
                return data
            except Exception as e:
                print(f"Failed to load {filename} from {path}: {e}", file=sys.stderr)

        return default.copy() if isinstance(default, dict) else list(default)

    def _write_json_state(self, filename: str, data) -> bool:
        state_path = self._state_file_path(filename)
        state_dir = os.path.dirname(state_path)
        try:
            os.makedirs(state_dir, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(prefix=f".{filename}.", suffix=".tmp", dir=state_dir, text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                    f.write("\n")
                os.replace(temp_path, state_path)
                return True
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
        except Exception as e:
            print(f"Failed to save {filename} to {state_path}: {e}", file=sys.stderr)
            return False

    def load_games(self):
        games = self._load_json_state(GAMES_FILE, [])
        self.games = games if isinstance(games, list) else []

    def save_games(self):
        if not self._write_json_state(GAMES_FILE, self.games):
            messagebox.showerror(self.t("save_failed_title"), self.t("save_games_failed"))

    def load_settings(self) -> dict:
        loaded = self._load_json_state(SETTINGS_FILE, DEFAULT_SETTINGS)
        settings = DEFAULT_SETTINGS.copy()
        if isinstance(loaded, dict):
            settings.update(loaded)
        return settings

    def save_settings(self):
        if not self._write_json_state(SETTINGS_FILE, self.settings):
            messagebox.showerror(self.t("save_failed_title"), self.t("save_settings_failed"))

    def render_game_buttons(self):
        if getattr(self, "_is_resizing", False):
            return

        self._ui_image_refs.clear()

        for widget in self.games_scroll.winfo_children():
            widget.destroy()

        columns = self._calculate_game_columns()
        self._games_columns = columns
        for col in range(columns):
            self.games_scroll.grid_columnconfigure(col, weight=1, uniform="games")

        self._display_games = self._get_filtered_sorted_games()

        if not self._display_games:
            msg = self.t("no_games_found") if self._search_term else self.t("no_games_empty")
            empty = self._create_panel(self.games_scroll, fg_color=UI["surface_alt"], corner_radius=14)
            empty.grid(row=0, column=0, columnspan=columns, pady=22, padx=12, sticky="nsew")
            label = ctk.CTkLabel(
                empty,
                text=msg,
                font=ctk.CTkFont(size=15, weight="bold"),
                text_color=UI["muted"],
                justify="center"
            )
            label.pack(expand=True, fill="both", padx=20, pady=34)

            self._cancel_games_scroll_poll()
            return

        self._rendered_games_count = 0

        self._render_next_game_chunk()

        self._setup_games_scroll_poll()

        self.update_games_count_label()

    def remove_game(self, game):
        if messagebox.askyesno(self.t("remove_game_title"), self.t("remove_game_confirm", name=game["name"])):
            self.invalidate_artwork_cache(game)
            for asset_type in ["grid", "hero"]:
                try:
                    cache_file = self._artwork_cache_file(game, asset_type)
                    if os.path.exists(cache_file):
                        os.remove(cache_file)
                except Exception:
                    pass

            if game.get("path"):
                exe_path = os.path.normpath(game["path"])
                self.invalidate_icon_cache(exe_path)

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

    def remove_all_games(self):
        if not self.games:
            messagebox.showinfo(self.t("no_games_title"), self.t("no_games_remove"))
            return

        if messagebox.askyesno(
            self.t("remove_all_title"),
            self.t("remove_all_confirm", count=len(self.games))
        ):
            for game in self.games:
                self.invalidate_artwork_cache(game)
                for asset_type in ["grid", "hero"]:
                    try:
                        cache_file = self._artwork_cache_file(game, asset_type)
                        if os.path.exists(cache_file):
                            os.remove(cache_file)
                    except Exception:
                        pass

                if game.get("path"):
                    exe_path = os.path.normpath(game["path"])

                    self.invalidate_icon_cache(exe_path)

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
            messagebox.showinfo(self.t("remove_all_done_title"), self.t("remove_all_done"))

    def _show_game_detail(self, game: dict):
        self._current_game_detail = game

        for widget in self.left_frame.winfo_children():
            widget.destroy()

        detail_scroll = ctk.CTkScrollableFrame(self.left_frame, fg_color="transparent")
        detail_scroll.pack(fill="both", expand=True)

        back_btn = ctk.CTkButton(
            detail_scroll,
            text=self.t("back_to_list"),
            command=self._hide_game_detail,
            width=150,
            height=36,
            corner_radius=10,
            **self._button_style("secondary")
        )
        back_btn.pack(anchor="w", pady=(0, 14))

        header_frame = self._create_panel(detail_scroll, fg_color=UI["surface"], corner_radius=18)
        header_frame.pack(fill="x", pady=(0, 16))
        header_frame.grid_columnconfigure(1, weight=1)

        icon_label = ctk.CTkLabel(header_frame, text="", width=300, height=140)
        icon_label.grid(row=0, column=0, rowspan=2, sticky="nw", padx=18, pady=18)
        icon_label.pack_propagate(False)
        self._set_game_artwork_async(game, (300, 140), icon_label, "hero")

        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 18), pady=(22, 8))

        title_label = ctk.CTkLabel(
            title_frame,
            text=game.get("name", "Unknown"),
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=UI["text"],
            wraplength=520,
            anchor="w",
            justify="left"
        )
        title_label.pack(anchor="w", fill="x")

        source_label = ctk.CTkLabel(
            title_frame,
            text=self.t("source", source=game.get("source", self.t("manual_source"))),
            font=ctk.CTkFont(size=12),
            text_color=UI["muted"]
        )
        source_label.pack(anchor="w", pady=(5, 0))

        action_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        action_frame.grid(row=1, column=1, sticky="sew", padx=(0, 18), pady=(0, 18))

        play_btn = ctk.CTkButton(
            action_frame,
            text=self.t("play_game"),
            command=lambda: self.launch_game(game),
            height=40,
            width=150,
            corner_radius=10,
            font=ctk.CTkFont(size=14, weight="bold"),
            **self._button_style("success")
        )
        play_btn.pack(side="left", padx=(0, 8))

        change_art_btn = ctk.CTkButton(
            action_frame,
            text=self.t("change_artwork"),
            command=lambda g=game: self.change_game_artwork(g),
            height=32,
            width=150,
            corner_radius=10,
            **self._button_style("secondary")
        )
        change_art_btn.pack(side="left", padx=(0, 8))

        refresh_art_btn = ctk.CTkButton(
            action_frame,
            text=self.t("refresh_artwork"),
            command=lambda g=game: self.refresh_game_artwork(g),
            height=32,
            width=150,
            corner_radius=10,
            **self._button_style("secondary")
        )
        refresh_art_btn.pack(side="left")

        loading_label = ctk.CTkLabel(
            detail_scroll,
            text=self.t("loading_game_info"),
            font=ctk.CTkFont(size=13),
            text_color=UI["muted"]
        )
        loading_label.pack(pady=20)

        def fetch_info():
            info = self._fetch_game_info(game.get("name", ""))
            self.after(0, lambda: self._display_game_info(detail_scroll, loading_label, info))

        Thread(target=fetch_info, daemon=True).start()

    def _hide_game_detail(self):
        self._current_game_detail = None
        self.show_view("library")

    def _fetch_game_info(self, game_name: str) -> dict:
        if not requests:
            error_msg = f"Request Import Fehler: {_requests_import_error}" if _requests_import_error else "requests library nicht installiert"
            return {"error": error_msg}
        rawg_api_key = self._get_rawg_api_key()
        if not rawg_api_key:
            return {"error": self.t("rawg_missing")}

        try:
            search_name = game_name

            search_name = re.sub(r'([a-z])(\d)', r'\1 \2', search_name, flags=re.IGNORECASE)

            for suffix in [" Enhanced", " Remastered", " Edition", " GOTY", " Complete", " Definitive"]:
                if suffix.lower() in search_name.lower():
                    search_name = search_name.replace(suffix, "")

            search_attempts = [
                search_name.strip(),
                search_name.strip().replace("_", " ").replace("-", " "),
                search_name.strip().title(),
            ]

            for attempt in search_attempts:
                url = "https://api.rawg.io/api/games"
                params = {
                    "key": rawg_api_key,
                    "search": attempt,
                    "page_size": 5,
                }

                response = requests.get(url, params=params, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("results") and len(data["results"]) > 0:
                        game_data = data["results"][0]

                        game_id = game_data.get("id")
                        detail_url = f"https://api.rawg.io/api/games/{game_id}"
                        detail_params = {"key": rawg_api_key}
                        detail_response = requests.get(detail_url, params=detail_params, timeout=10)

                        if detail_response.status_code == 200:
                            detailed_data = detail_response.json()
                            return {
                                "name": detailed_data.get("name", game_name),
                                "released": detailed_data.get("released", "Unbekannt"),
                                "developers": [d.get("name") for d in detailed_data.get("developers", [])],
                                "publishers": [p.get("name") for p in detailed_data.get("publishers", [])],
                                "description": detailed_data.get("description_raw", ""),
                                "playtime": detailed_data.get("playtime", 0),
                                "rating": detailed_data.get("rating", 0),
                                "platforms": [p.get("platform", {}).get("name") for p in detailed_data.get("platforms", [])],
                                "genres": [g.get("name") for g in detailed_data.get("genres", [])],
                                "metacritic": detailed_data.get("metacritic"),
                            }

                        return {
                            "name": game_data.get("name", game_name),
                            "released": game_data.get("released", "Unbekannt"),
                            "rating": game_data.get("rating", 0),
                            "playtime": game_data.get("playtime", 0),
                            "genres": [g.get("name") for g in game_data.get("genres", [])],
                        }

            return {"error": f"Game '{game_name}' not found in database"}
        except requests.exceptions.Timeout:
            return {"error": "Request timed out"}
        except requests.exceptions.RequestException as e:
            return {"error": f"Network error: {str(e)}"}
        except Exception as e:
            return {"error": f"Failed to fetch info: {str(e)}"}

    def _display_game_info(self, parent: ctk.CTkScrollableFrame, loading_label: ctk.CTkLabel, info: dict):
        loading_label.destroy()

        if info.get("error"):
            error_label = ctk.CTkLabel(
                parent,
                text=self.t("game_info_error", error=info["error"]),
                font=ctk.CTkFont(size=13),
                text_color=UI["danger"]
            )
            error_label.pack(pady=20)
            return

        sections = [
            ("📅 Veröffentlichungsdatum", info.get("released", "Unbekannt")),
            ("👨‍💻 Entwickler", ", ".join(info.get("developers", [])) or "Unbekannt"),
            ("🏭 Publisher", ", ".join(info.get("publishers", [])) or "Unbekannt"),
            ("🎮 Genres", ", ".join(info.get("genres", [])) or "Unbekannt"),
            ("💻 Plattformen", ", ".join(info.get("platforms", [])[:5]) or "Unbekannt"),
        ]

        for title, value in sections:
            if value and value != "Unbekannt":
                section_frame = self._create_panel(parent, fg_color=UI["surface"], corner_radius=12)
                section_frame.pack(fill="x", pady=5)

                title_label = ctk.CTkLabel(
                    section_frame,
                    text=title,
                    font=ctk.CTkFont(size=13, weight="bold")
                )
                title_label.pack(anchor="w", padx=15, pady=(10, 2))

                value_label = ctk.CTkLabel(
                    section_frame,
                    text=value,
                    font=ctk.CTkFont(size=12),
                    wraplength=800,
                    justify="left"
                )
                value_label.pack(anchor="w", padx=15, pady=(0, 10))

        stats_frame = self._create_panel(parent, fg_color=UI["surface"], corner_radius=12)
        stats_frame.pack(fill="x", pady=10)

        stats_inner = ctk.CTkFrame(stats_frame, fg_color="transparent")
        stats_inner.pack(fill="x", padx=15, pady=10)

        if info.get("rating"):
            rating_frame = ctk.CTkFrame(stats_inner, fg_color="transparent")
            rating_frame.pack(side="left", padx=(0, 20))

            rating_label = ctk.CTkLabel(
                rating_frame,
                text=self.t("rating"),
                font=ctk.CTkFont(size=12, weight="bold")
            )
            rating_label.pack()

            rating_value = ctk.CTkLabel(
                rating_frame,
                text=f"{info['rating']:.1f} / 5.0",
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=UI["warning"]
            )
            rating_value.pack()

        if info.get("playtime"):
            playtime_frame = ctk.CTkFrame(stats_inner, fg_color="transparent")
            playtime_frame.pack(side="left", padx=(0, 20))

            playtime_label = ctk.CTkLabel(
                playtime_frame,
                text=self.t("average_playtime"),
                font=ctk.CTkFont(size=12, weight="bold")
            )
            playtime_label.pack()

            playtime_value = ctk.CTkLabel(
                playtime_frame,
                text=self.t("hours", hours=info["playtime"]),
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=UI["accent"]
            )
            playtime_value.pack()

        if info.get("metacritic"):
            metacritic_frame = ctk.CTkFrame(stats_inner, fg_color="transparent")
            metacritic_frame.pack(side="left")

            metacritic_label = ctk.CTkLabel(
                metacritic_frame,
                text="🎯 Metacritic",
                font=ctk.CTkFont(size=12, weight="bold")
            )
            metacritic_label.pack()

            score = info['metacritic']
            color = UI["success"] if score >= 75 else UI["warning"] if score >= 50 else UI["danger"]

            metacritic_value = ctk.CTkLabel(
                metacritic_frame,
                text=str(score),
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=color
            )
            metacritic_value.pack()

        if info.get("description"):
            desc_frame = self._create_panel(parent, fg_color=UI["surface"], corner_radius=12)
            desc_frame.pack(fill="both", expand=True, pady=10)

            desc_title = ctk.CTkLabel(
                desc_frame,
                text=self.t("description"),
                font=ctk.CTkFont(size=13, weight="bold")
            )
            desc_title.pack(anchor="w", padx=15, pady=(10, 5))

            desc_text = info["description"]
            if len(desc_text) > 800:
                desc_text = desc_text[:800] + "..."

            desc_label = ctk.CTkLabel(
                desc_frame,
                text=desc_text,
                font=ctk.CTkFont(size=12),
                wraplength=900,
                justify="left"
            )
            desc_label.pack(anchor="w", padx=15, pady=(0, 15))

    def add_game_dialog(self):
        file_path = filedialog.askopenfilename(
            title=self.t("select_game"),
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
                self.t("file_not_found_title"), self.t("file_not_found", path=path))
            return

        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showerror(self.t("launch_error_title"), str(e))

    def change_game_artwork(self, game: dict):
        file_path = filedialog.askopenfilename(
            title=self.t("select_artwork"),
            filetypes=[
                (self.t("artwork_files"), "*.png;*.jpg;*.jpeg;*.webp"),
                ("All files", "*.*"),
            ]
        )
        if not file_path:
            return

        try:
            os.makedirs(self._get_custom_artwork_dir(), exist_ok=True)
            custom_path = os.path.join(self._get_custom_artwork_dir(), f"{self._game_artwork_id(game)}.png")
            Image.open(file_path).convert("RGBA").save(custom_path, format="PNG")
            game["artwork_path"] = custom_path
            self.invalidate_artwork_cache(game)
            self.save_games()
            messagebox.showinfo(self.t("artwork_saved_title"), self.t("artwork_saved"))
            self._show_game_detail(game)
        except Exception as e:
            messagebox.showerror(self.t("artwork_failed_title"), self.t("artwork_failed", error=e))

    def refresh_game_artwork(self, game: dict):
        old_override = game.pop("artwork_path", None)
        if old_override and os.path.exists(old_override):
            try:
                os.remove(old_override)
            except Exception:
                pass

        for asset_type in ["grid", "hero"]:
            try:
                cache_file = self._artwork_cache_file(game, asset_type)
                if os.path.exists(cache_file):
                    os.remove(cache_file)
            except Exception:
                pass

        self.invalidate_artwork_cache(game)
        self.save_games()
        self._show_game_detail(game)

    def _set_game_artwork_async(self, game: dict, size: tuple[int, int], label: ctk.CTkLabel, asset_type: str = "grid"):
        if self._is_resizing or self._is_scrolling:
            return

        fallback_size = (min(size), min(size))
        fallback = self.get_fallback_icon(fallback_size)
        label.configure(image=fallback)
        self._ui_image_refs.append(fallback)

        artwork_id = self._game_artwork_id(game)
        ctk_key = (artwork_id, asset_type, size[0], size[1])
        pil_key = (artwork_id, asset_type)

        with self._icon_cache_lock:
            if ctk_key in self._artwork_ctk_cache:
                cached = self._artwork_ctk_cache[ctk_key]
                img = cached or fallback
                label.configure(image=img)
                self._ui_image_refs.append(img)
                return
            if pil_key in self._artwork_load_inflight:
                return
            self._artwork_load_inflight.add(pil_key)

        def worker():
            try:
                with self._icon_cache_lock:
                    needs_load = pil_key not in self._artwork_pil_cache
                if needs_load:
                    pil_artwork = self._load_game_artwork_pil(game, asset_type)
                    with self._icon_cache_lock:
                        self._artwork_pil_cache[pil_key] = pil_artwork
            finally:
                if not self._is_resizing and not self._is_scrolling:
                    self.after(0, lambda: self._on_artwork_ready(game, size, label, asset_type))
                else:
                    with self._icon_cache_lock:
                        self._artwork_load_inflight.discard(pil_key)

        Thread(target=worker, daemon=True).start()

    def _on_artwork_ready(self, game: dict, size: tuple[int, int], label: ctk.CTkLabel, asset_type: str):
        artwork_id = self._game_artwork_id(game)
        pil_key = (artwork_id, asset_type)
        with self._icon_cache_lock:
            self._artwork_load_inflight.discard(pil_key)
        if not label.winfo_exists():
            return
        with self._icon_cache_lock:
            pil_artwork = self._artwork_pil_cache.get(pil_key)
        if pil_artwork is None:
            self._set_icon_async(game.get("path"), (min(size), min(size)), label)
            return
        img = self.get_game_artwork_image(game, size, asset_type)
        label.configure(image=img)
        self._ui_image_refs.append(img)

    def _set_icon_async(self, exe_path: str | None, size: tuple[int, int], label: ctk.CTkLabel):
        if self._is_resizing or self._is_scrolling:
            return

        fallback = self.get_fallback_icon(size)
        label.configure(image=fallback)
        self._ui_image_refs.append(fallback)

        if not exe_path:
            return

        exe_path = os.path.normpath(exe_path)
        w, h = size
        key = (exe_path, w, h)

        with self._icon_cache_lock:
            if key in self._icon_ctk_cache:
                cached = self._icon_ctk_cache[key]
                img = cached or fallback
                label.configure(image=img)
                self._ui_image_refs.append(img)
                return

            if exe_path in self._icon_load_inflight:
                return
            self._icon_load_inflight.add(exe_path)

        def worker():
            try:
                with self._icon_cache_lock:
                    needs_load = exe_path not in self._icon_pil_cache
                if needs_load:
                    pil_icon = self.extract_icon_pil(exe_path)
                    with self._icon_cache_lock:
                        self._icon_pil_cache[exe_path] = pil_icon
            finally:
                if not self._is_resizing and not self._is_scrolling:
                    self.after(0, lambda: self._on_icon_ready(exe_path, size, label))
                else:
                    with self._icon_cache_lock:
                        self._icon_load_inflight.discard(exe_path)

        t = Thread(target=worker, daemon=True)
        t.start()

    def _on_icon_ready(self, exe_path: str, size: tuple[int, int], label: ctk.CTkLabel):
        with self._icon_cache_lock:
            self._icon_load_inflight.discard(exe_path)

        img = self.get_game_icon_image(exe_path, size)
        if self._is_scrolling:
            self._pending_icon_updates.append((exe_path, size, label))
            return
        if label.winfo_exists():
            label.configure(image=img)
            self._ui_image_refs.append(img)

    def _process_pending_icons(self):
        pending = list(self._pending_icon_updates)
        self._pending_icon_updates.clear()
        for exe_path, size, label in pending:
            if not label.winfo_exists():
                continue
            img = self.get_game_icon_image(exe_path, size)
            label.configure(image=img)
            self._ui_image_refs.append(img)

    def _create_game_card(self, parent: ctk.CTkScrollableFrame, index: int, game: dict):
        columns = getattr(self, "_games_columns", 3)
        row, col = divmod(index, columns)

        card = self._create_panel(parent, fg_color=UI["surface_alt"], border_width=1, border_color=UI["border"], corner_radius=14, cursor="hand2")
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        card.configure(width=270, height=252)
        card.grid_propagate(False)
        card.pack_propagate(False)

        def show_detail(e=None):
            self._show_game_detail(game)

        def on_enter(e=None):
            if not self._is_scrolling:
                if self._hovered_card is not None and self._hovered_card != card:
                    try:
                        self._hovered_card.configure(border_color=UI["border"], border_width=1)
                    except Exception:
                        pass
                self._hovered_card = card
                card.configure(border_color=UI["border_hover"], border_width=2)

        def on_leave(e=None):
            if self._is_scrolling:
                return

            try:
                x = card.winfo_pointerx() - card.winfo_rootx()
                y = card.winfo_pointery() - card.winfo_rooty()
                if 0 <= x < card.winfo_width() and 0 <= y < card.winfo_height():
                    return
            except Exception:
                pass

            card.configure(border_color=UI["border"], border_width=1)
            if self._hovered_card == card:
                self._hovered_card = None

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)
        card.bind("<Button-1>", show_detail)

        is_fav = game.get("favorite", False)
        fav_btn = ctk.CTkButton(
            card,
            text="⭐" if is_fav else "☆",
            width=30,
            height=30,
            fg_color="transparent",
            hover_color=UI["surface_hover"],
            command=lambda g=game: self._toggle_favorite(g),
            font=ctk.CTkFont(size=16)
        )
        fav_btn.place(relx=0.95, rely=0.05, anchor="ne")
        fav_btn.bind("<Button-1>", lambda e: "break", add="+")

        icon_label = ctk.CTkLabel(card, text="", cursor="hand2", width=214, height=100)
        icon_label.pack(side="top", pady=(14, 8))
        icon_label.pack_propagate(False)
        icon_label.bind("<Button-1>", show_detail)

        fallback_img = self.get_game_icon_image(game.get("path", ""), (64, 64))
        icon_label.configure(image=fallback_img)
        self._ui_image_refs.append(fallback_img)
        self._set_game_artwork_async(game, (214, 100), icon_label)

        name_label = ctk.CTkLabel(
            card,
            text=game.get("name", "Unknown"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=UI["text"],
            wraplength=210,
            cursor="hand2",
            height=40
        )
        name_label.pack(side="top", padx=8, pady=(0, 8))
        name_label.bind("<Button-1>", show_detail)

        info_available = bool(game.get("name")) and requests is not None
        if info_available:
            info_label = ctk.CTkLabel(
                card,
                text=self.t("info_available"),
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=UI["accent"]
            )
            info_label.pack(side="top", pady=(0, 6))
            info_label.bind("<Button-1>", show_detail)

        button_frame = ctk.CTkFrame(card, fg_color="transparent")
        button_frame.pack(side="top", pady=(0, 10))

        play_btn = ctk.CTkButton(
            button_frame,
            text=self.t("play"),
            width=80,
            height=32,
            corner_radius=8,
            command=lambda g=game: self.launch_game(g),
            **self._button_style("success")
        )
        play_btn.pack(side="left", padx=4)
        play_btn.bind("<Button-1>", lambda e: "break", add="+")

        del_btn = ctk.CTkButton(
            button_frame,
            text="🗑",
            width=35,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(size=14),
            command=lambda g=game: self.remove_game(g),
            **self._button_style("danger")
        )
        del_btn.pack(side="left", padx=4)
        del_btn.bind("<Button-1>", lambda e: "break", add="+")

    def _render_next_game_chunk(self):
        if self._is_resizing:
            return
        display_games = getattr(self, "_display_games", [])
        if not display_games:
            return
        start = self._rendered_games_count
        end = min(start + getattr(self, "_games_chunk_size", 12), len(display_games))
        for idx in range(start, end):
            self._create_game_card(self.games_scroll, idx, display_games[idx])
        self._rendered_games_count = end

        if start == 0:
            try:
                self.after(500, self._start_idle_icon_prewarm)
            except Exception:
                pass

    def _setup_games_scroll_poll(self):
        self._cancel_games_scroll_poll()

        def poll():
            try:
                if not self._is_resizing:
                    canvas = getattr(self.games_scroll, "_parent_canvas", None)
                    if canvas and hasattr(canvas, "yview"):
                        y1, y2 = canvas.yview()
                        display_games = getattr(self, "_display_games", [])

                        if y2 > 0.96 and self._rendered_games_count < len(display_games):
                            self._render_next_game_chunk()

                            next_delay = 150
                        else:
                            next_delay = 300
                    else:
                        next_delay = 300
                else:
                    next_delay = 400

                if self.games_scroll.winfo_exists():
                    self._scroll_poll_after_id = self.after(next_delay, poll)
            except Exception:
                self._scroll_poll_after_id = None
        self._scroll_poll_after_id = self.after(200, poll)

    def _cancel_games_scroll_poll(self):
        if self._scroll_poll_after_id:
            try:
                self.after_cancel(self._scroll_poll_after_id)
            except Exception:
                pass
            self._scroll_poll_after_id = None

    def _detect_resize_start(self, event):
        if event.widget != self:
            return

        curr_w = event.width
        curr_h = event.height

        if curr_w != self._last_width or curr_h != self._last_height:
            if not self._is_resizing:
                self._is_resizing = True

            self._last_width = curr_w
            self._last_height = curr_h

            if self._resize_after_id:
                try:
                    self.after_cancel(self._resize_after_id)
                except Exception:
                    pass

            self._resize_after_id = self.after(100, self._detect_resize_end)

    def _detect_resize_end(self):
        self._is_resizing = False
        self._resize_after_id = None

        try:
            self.update_idletasks()
        except Exception:
            pass

        if getattr(self, "_active_view", "") == "library" and hasattr(self, "games_scroll"):
            try:
                new_columns = self._calculate_game_columns()
                if new_columns != getattr(self, "_games_columns", 0) or self.winfo_width() != self._last_library_width:
                    self._games_columns = new_columns
                    self._last_library_width = self.winfo_width()
                    self.render_game_buttons()
            except Exception:
                pass

    def _start_idle_icon_prewarm(self):
        if getattr(self, "_prewarm_started", False):
            return
        self._prewarm_started = True

        def worker():
            try:
                for game in self.games[:50]:
                    p = game.get("path")
                    if not p:
                        continue
                    p = os.path.normpath(p)
                    with self._icon_cache_lock:
                        needs_load = p not in self._icon_pil_cache
                    if needs_load:
                        img = self.extract_icon_pil(p)
                        with self._icon_cache_lock:
                            self._icon_pil_cache[p] = img

                self._prune_icon_cache(
                    max_size_mb=self.settings.get("cache_size_mb", 200),
                    max_files=self.settings.get("cache_max_files", 2000)
                )
            except Exception:
                pass

        try:
            Thread(target=worker, daemon=True).start()
        except Exception:
            pass

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

            entries.sort(key=lambda x: x[1])

            size_limit = max_size_mb * 1024 * 1024
            removed_count = 0
            while (total_size > size_limit or len(entries) > max_files) and entries:
                if removed_count > 1000:
                    break
                path, _, sz = entries.pop(0)
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                        total_size -= sz
                        removed_count += 1
                except (OSError, PermissionError):
                    continue
        except Exception:
            pass

if __name__ == "__main__":
    app = GameLauncherApp()
    app.mainloop()
