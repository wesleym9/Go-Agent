import requests

def list_assets(repo, tag):
    url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    r = requests.get(url)
    assets = r.json().get("assets", [])
    for asset in assets:
        print(f"{asset['name']}: {asset['browser_download_url']}")

if __name__ == "__main__":
    list_assets("sanderland/katrain", "v1.16.0")
