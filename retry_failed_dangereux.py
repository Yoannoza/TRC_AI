#!/usr/bin/env python3
"""
Script pour retenter uniquement les images dangereuses qui ont échoué lors de la première génération.

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

# Liste des fichiers qui ont échoué
FAILED_FILES = [
    "competition_waste_dataset/images/dangereux/commerciale/dangereux_commerciale_batterie_vehicule_12V.jpg",
    "competition_waste_dataset/images/dangereux/commerciale/dangereux_commerciale_batterie_ordinateur.jpg",
    "competition_waste_dataset/images/dangereux/commerciale/dangereux_commerciale_liquide_refroidissement.jpg",
    "competition_waste_dataset/images/dangereux/commerciale/dangereux_commerciale_batterie_ups.jpg",
    "competition_waste_dataset/images/dangereux/commerciale/dangereux_commerciale_disque_dur_defaillant.jpg",
    "competition_waste_dataset/images/dangereux/residentielle/dangereux_residentielle_aerosol_vide.jpg",
    "competition_waste_dataset/images/dangereux/residentielle/dangereux_residentielle_insecticide_aerosol.jpg",
    "competition_waste_dataset/images/dangereux/residentielle/dangereux_residentielle_peinture_pot_vide.jpg",
    "competition_waste_dataset/images/dangereux/residentielle/dangereux_residentielle_huile_vidange.jpg",
    "competition_waste_dataset/images/dangereux/residentielle/dangereux_residentielle_solvant_bricolage.jpg",
    "competition_waste_dataset/images/dangereux/residentielle/dangereux_residentielle_ampoule_led_cassee.jpg",
    "competition_waste_dataset/images/dangereux/residentielle/dangereux_residentielle_pile_bouton.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_pesticide_industriel.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_acide_industriel.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_dechet_radioactif_faible.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_dechet_pharmaceutique.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_chrome_hexavalent.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_mercure_industriel.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_dechet_medical_hopital.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_formaldehyde_industriel.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_cyanure_industriel.jpg"
]

PROMPT_TEMPLATE = (
    "realistic {waste_type} hazardous waste, used dirty discarded item, "
    "clear visible details, isolated object, white background, "
    "photo quality, no container, no bin, no hands"
)

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
        
        # Attendre la completion avec timeout plus long
        image_url = wait_for_completion(task_id, api_key, max_wait=120)  # 2 minutes
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

def wait_for_completion(task_id, api_key, max_wait=120):
    """Attend la completion de la tâche avec timeout plus long"""
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
            
            time.sleep(5)  # Attendre plus longtemps entre les vérifications
        else:
            time.sleep(5)
    
    return None

def main():
    logging.basicConfig(level=logging.INFO)
    
    if not API_KEYS:
        print("❌ Aucune clé API Freepik trouvée. Vérifiez votre fichier .env")
        return
        
    print(f"🔑 {len(API_KEYS)} clés API chargées")
    print(f"🔄 Retry de {len(FAILED_FILES)} images échouées...")
    
    api_idx = 0
    success_count = 0
    
    for file_path in tqdm(FAILED_FILES):
        img_path = Path(file_path)
        
        if not img_path.exists():
            logging.warning(f"Fichier non trouvé : {img_path}")
            continue
        
        # Extraire le type de déchet depuis le nom du fichier
        waste_type = img_path.stem.split('_', 2)[-1].replace('_', ' ')
        prompt = PROMPT_TEMPLATE.format(waste_type=waste_type)
        
        api_key = get_next_api_key(api_idx)
        api_idx += 1
        
        # Délai plus long entre les appels pour éviter les timeouts
        if api_idx > 1:
            time.sleep(random.uniform(2, 4))
        
        print(f"🔄 Retry: {waste_type}")
        
        img = generate_image_with_freepik_api(prompt, api_key)
        if img:
            # Redimensionner à 1024x1024 pour garder la qualité
            img = img.convert('RGB').resize((1024, 1024), Image.LANCZOS)
            img.save(img_path, 'JPEG', quality=95, dpi=(300, 300))
            logging.info(f"✅ Image régénérée : {img_path}")
            success_count += 1
        else:
            logging.error(f"❌ Échec pour : {img_path}")
    
    print(f"✅ Retry terminé ! {success_count}/{len(FAILED_FILES)} images générées")

if __name__ == "__main__":
    main()
