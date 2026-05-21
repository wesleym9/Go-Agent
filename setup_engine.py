import requests
import zipfile
import io
import os

def get_latest_katago_url():
    print("Finding latest KataGo release (preferring OpenCL for stability)...")
    api_url = "https://api.github.com/repos/lightvector/KataGo/releases/latest"
    r = requests.get(api_url)
    assets = r.json().get("assets", [])
    
    opencl_url = None
    for asset in assets:
        name = asset["name"]
        url = asset["browser_download_url"]
        if "windows-x64.zip" in name and "opencl" in name:
            opencl_url = url
                
    return opencl_url

def download_and_extract(url, target_dir):
    print(f"Downloading {url}...")
    r = requests.get(url)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extractall(target_dir)
    print(f"Extracted to {target_dir}")

if __name__ == "__main__":
    url = get_latest_katago_url()
    if url:
        download_and_extract(url, "engine")
    else:
        print("Could not find a suitable KataGo OpenCL release.")
