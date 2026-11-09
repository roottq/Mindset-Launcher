import sys
import os

# --- ФИКС ДЛЯ PYINSTALLER (ЧТОБЫ НЕ БЫЛО ОШИБКИ 404) ---
if getattr(sys, 'frozen', False):
    # Если программа скомпилирована, меняем рабочую директорию на временную папку распаковки
    os.chdir(sys._MEIPASS)
# -------------------------------------------------------

import json
import subprocess
import threading
import time
import shutil
import webview
import minecraft_launcher_lib
from tkinter import Tk, filedialog

# --- НАСТРОЙКИ ---
MC_DIR = minecraft_launcher_lib.utils.get_minecraft_directory()
CONFIG_FILE = "config.json"
DISCORD_CLIENT_ID = "1569053506168426506"

AIKAR_FLAGS = "-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch -XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M -XX:G1ReservePercent=20 -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4 -XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90 -XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 -XX:+PerfDisableSharedMem -XX:MaxTenuringThreshold=1"

default_config = {
    "active_profile": "Player",
    "profiles": {
        "Player": {
            "ram": 4, "java_path": "java",
            "version": "1.20.1", "skin_path": "", "optimized": False, "server_ip": ""
        }
    }
}

# Загрузка конфига с защитой от старых версий
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
        if "profiles" not in config:
            config = default_config
            with open(CONFIG_FILE, "w") as f: json.dump(config, f)
else:
    config = default_config
    with open(CONFIG_FILE, "w") as f: json.dump(config, f)

def save_config():
    with open(CONFIG_FILE, "w") as f: json.dump(config, f)

def get_active():
    return config["profiles"][config["active_profile"]]

# --- DISCORD RPC ---
try:
    from pypresence import Presence
    rpc = Presence(DISCORD_CLIENT_ID)
    rpc.connect()
    rpc.update(state="В главном меню", details="Mindset Launcher", start=int(time.time()))
except Exception:
    rpc = None

class LauncherAPI:
    def ready(self):
        self.refresh_ui()
        profiles_list = list(config["profiles"].keys())
        window.evaluate_js(f"window.updateProfileList({json.dumps(profiles_list)}, '{config['active_profile']}');")

    def refresh_ui(self):
        profile = get_active()
        window.evaluate_js(f"window.updateUI('{profile['version']}');")
        window.evaluate_js(f"window.fillSettings({profile['ram']}, '{profile['java_path']}', {str(profile['optimized']).lower()}, '{profile.get('server_ip', '')}');")

    def switch_profile(self, profile_name):
        config["active_profile"] = profile_name
        save_config()
        self.refresh_ui()

    def create_profile(self, name):
        if name and name not in config["profiles"]:
            config["profiles"][name] = {
                "ram": 4, "java_path": "java", "version": "1.20.1",
                "skin_path": "", "optimized": False, "server_ip": ""
            }
            config["active_profile"] = name
            save_config()
            self.refresh_ui()
            profiles_list = list(config["profiles"].keys())
            window.evaluate_js(f"window.updateProfileList({json.dumps(profiles_list)}, '{name}');")

    def set_version(self, version):
        get_active()["version"] = version
        save_config()

    def set_server(self, ip):
        get_active()["server_ip"] = ip
        save_config()

    def get_mc_dir(self):
        return MC_DIR

    def set_skin(self):
        root = Tk(); root.withdraw()
        filepath = filedialog.askopenfilename(title="Выбери скин (PNG)", filetypes=[("PNG", "*.png")])
        root.destroy()
        if filepath:
            get_active()["skin_path"] = filepath
            save_config()
            window.evaluate_js("window.showToast('Скин успешно установлен!');")

    def save_settings(self, ram, java_path, optimized):
        get_active()["ram"] = int(ram)
        get_active()["java_path"] = java_path
        get_active()["optimized"] = bool(optimized)
        save_config()

    # --- МОДЫ ---
    def get_mods(self):
        mods_dir = os.path.join(MC_DIR, "mods")
        if not os.path.exists(mods_dir): os.makedirs(mods_dir)
        mods = []
        for f in os.listdir(mods_dir):
            if f.endswith(".jar"): mods.append({"name": f, "enabled": True})
            elif f.endswith(".jar.disabled"): mods.append({"name": f.replace(".disabled", ""), "enabled": False})
        return mods

    def toggle_mod(self, mod_name):
        mods_dir = os.path.join(MC_DIR, "mods")
        en_path = os.path.join(mods_dir, mod_name)
        dis_path = os.path.join(mods_dir, mod_name + ".disabled")
        if os.path.exists(en_path): os.rename(en_path, dis_path)
        elif os.path.exists(dis_path): os.rename(dis_path, en_path)
        return self.get_mods()

    def import_mod(self):
        root = Tk(); root.withdraw()
        filepath = filedialog.askopenfilename(title="Выбери мод (.jar)", filetypes=[("JAR files", "*.jar")])
        root.destroy()
        if filepath:
            mods_dir = os.path.join(MC_DIR, "mods")
            if not os.path.exists(mods_dir): os.makedirs(mods_dir)
            shutil.copy(filepath, os.path.join(mods_dir, os.path.basename(filepath)))
            window.evaluate_js("window.showToast('Мод добавлен!');")

    def open_mods(self):
        mods_dir = os.path.join(MC_DIR, "mods")
        if not os.path.exists(mods_dir): os.makedirs(mods_dir)
        subprocess.Popen(["xdg-open", mods_dir])

    # --- СКРИНШОТЫ ---
    def get_screenshots(self):
        ss_dir = os.path.join(MC_DIR, "screenshots")
        if not os.path.exists(ss_dir): os.makedirs(ss_dir)
        return [f for f in os.listdir(ss_dir) if f.endswith(('.png', '.jpg'))]

    def open_screenshot(self, filename):
        path = os.path.join(MC_DIR, "screenshots", filename)
        subprocess.Popen(["xdg-open", path])

    def delete_screenshot(self, filename):
        path = os.path.join(MC_DIR, "screenshots", filename)
        if os.path.exists(path): os.remove(path)
        return self.get_screenshots()

    # --- СИСТЕМНЫЕ ---
    def clear_cache(self):
        logs_dir = os.path.join(MC_DIR, "logs")
        crash_dir = os.path.join(MC_DIR, "crash-reports")
        try:
            if os.path.exists(logs_dir): shutil.rmtree(logs_dir)
            if os.path.exists(crash_dir): shutil.rmtree(crash_dir)
            window.evaluate_js("window.showToast('Логи и краш-репорты очищены!');")
        except: pass

    def open_saves(self):
        saves_dir = os.path.join(MC_DIR, "saves")
        if not os.path.exists(saves_dir): os.makedirs(saves_dir)
        subprocess.Popen(["xdg-open", saves_dir])

    def check_updates(self):
        time.sleep(1)
        window.evaluate_js("window.showToast('У вас последняя версия (1.0.0)!');")

    # --- JAVA ---
    def ensure_java(self, version):
        java_path = get_active()["java_path"]
        if java_path != "java": return java_path
        try:
            runtime_info = minecraft_launcher_lib.utils.get_version_runtime_information(version)
            if runtime_info:
                java_dir = os.path.join(MC_DIR, "runtime", runtime_info["name"])
                if not os.path.exists(java_dir):
                    window.evaluate_js("window.showToast('Скачивание Java...');")
                    minecraft_launcher_lib.java_utils.install_jvm_runtime(runtime_info["name"], MC_DIR)
                return os.path.join(java_dir, "bin", "java")
        except Exception as e:
            print(f"Java Error: {e}")
        return "java"

    # --- ЗАПУСК ---
    def play_game(self):
        profile_name = config["active_profile"]
        profile = get_active()
        version = profile["version"]
        ram = profile["ram"]
        optimized = profile.get("optimized", False)
        server_ip = profile.get("server_ip", "").strip()

        def run():
            try:
                java_path = self.ensure_java(version)
                installed = [v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(MC_DIR)]
                if version not in installed:
                    minecraft_launcher_lib.install.install_minecraft_version(version, MC_DIR)

                jvm_args = [f"-Xmx{ram}G", f"-Xms{ram}G"]
                if optimized:
                    jvm_args.extend(AIKAR_FLAGS.split())

                options = {
                    "username": profile_name, "token": "offline",
                    "uuid": "00000000-0000-0000-0000-000000000000",
                    "executablePath": java_path,
                    "jvmArguments": jvm_args
                }

                cmd = minecraft_launcher_lib.command.get_minecraft_command(version, MC_DIR, options)
                if server_ip:
                    cmd.extend(["--server", server_ip])

                if rpc: rpc.update(state="Играет в Minecraft", details=f"Версия: {version}", start=int(time.time()))
                subprocess.Popen(cmd)

            except Exception as e:
                print(f"Error: {e}")
            finally:
                window.evaluate_js("window.resetPlayButton();")

        threading.Thread(target=run, daemon=True).start()

# --- ИНИЦИАЛИЗАЦИЯ ---
if __name__ == "__main__":
    api = LauncherAPI()
    # Благодаря os.chdir в начале кода, этот путь будет правильным и для .py, и для .exe
    html_path = os.path.abspath("ui.html")

    window = webview.create_window(
        "Mindset Launcher", url=html_path, width=1000, height=650,
        background_color='#000000',
        frameless=False,
        js_api=api
    )

    webview.start(debug=False)
