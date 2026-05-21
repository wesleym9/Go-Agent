import requests
import os

def download_human_model():
    url = "https://github.com/lightvector/KataGo/releases/download/v1.15.0/b18c384nbt-humanv0.bin.gz"
    print(f"Downloading Human SL model from {url}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        response.raise_for_status()
        
        os.makedirs("models", exist_ok=True)
        model_path = "models/default_model.bin.gz"
        
        with open(model_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"Download complete. Size: {os.path.getsize(model_path)} bytes.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    download_human_model()
