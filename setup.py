import os
import sys
import platform
import subprocess
import requests
import zipfile
import io

def print_banner(text):
    print("=" * 70)
    print(f" {text:^68} ")
    print("=" * 70)

def install_dependencies():
    print_banner("STEP 1: INSTALLING PYTHON DEPENDENCIES")
    try:
        print("Running: pip install -r requirements.txt...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("\n[SUCCESS] Dependencies installed successfully!")
    except Exception as e:
        print(f"\n[ERROR] Failed to install dependencies via pip: {e}")
        print("Please run manually: pip install -r requirements.txt")

def setup_katago_engine():
    print_banner("STEP 2: SETTING UP KATAGO ENGINE BINARY")
    os.makedirs("engine", exist_ok=True)
    
    current_os = platform.system().lower()
    
    if current_os == "windows":
        katago_exe = "engine/katago.exe"
        if os.path.exists(katago_exe):
            print("[INFO] KataGo binary already exists at engine/katago.exe. Skipping download.")
            return
            
        print("Windows system detected. Automating OpenCL KataGo download...")
        try:
            api_url = "https://api.github.com/repos/lightvector/KataGo/releases/latest"
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(api_url, headers=headers)
            r.raise_for_status()
            
            assets = r.json().get("assets", [])
            opencl_url = None
            for asset in assets:
                name = asset["name"]
                url = asset["browser_download_url"]
                if "windows-x64.zip" in name and "opencl" in name:
                    opencl_url = url
                    break
            
            if opencl_url:
                print(f"Downloading latest Windows OpenCL release: {opencl_url}...")
                zip_r = requests.get(opencl_url, headers=headers)
                zip_r.raise_for_status()
                
                with zipfile.ZipFile(io.BytesIO(zip_r.content)) as z:
                    z.extractall("engine")
                print("[SUCCESS] Windows KataGo engine and supporting DLLs extracted to engine/ folder!")
            else:
                print("[WARNING] Could not locate Windows OpenCL release. Please download from: https://github.com/lightvector/KataGo/releases")
        except Exception as e:
            print(f"[ERROR] Failed to download Windows KataGo automatically: {e}")
            print("Please download manually and place 'katago.exe' in 'engine/' folder.")
            
    elif current_os == "darwin":  # macOS
        print("macOS (OS X) system detected.")
        print("Please install KataGo using Homebrew:")
        print("  brew install katago")
        print("\nThen copy the 'katago' executable or create a symlink inside the 'engine' folder.")
        
    else:  # Linux or other
        print("Linux system detected.")
        print("Please install KataGo using your package manager:")
        print("  Ubuntu/Debian: sudo apt install katago")
        print("  Arch Linux:    sudo pacman -S katago")
        print("\nThen copy the 'katago' executable inside the 'engine' folder.")

def download_model(url, filename, desc):
    os.makedirs("models", exist_ok=True)
    target_path = os.path.join("models", filename)
    
    if os.path.exists(target_path):
        print(f"[INFO] {desc} already exists at {target_path}. Skipping.")
        return
        
    print(f"Downloading {desc}...")
    print(f"Source: {url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, stream=True, timeout=60, headers=headers)
        response.raise_for_status()
        
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        print(f"[SUCCESS] {desc} saved as {target_path} (Size: {os.path.getsize(target_path)} bytes).")
    except Exception as e:
        print(f"[ERROR] Failed to download {desc}: {e}")

def setup_models():
    print_banner("STEP 3: DOWNLOADING NEURAL NETWORK MODELS")
    
    # 1. Download Human SL Model (default_model.bin.gz)
    human_url = "https://github.com/lightvector/KataGo/releases/download/v1.15.0/b18c384nbt-humanv0.bin.gz"
    download_model(human_url, "default_model.bin.gz", "Human SL Model (9D Style)")
    
    # 2. Download Superhuman Model (superhuman_model.bin.gz)
    superhuman_url = "https://github.com/lightvector/KataGo/releases/download/v1.13.0/b18c384nbt-optimisticv13-s5971M.bin.gz"
    download_model(superhuman_url, "superhuman_model.bin.gz", "Superhuman Self-Play Model (optimistic 18b)")

def main():
    print_banner("GO TEACHING COMPANION SYSTEM INSTALLER")
    print("This script will install all requirements, set up the KataGo engine,")
    print("and download the required neural network models automatically.")
    print("Please make sure you have a working internet connection.")
    print("=" * 70)
    
    install_dependencies()
    setup_katago_engine()
    setup_models()
    
    print_banner("INSTALLATION COMPLETE")
    print("All components have been configured. To run the application:")
    print("  1. Start the FastAPI server:")
    print("     python -m uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000")
    print("  2. Open your web browser at:")
    print("     http://127.0.0.1:8000")
    print("=" * 70)

if __name__ == "__main__":
    main()
