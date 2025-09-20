#!/usr/bin/env python3
"""
Script pour régénérer les images de la catégorie 'dangereux' avec un prompt amélioré
pour que le déchet soit bien visible, isolé, sans poubelle ni contenant, sur fond neutre.

- Parcourt tous les types/zones de la catégorie 'dangereux'
- Génère une nouvelle image pour chaque type/zone
- Écrase l'image existante

Auteur : Assistant IA
Date : 20 septembre 2025
"""

import os
from pathlib import Path
import logging
from dotenv import load_dotenv
import requests
from PIL import Image
from io import BytesIO
from tqdm import tqdm
import time
import random

# Charger les clés API
load_dotenv()

# Charger toutes les clés API disponibles comme dans le générateur principal
def load_api_keys():
    keys = []
    # Clé principale
    main_key = os.getenv("FREEPIK_API_KEY")
    if main_key:
        keys.append(main_key)
    
    # Clés additionnelles
    for i in range(1, 10):
        key = os.getenv(f"FREEPIK_API_KEY_{i}")
        if key:
            keys.append(key)
    
    return [k for k in keys if k and len(k) > 10]

API_KEYS = load_api_keys()

DANGEROUS_DIR = Path("competition_waste_dataset/images/dangereux")

PROMPT_TEMPLATE = (
    "realistic {waste_type} hazardous waste, used dirty discarded item, "
    "clear visible details, isolated object, white background, "
    "photo quality, no container, no bin, no hands"
)

def get_image_files():
    """Retourne la liste des fichiers images à régénérer."""
    image_files = []
    for zone_dir in DANGEROUS_DIR.iterdir():
        if zone_dir.is_dir():
            for img_file in zone_dir.glob("*.jpg"):
                image_files.append(img_file)
    return image_files


def get_next_api_key(idx):
    return API_KEYS[idx % len(API_KEYS)]


def generate_image_with_freepik_api(prompt, api_key):
    """Génère une image en utilisant la même API que le générateur principal"""
    api_base_url = "https://api.freepik.com/v1/ai/text-to-image"
    
    headers = {
        "x-freepik-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": prompt,
        "aspect_ratio": "square_1_1",
        "guidance_scale": 3.0,
    }
    
    try:
        # Créer la tâche
        response = requests.post(
            f"{api_base_url}/seedream",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"Task creation failed: {response.status_code} - {response.text}")
        
        task_data = response.json()
        task_id = task_data.get("data", {}).get("task_id")
        
        if not task_id:
            raise Exception("No task_id received")
        
        # Attendre la completion
        image_url = wait_for_completion(task_id, api_key)
        if not image_url:
            raise Exception("Image generation timeout")
        
        # Télécharger l'image
        img_response = requests.get(image_url, timeout=60)
        if img_response.status_code == 200:
            return Image.open(BytesIO(img_response.content))
        else:
            raise Exception(f"Download failed: {img_response.status_code}")
            
    except Exception as e:
        logging.error(f"Erreur API Freepik : {e}")
        return None


def wait_for_completion(task_id, api_key, max_wait=60):
    """Attend la completion de la tâche"""
    api_base_url = "https://api.freepik.com/v1/ai/text-to-image"
    headers = {"x-freepik-api-key": api_key}
    check_url = f"{api_base_url}/seedream/{task_id}"
    
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        response = requests.get(check_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            task_data = data.get("data", {})
            status = task_data.get("status")
            
            if status == "COMPLETED":
                generated_urls = task_data.get("generated", [])
                if len(generated_urls) >= 2 and str(generated_urls[1]).startswith("http"):
                    return generated_urls[1]
            elif status in ["FAILED", "CANCELLED"]:
                return None
            
            time.sleep(3)
        else:
            time.sleep(3)
    
    return None


def main():
    logging.basicConfig(level=logging.INFO)
    
    if not API_KEYS:
        print("❌ Aucune clé API Freepik trouvée. Vérifiez votre fichier .env")
        return
        
    print(f"🔑 {len(API_KEYS)} clés API chargées")
    
    image_files = get_image_files()
    if not image_files:
        print("Aucune image dangereuse trouvée.")
        return
        
    print(f"Régénération de {len(image_files)} images dangereuses...")
    
    api_idx = 0
    success_count = 0
    
    for img_path in tqdm(image_files):
        # Extraire le type de déchet depuis le nom du fichier
        waste_type = img_path.stem.split('_', 2)[-1].replace('_', ' ')
        zone = img_path.parent.name
        prompt = PROMPT_TEMPLATE.format(waste_type=waste_type)
        
        api_key = get_next_api_key(api_idx)
        api_idx += 1
        
        # Ajouter un petit délai entre les appels
        if api_idx > 1:
            time.sleep(random.uniform(0.5, 1.5))
        
        img = generate_image_with_freepik_api(prompt, api_key)
        if img:
            # Redimensionner à 1024x1024 pour garder la qualité
            img = img.convert('RGB').resize((1024, 1024), Image.LANCZOS)
            img.save(img_path, 'JPEG', quality=95, dpi=(300, 300))
            logging.info(f"Image régénérée : {img_path}")
            success_count += 1
        else:
            logging.error(f"Échec pour : {img_path}")
    
    print(f"✅ Régénération terminée ! {success_count}/{len(image_files)} images générées")

if __name__ == "__main__":
    main()
