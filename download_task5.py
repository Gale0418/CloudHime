import urllib.request
import urllib.error
import zipfile
import os
import json
import hashlib
from pathlib import Path
import sys

def download_file(url, dest):
    print(f"Downloading {url} to {dest}...")
    try:
        urllib.request.urlretrieve(url, dest)
        print(f"Downloaded {dest}")
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        sys.exit(1)

def main():
    root = Path(__file__).parent
    models_dir = root / "models"
    runtime_dir = root / "runtime"
    
    models_dir.mkdir(exist_ok=True)
    runtime_dir.mkdir(exist_ok=True)
    
    # 1. Download mmproj
    projector_url = "https://huggingface.co/ggml-org/gemma-3-4b-it-gguf/resolve/main/mmproj-model-f16.gguf"
    projector_dest = models_dir / "mmproj-model-f16.gguf"
    if not projector_dest.exists():
        download_file(projector_url, projector_dest)
    else:
        print(f"{projector_dest} already exists.")
        
    # Calculate SHA256 of mmproj
    print("Calculating SHA256 of projector...")
    h = hashlib.sha256()
    with open(projector_dest, "rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    print(f"Projector SHA256: {h.hexdigest()}")
    
    # 2. Get latest llama.cpp release for CUDA 12.4
    print("Fetching latest llama.cpp release...")
    r = urllib.request.urlopen("https://api.github.com/repos/ggerganov/llama.cpp/releases/latest")
    release_data = json.loads(r.read())
    
    llama_zip_url = None
    cudart_zip_url = None
    
    for asset in release_data.get("assets", []):
        name = asset["name"]
        if "win-cuda-12.4-x64.zip" in name:
            if "cudart" in name:
                cudart_zip_url = asset["browser_download_url"]
            elif "llama" in name and "bin" in name:
                llama_zip_url = asset["browser_download_url"]
                
    if not llama_zip_url:
        print("Could not find llama.cpp win-cuda-12.4-x64.zip in latest release.")
        sys.exit(1)
        
    llama_zip_dest = runtime_dir / "llama-bin.zip"
    cudart_zip_dest = runtime_dir / "cudart-bin.zip"
    
    if not (runtime_dir / "llama-server.exe").exists():
        download_file(llama_zip_url, llama_zip_dest)
        if cudart_zip_url:
            download_file(cudart_zip_url, cudart_zip_dest)
            
        print("Extracting files to runtime directory...")
        with zipfile.ZipFile(llama_zip_dest, "r") as zip_ref:
            for member in zip_ref.namelist():
                # Extract directly to runtime/ avoiding the nested directory if there is one
                filename = os.path.basename(member)
                if not filename:
                    continue
                source = zip_ref.open(member)
                target_path = runtime_dir / filename
                with open(target_path, "wb") as target:
                    target.write(source.read())
                    
        if cudart_zip_url and cudart_zip_dest.exists():
            with zipfile.ZipFile(cudart_zip_dest, "r") as zip_ref:
                for member in zip_ref.namelist():
                    filename = os.path.basename(member)
                    if not filename:
                        continue
                    source = zip_ref.open(member)
                    target_path = runtime_dir / filename
                    with open(target_path, "wb") as target:
                        target.write(source.read())
                        
        print("Extraction complete. Cleaning up zip files...")
        llama_zip_dest.unlink(missing_ok=True)
        cudart_zip_dest.unlink(missing_ok=True)
    else:
        print("llama-server.exe already exists in runtime/")

    # 3. Verify assets
    print("Verifying all assets using local_vision_assets.py...")
    sys.path.insert(0, str(root))
    import local_vision_assets
    assets = local_vision_assets.resolve_vision_assets(root)
    missing = []
    for field_name, path in [
        ("server_path", assets.server_path),
        ("model_path", assets.model_path),
        ("projector_path", assets.projector_path),
    ]:
        min_bytes = local_vision_assets.ASSET_MINIMUM_BYTES[field_name]
        try:
            local_vision_assets.verify_asset(path, None, minimum_bytes=min_bytes)
            size = path.stat().st_size
            print(f"  [OK] {field_name}: {path} ({size:,} bytes)")
        except local_vision_assets.VisionAssetError as exc:
            missing.append(f"  [ERROR] {field_name}: {path} -> {exc.code}")

    if missing:
        print("Verification failed!")
        for m in missing:
            print(m)
        sys.exit(1)
    else:
        print("All assets verified successfully!")

if __name__ == "__main__":
    main()
