#!/usr/bin/env python3
"""
Script pour corriger les dernières 11 images dangereuses qui ont échoué.
Utilise des prompts simplifiés et des délais plus longs.

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

# Liste des 11 fichiers qui ont encore échoué
REMAINING_FAILED_FILES = [
    "competition_waste_dataset/images/dangereux/commerciale/dangereux_commerciale_batterie_ordinateur.jpg",
    "competition_waste_dataset/images/dangereux/commerciale/dangereux_commerciale_batterie_ups.jpg",
    "competition_waste_dataset/images/dangereux/residentielle/dangereux_residentielle_pile_bouton.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_acide_industriel.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_dechet_radioactif_faible.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_dechet_pharmaceutique.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_chrome_hexavalent.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_mercure_industriel.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_dechet_medical_hopital.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_formaldehyde_industriel.jpg",
    "competition_waste_dataset/images/dangereux/industrielle/dangereux_industrielle_cyanure_industriel.jpg"
]

# Prompts simplifiés pour chaque type problématique
SIMPLIFIED_PROMPTS = {
    "batterie ordinateur": "computer battery waste, used laptop battery, isolated object, white background",
    "batterie ups": "UPS battery waste, backup power battery, isolated object, white background",
    "pile bouton": "button battery waste, small round battery, isolated object, white background",
    "acide industriel": "industrial acid container waste, chemical bottle, isolated object, white background",
    "dechet radioactif faible": "low radioactive waste container, hazardous waste drum, isolated object, white background",
    "dechet pharmaceutique": "pharmaceutical waste, medicine bottles, isolated object, white background",
    "chrome hexavalent": "hexavalent chromium waste container, chemical drum, isolated object, white background",
    "mercure industriel": "industrial mercury waste, mercury container, isolated object, white background",
    "dechet medical hopital": "medical waste, hospital waste bag, isolated object, white background",
    "formaldehyde industriel": "formaldehyde waste container, chemical bottle, isolated object, white background",
    "cyanure industriel": "industrial cyanide waste container, chemical drum, isolated object, white background"
}

def get_next_api_key(idx):
    return API_KEYS[idx % len(API_KEYS)]

def generate_image_with_freepik_api(prompt, api_key):
    """Version avec timeout encore plus long et gestion d'erreur améliorée"""
    api_base_url = "https://api.freepik.com/v1/ai/text-to-image"
    
    headers = {
        "x-freepik-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": prompt,
        "aspect_ratio": "square_1_1",
        "guidance_scale": 2.0,  # Réduire pour des résultats plus rapides
    }
    
    try:
        # Créer la tâche avec retry en cas d'erreur réseau
        for attempt in range(3):
            try:
                response = requests.post(
                    f"{api_base_url}/seedream",
                    headers=headers,
                    json=payload,
                    timeout=45
                )
                break
            except requests.exceptions.RequestException as e:
                if attempt == 2:
                    raise e
                time.sleep(5)
        
        if response.status_code != 200:
            raise Exception(f"Task creation failed: {response.status_code} - {response.text}")
        
        task_data = response.json()
        task_id = task_data.get("data", {}).get("task_id")
        
        if not task_id:
            raise Exception("No task_id received")
        
        # Attendre la completion avec timeout très long
        image_url = wait_for_completion(task_id, api_key, max_wait=180)  # 3 minutes
        if not image_url:
            raise Exception("Image generation timeout")
        
        # Télécharger l'image avec retry
        for attempt in range(3):
            try:
                img_response = requests.get(image_url, timeout=90)
                if img_response.status_code == 200:
                    return Image.open(BytesIO(img_response.content))
                else:
                    raise Exception(f"Download failed: {img_response.status_code}")
            except requests.exceptions.RequestException as e:
                if attempt == 2:
                    raise e
                time.sleep(3)
            
    except Exception as e:
        logging.error(f"Erreur API Freepik : {e}")
        return None

def wait_for_completion(task_id, api_key, max_wait=180):
    """Version avec timeout très long et gestion d'erreur réseau"""
    api_base_url = "https://api.freepik.com/v1/ai/text-to-image"
    headers = {"x-freepik-api-key": api_key}
    check_url = f"{api_base_url}/seedream/{task_id}"
    
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(check_url, headers=headers, timeout=45)
            
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
                
                time.sleep(8)  # Attendre encore plus longtemps
            else:
                time.sleep(8)
        except requests.exceptions.RequestException:
            # En cas d'erreur réseau, attendre et continuer
            time.sleep(10)
    
    return None

def main():
    logging.basicConfig(level=logging.INFO)
    
    if not API_KEYS:
        print("❌ Aucune clé API Freepik trouvée. Vérifiez votre fichier .env")
        return
        
    print(f"🔑 {len(API_KEYS)} clés API chargées")
    print(f"🚨 Correction finale de {len(REMAINING_FAILED_FILES)} images restantes...")
    print("⏱️ Utilisation de timeouts très longs et prompts simplifiés")
    
    api_idx = 0
    success_count = 0
    
    for file_path in tqdm(REMAINING_FAILED_FILES):
        img_path = Path(file_path)
        
        if not img_path.exists():
            logging.warning(f"Fichier non trouvé : {img_path}")
            continue
        
        # Extraire le type de déchet et utiliser le prompt simplifié
        waste_type = img_path.stem.split('_', 2)[-1].replace('_', ' ')
        prompt = SIMPLIFIED_PROMPTS.get(waste_type, f"hazardous waste {waste_type}, isolated object, white background")
        
        api_key = get_next_api_key(api_idx)
        api_idx += 1
        
        # Délai très long entre les appels
        if api_idx > 1:
            delay = random.uniform(5, 10)
            print(f"⏳ Attente {delay:.1f}s avant le prochain appel...")
            time.sleep(delay)
        
        print(f"🔧 Correction finale: {waste_type}")
        print(f"📝 Prompt: {prompt}")
        
        img = generate_image_with_freepik_api(prompt, api_key)
        if img:
            # Redimensionner à 1024x1024 pour garder la qualité
            img = img.convert('RGB').resize((1024, 1024), Image.LANCZOS)
            img.save(img_path, 'JPEG', quality=95, dpi=(300, 300))
            logging.info(f"✅ Image corrigée : {img_path}")
            success_count += 1
        else:
            logging.error(f"❌ Échec définitif pour : {img_path}")
    
    print(f"🎯 Correction finale terminée ! {success_count}/{len(REMAINING_FAILED_FILES)} images générées")
    
    total_success = 24 + 10 + success_count  # Premier run + retry + correction finale
    print(f"📊 Bilan total images dangereuses : {total_success}/45 ({total_success/45*100:.1f}%)")

if __name__ == "__main__":
    main()
