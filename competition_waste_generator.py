#!/usr/bin/env python3
"""
Générateur d'images de déchets pour compétition de robotique
===========================================================

Génère des images de déchets via l'API Freepik pour une compétition de robotique.
Organise les déchets en 3 catégories (Ménagers, Dangereux, Recyclables) 
et 3 zones (Résidentielle, Commerciale, Industrielle).

Structure: 14 types de déchets × 3 zones × 3 catégories = 126 images
Format final: PDFs avec images 3x3 cm, 10 répétitions par ligne

Auteur: Assistant IA
Date: Septembre 2025
"""

import os
import json
import logging
import asyncio
import time
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Imports pour le traitement d'images et PDF
import requests
import base64
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import tempfile

# Imports pour la génération PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import black, white

# Imports pour le progress tracking
from tqdm import tqdm

# Variables d'environnement
from dotenv import load_dotenv
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler('competition_waste_generator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class CompetitionWasteItem:
    """Configuration d'un déchet pour la compétition"""
    name: str
    category: str  # "menagers", "dangereux", "recyclables"
    zone: str     # "residentielle", "commerciale", "industrielle"
    description: str
    colors: List[str]
    materials: List[str]
    typical_forms: List[str]
    
class FreepikImageGenerator:
    """Générateur d'images via l'API Freepik avec retry robuste et rotation des clés"""
    
    def __init__(self):
        # Charger toutes les clés API disponibles
        raw_keys = []
        
        # Clé principale
        main_key = os.getenv("FREEPIK_API_KEY")
        if main_key:
            raw_keys.append(main_key)
        
        # Clés additionnelles
        for i in range(1, 10):  # Support jusqu'à 10 clés (FREEPIK_API_KEY_1 à FREEPIK_API_KEY_9)
            key = os.getenv(f"FREEPIK_API_KEY_{i}")
            if key:
                raw_keys.append(key)
        
        if not raw_keys:
            logger.error("Aucune clé API Freepik trouvée dans les variables d'environnement")
            logger.error("Définissez au moins FREEPIK_API_KEY ou FREEPIK_API_KEY_1")
            raise ValueError("Aucune clé API Freepik configurée")
        
        # Configuration de rotation des clés
        self.current_key_index = 0
        self.key_usage_count = {}  # Compteur d'utilisation par clé
        self.failed_keys = set()  # Clés temporairement en échec
        self.invalid_keys = set()  # Clés définitivement invalides
        
        self.api_base_url = "https://api.freepik.com/v1/ai/text-to-image/seedream"
        self.max_retries = 2
        self.base_delay = 1.0
        self.max_delay = 10.0
        
        logger.info(f"Validation de {len(raw_keys)} clé(s) API Freepik...")
        
        # Valider les clés avant de les utiliser
        self.api_keys = self._validate_api_keys(raw_keys)
        
        if not self.api_keys:
            logger.error("Aucune clé API valide trouvée!")
            raise ValueError("Toutes les clés API Freepik sont invalides")
        
        # Initialiser les compteurs pour les clés valides
        for key in self.api_keys:
            self.key_usage_count[key] = 0
        
        logger.info(f"✓ {len(self.api_keys)} clé(s) API valide(s) prête(s) à utiliser")
        for i, key in enumerate(self.api_keys):
            logger.info(f"  Clé {i+1}: {key[:10]}... ✓")
    
    def _validate_api_keys(self, raw_keys: list) -> list:
        """Valide les clés API en testant l'endpoint réel d'API"""
        valid_keys = []
        
        for i, key in enumerate(raw_keys):
            logger.info(f"Validation clé {i+1} ({key[:10]}...)...")
            
            try:
                # Test avec l'endpoint réel de l'API Freepik
                headers = {
                    "x-freepik-api-key": key,
                    "Content-Type": "application/json"
                }
                
                # Test avec un prompt simple pour vérifier l'accès réel
                test_payload = {
                    "prompt": "simple test object",
                    "aspect_ratio": "square_1_1",
                    "guidance_scale": 3.0,
                }
                
                response = requests.post(
                    self.api_base_url,
                    headers=headers,
                    json=test_payload,
                    timeout=15
                )
                
                if response.status_code == 200:
                    logger.info(f"✓ Clé {i+1} ({key[:10]}...) : Test API réel OK")
                    valid_keys.append(key)
                elif response.status_code == 401:
                    logger.warning(f"❌ Clé {i+1} ({key[:10]}...) : Authentification échouée - clé invalide")
                    self.invalid_keys.add(key)
                elif response.status_code == 403:
                    logger.warning(f"❌ Clé {i+1} ({key[:10]}...) : Accès interdit - permissions insuffisantes")
                    self.invalid_keys.add(key)
                elif response.status_code == 404:
                    logger.warning(f"❌ Clé {i+1} ({key[:10]}...) : Endpoint non trouvé - clé probablement invalide")
                    self.invalid_keys.add(key)
                elif response.status_code == 429:
                    logger.warning(f"⚠️  Clé {i+1} ({key[:10]}...) : Limite de taux atteinte - garde quand même")
                    valid_keys.append(key)  # On garde car la clé fonctionne, juste limitée
                else:
                    logger.warning(f"⚠️  Clé {i+1} ({key[:10]}...) : Statut inattendu {response.status_code}")
                    try:
                        error_detail = response.json()
                        logger.warning(f"   Détail: {error_detail}")
                    except:
                        logger.warning(f"   Réponse: {response.text[:100]}")
                    
                    # Pour les autres codes, on teste l'endpoint général en fallback
                    fallback_response = requests.get(
                        "https://api.freepik.com", 
                        headers={"x-freepik-api-key": key}, 
                        timeout=10
                    )
                    if fallback_response.status_code in [200, 404, 405]:
                        logger.info(f"   Fallback OK - garde la clé {i+1}")
                        valid_keys.append(key)
                    else:
                        logger.warning(f"   Fallback échoué - rejette la clé {i+1}")
                        self.invalid_keys.add(key)
                    
            except Exception as e:
                logger.warning(f"⚠️  Clé {i+1} ({key[:10]}...) : Erreur de test ({e})")
                # En cas d'erreur réseau, on teste avec l'endpoint général
                try:
                    fallback_response = requests.get(
                        "https://api.freepik.com", 
                        headers={"x-freepik-api-key": key}, 
                        timeout=10
                    )
                    if fallback_response.status_code in [200, 404, 405]:
                        logger.info(f"   Fallback OK après erreur - garde la clé {i+1}")
                        valid_keys.append(key)
                    else:
                        logger.warning(f"   Fallback échoué - rejette la clé {i+1}")
                        self.invalid_keys.add(key)
                except:
                    logger.warning(f"   Tous les tests échoués - rejette la clé {i+1}")
                    self.invalid_keys.add(key)
        
        return valid_keys
    
    def get_current_api_key(self) -> str:
        """Récupère la clé API actuelle, avec rotation automatique"""
        # Filtrer les clés valides (pas failed et pas invalides)
        available_keys = [key for key in self.api_keys 
                         if key not in self.failed_keys and key not in self.invalid_keys]
        
        if not available_keys:
            # Reset des clés failed si toutes sont bloquées
            logger.warning("Toutes les clés API sont temporairement indisponibles, reset...")
            self.failed_keys.clear()
            available_keys = self.api_keys
        
        # Sélectionner la clé avec le moins d'utilisation
        current_key = min(available_keys, key=lambda k: self.key_usage_count.get(k, 0))
        return current_key
    
    def rotate_api_key(self, failed_key: str = None):
        """Effectue la rotation vers une nouvelle clé API"""
        if failed_key:
            self.failed_keys.add(failed_key)
            logger.warning(f"Clé API {failed_key[:10]}... marquée comme temporairement indisponible")
        
        # Sélectionner la prochaine clé disponible (exclure failed ET invalid)
        available_keys = [key for key in self.api_keys 
                         if key not in self.failed_keys and key not in self.invalid_keys]
        
        if available_keys:
            next_key = min(available_keys, key=lambda k: self.key_usage_count.get(k, 0))
            logger.info(f"Rotation vers la clé: {next_key[:10]}...")
            return next_key
        else:
            # Toutes les clés valides sont failed, reset les failed seulement
            valid_keys = [key for key in self.api_keys if key not in self.invalid_keys]
            if valid_keys:
                logger.warning("Reset de toutes les clés API failed (gardant les valides)")
                self.failed_keys.clear()
                return valid_keys[0]
            else:
                logger.error("Toutes les clés API sont invalides!")
                return self.api_keys[0]  # Dernier recours
    
    def _make_request_with_retry(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        """Effectue une requête avec retry automatique et rotation des clés API"""
        original_key = self.get_current_api_key()
        current_key = original_key
        
        # Effectuer la requête avec toutes les clés disponibles si nécessaire
        for key_attempt in range(len(self.api_keys)):
            # Mettre à jour les headers avec la clé actuelle
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers']['x-freepik-api-key'] = current_key
            
            # Tentatives de retry pour cette clé
            for attempt in range(self.max_retries + 1):
                try:
                    if attempt > 0:
                        delay = min(self.base_delay * (2 ** attempt) + random.uniform(0, 0.5), self.max_delay)
                        logger.info(f"Retry attempt {attempt + 1}/{self.max_retries + 1} avec clé {current_key[:10]}..., waiting {delay:.1f}s...")
                        time.sleep(delay)
                    else:
                        # Incrémenter le compteur d'utilisation pour cette clé
                        self.key_usage_count[current_key] += 1
                        if key_attempt == 0:
                            logger.debug(f"Utilisation de la clé {current_key[:10]}... (usage: {self.key_usage_count[current_key]})")
                    
                    # Configuration de la requête
                    kwargs.setdefault('timeout', 20)
                    kwargs['headers']['User-Agent'] = 'Competition-Waste-Generator/1.0'
                    
                    if method.upper() == 'GET':
                        response = requests.get(url, **kwargs)
                    elif method.upper() == 'POST':
                        response = requests.post(url, **kwargs)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")
                    
                    logger.debug(f"Request {method} {url} -> Status: {response.status_code}")
                    
                    if response.status_code == 200:
                        return response
                    elif response.status_code == 401:
                        logger.error(f"Authentication échouée avec la clé {current_key[:10]}... - clé invalide")
                        # Marquer cette clé comme définitivement invalide
                        self.invalid_keys.add(current_key)
                        self.rotate_api_key(current_key)
                        break  # Sortir du retry loop pour cette clé
                    elif response.status_code == 403:
                        logger.error(f"Accès interdit avec la clé {current_key[:10]}... - Vérifiez les permissions")
                        # Marquer cette clé comme définitivement invalide
                        self.invalid_keys.add(current_key)
                        self.rotate_api_key(current_key)
                        break
                    elif response.status_code == 404:
                        logger.warning(f"Endpoint non trouvé (404) avec la clé {current_key[:10]}... - possible clé invalide")
                        if attempt == self.max_retries:
                            # Après plusieurs tentatives 404, marquer comme invalide
                            logger.error(f"Erreurs 404 persistantes - marquage de la clé {current_key[:10]}... comme invalide")
                            self.invalid_keys.add(current_key)
                            self.rotate_api_key(current_key)
                            break
                    elif response.status_code == 429:
                        logger.warning(f"Limite de taux atteinte avec la clé {current_key[:10]}... sur l'attempt {attempt + 1}")
                        if attempt == self.max_retries:
                            # Si c'est le dernier retry, marquer la clé et passer à la suivante
                            logger.warning(f"Limite de taux persistante, rotation de la clé {current_key[:10]}...")
                            self.rotate_api_key(current_key)
                            break
                    elif response.status_code in [500, 502, 503, 504]:
                        logger.warning(f"Erreur serveur temporaire {response.status_code} avec clé {current_key[:10]}... sur l'attempt {attempt + 1}")
                    else:
                        logger.warning(f"Erreur inattendue {response.status_code} avec clé {current_key[:10]}... sur l'attempt {attempt + 1}")
                        if attempt == self.max_retries:
                            logger.warning(f"Erreur persistante, rotation de la clé {current_key[:10]}...")
                            self.rotate_api_key(current_key)
                            break
                
                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout avec clé {current_key[:10]}... sur l'attempt {attempt + 1}")
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Erreur de requête avec clé {current_key[:10]}... sur l'attempt {attempt + 1}: {e}")
                except Exception as e:
                    logger.error(f"Erreur inattendue avec clé {current_key[:10]}... sur l'attempt {attempt + 1}: {e}")
            
            # Si on arrive ici, cette clé a échoué, essayer la suivante
            current_key = self.rotate_api_key(current_key)
            if current_key == original_key and key_attempt > 0:
                # On a fait le tour de toutes les clés
                logger.error("Toutes les clés API ont échoué")
                break
        
        return None
    
    def generate_image(self, waste_item: CompetitionWasteItem) -> Optional[bytes]:
        """Génère une image pour un déchet donné avec gestion d'erreurs améliorée"""
        try:
            # 1. Créer le prompt optimisé
            prompt = self._build_prompt(waste_item)
            logger.info(f"Generating image for: {waste_item.name} ({waste_item.category}/{waste_item.zone})")
            logger.debug(f"Prompt: {prompt[:100]}...")
            
            # 2. Test de connectivité API avant génération
            if not self._test_api_connectivity():
                logger.error("API connectivity test failed")
                return None
            
            # 3. Créer la tâche de génération
            task_id = self._create_generation_task(prompt)
            if not task_id:
                logger.error(f"Failed to create generation task for {waste_item.name}")
                return None
            
            # 4. Attendre la completion et récupérer l'URL
            image_url = self._wait_for_completion(task_id, max_wait_time=60)  # Timeout réduit
            if not image_url:
                logger.error(f"Failed to get image URL for {waste_item.name}")
                return None
            
            # 5. Télécharger l'image
            image_data = self._download_image(image_url)
            if not image_data:
                logger.error(f"Failed to download image for {waste_item.name}")
                return None
            
            logger.info(f"✓ Successfully generated image for {waste_item.name}")
            return image_data
            
        except Exception as e:
            logger.error(f"Exception generating image for {waste_item.name}: {e}")
            return None
    
    def _test_api_connectivity(self) -> bool:
        """Test simple de connectivité à l'API Freepik avec toutes les clés"""
        try:
            # Tester avec chaque clé API disponible
            for i, api_key in enumerate(self.api_keys):
                headers = {"x-freepik-api-key": api_key}
                response = requests.get("https://api.freepik.com", headers=headers, timeout=10)
                if response.status_code in [200, 404, 405]:  # API accessible
                    logger.info(f"Clé API {i+1} ({api_key[:10]}...) : connexion OK")
                    return True
                else:
                    logger.warning(f"Clé API {i+1} ({api_key[:10]}...) : erreur {response.status_code}")
            return False
        except Exception as e:
            logger.warning(f"Test de connectivité API échoué: {e}")
            return False
    
    def _build_prompt(self, waste_item: CompetitionWasteItem) -> str:
        """Construit un prompt optimisé pour la génération d'image de déchets réalistes"""
        
        # Prompts spécialisés par type de déchet et zone - VRAIMENT des déchets
        base_prompts = {
            "menagers": {
                "residentielle": "Used dirty household waste item, garbage from home, discarded trash, worn out domestic refuse",
                "commerciale": "Discarded commercial waste, used office trash, thrown away business garbage, soiled refuse",
                "industrielle": "Industrial waste debris, factory refuse, discarded manufacturing materials, dirty industrial trash"
            },
            "dangereux": {
                "residentielle": "Discarded hazardous household waste, used dangerous materials, toxic waste container, contaminated refuse",
                "commerciale": "Used commercial hazardous waste, discarded toxic materials, contaminated business trash",
                "industrielle": "Industrial toxic waste, contaminated dangerous refuse, polluted hazardous materials, dirty chemical containers"
            },
            "recyclables": {
                "residentielle": "Used recyclable waste, dirty household recycling, soiled materials ready for recycling, worn out recyclables",
                "commerciale": "Discarded commercial recyclables, used business materials, soiled packaging waste, dirty office recycling",
                "industrielle": "Industrial recyclable waste, used factory materials, soiled manufacturing refuse, dirty production waste"
            }
        }
        
        # Construire le prompt principal
        base_prompt = base_prompts.get(waste_item.category, {}).get(
            waste_item.zone, 
            f"discarded {waste_item.category} waste item, dirty trash from {waste_item.zone} setting"
        )
        
        # Ajouter les détails spécifiques avec aspect usagé
        details = []
        if waste_item.colors:
            details.append(f"faded dirty {', '.join(waste_item.colors[:2])} color")
        if waste_item.materials:
            details.append(f"worn {', '.join(waste_item.materials[:2])} material")
        if waste_item.typical_forms:
            details.append(f"damaged {', '.join(waste_item.typical_forms[:2])} shape")
        
        # Prompt final optimisé pour des VRAIS déchets
        prompt = f"""
        Realistic photography of discarded {waste_item.name}, {base_prompt}.
        {', '.join(details) if details else ''}
        {waste_item.description} - thrown away, used, dirty, soiled
        
        Style: Realistic waste photography, dirty trash, used refuse, garbage appearance,
        soiled surface, worn out materials, discarded items, authentic waste look,
        stained and weathered, suitable for waste recognition training,
        clear waste identification, documentary trash photography, dirty texture,
        realistic refuse condition, abandoned garbage appearance.
        
        IMPORTANT: Make it look like REAL WASTE - dirty, used, discarded, soiled, stained.
        """.strip()
        
        return prompt
    
    def _create_generation_task(self, prompt: str) -> Optional[str]:
        """Crée une tâche de génération sur Freepik"""
        try:
            payload = {
                "prompt": prompt,
                "aspect_ratio": "square_1_1",
                "guidance_scale": 3.0,
            }
            
            # Les headers x-freepik-api-key sont maintenant gérés par _make_request_with_retry
            response = self._make_request_with_retry(
                'POST', 
                self.api_base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response and response.status_code == 200:
                data = response.json()
                task_id = data.get("data", {}).get("task_id")
                if task_id:
                    logger.debug(f"Created Freepik task: {task_id}")
                    return task_id
                else:
                    logger.error(f"No task_id in response: {data}")
            else:
                logger.error(f"Failed to create task: {response.status_code if response else 'No response'}")
                
        except Exception as e:
            logger.error(f"Exception creating task: {e}")
            
        return None
    
    def _wait_for_completion(self, task_id: str, max_wait_time: int = 120) -> Optional[str]:
        """Attend la completion de la tâche Freepik"""
        try:
            check_url = f"{self.api_base_url}/{task_id}"
            
            start_time = time.time()
            check_interval = 5
            
            while time.time() - start_time < max_wait_time:
                response = self._make_request_with_retry(
                    'GET', 
                    check_url,
                    timeout=30
                )
                
                if response and response.status_code == 200:
                    data = response.json()
                    task_data = data.get("data", {})
                    status = task_data.get("status")
                    
                    if status == "COMPLETED":
                        # Freepik retourne [dimensions, url] dans generated[]
                        generated_urls = task_data.get("generated", [])
                        
                        logger.debug(f"Generated array: {generated_urls}")
                        
                        if len(generated_urls) >= 2:
                            # Prendre le deuxième élément qui est l'URL
                            image_url = generated_urls[1]
                            
                            if image_url and str(image_url).startswith("http"):
                                logger.info(f"✓ Image URL obtained: {image_url[:100]}...")
                                return image_url
                            else:
                                logger.error(f"Invalid image URL format: {image_url}")
                        elif len(generated_urls) == 1:
                            # Fallback si un seul élément
                            url = generated_urls[0]
                            if str(url).startswith("http"):
                                return str(url)
                        
                        logger.error(f"No valid image URL found. Generated: {generated_urls}")
                        return None
                    elif status in ["FAILED", "CANCELLED"]:
                        logger.error(f"Task failed with status: {status}")
                        return None
                    elif status in ["CREATED", "PROCESSING", "IN_PROGRESS"]:
                        logger.debug(f"Task status: {status}, waiting...")
                        time.sleep(check_interval)
                        continue
                
                time.sleep(check_interval)
            
            logger.error(f"Timeout waiting for task completion: {task_id}")
            return None
            
        except Exception as e:
            logger.error(f"Exception waiting for completion: {e}")
            return None
    
    def _download_image(self, image_url: str) -> Optional[bytes]:
        """Télécharge l'image depuis l'URL Freepik"""
        try:
            response = self._make_request_with_retry(
                'GET',
                image_url,
                timeout=60,
                stream=True
            )
            
            if response and response.status_code == 200:
                image_data = response.content
                if len(image_data) > 0:
                    return image_data
                else:
                    logger.error("Empty image downloaded")
            else:
                logger.error(f"Failed to download image: {response.status_code if response else 'No response'}")
                
        except Exception as e:
            logger.error(f"Exception downloading image: {e}")
            
        return None

class PDFLayoutGenerator:
    """Générateur de mise en page PDF pour les cubes de déchets"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.image_size_cm = 3.0  # 3x3 cm
        self.dpi = 300
        self.image_size_px = int(self.image_size_cm * self.dpi / 12.54)  # Conversion cm to pixels
        
        # Configuration PDF
        self.page_width, self.page_height = A4
        self.margin = 1 * cm
        self.spacing = 0.2 * cm
        self.images_per_row = 10
        
    def create_category_pdf(self, category: str, waste_images: List[Tuple[CompetitionWasteItem, bytes]]) -> str:
        """Crée un PDF pour une catégorie de déchets avec page de bilan"""
        try:
            pdf_filename = f"competition_waste_{category}.pdf"
            pdf_path = self.output_dir / pdf_filename
            
            # Créer le canvas PDF
            c = canvas.Canvas(str(pdf_path), pagesize=A4)
            
            # 1. Créer la page de bilan en premier
            self._create_summary_page(c, category, waste_images)
            c.showPage()
            
            # 2. Créer les pages d'images
            self._create_images_pages(c, category, waste_images)
            
            # Finaliser le PDF
            c.save()
            
            logger.info(f"✓ PDF created: {pdf_path}")
            return str(pdf_path)
            
        except Exception as e:
            logger.error(f"Error creating PDF for {category}: {e}")
            return None
    
    def _create_summary_page(self, c: canvas.Canvas, category: str, waste_images: List[Tuple[CompetitionWasteItem, bytes]]):
        """Crée une page de résumé/bilan pour le PDF"""
        try:
            # Configuration de la page
            page_width, page_height = A4
            margin = 2 * cm
            
            # Titre principal
            c.setFont("Helvetica-Bold", 24)
            title = f"DATASET DÉCHETS - {category.upper()}"
            title_width = c.stringWidth(title, "Helvetica-Bold", 24)
            title_x = (page_width - title_width) / 2
            c.drawString(title_x, page_height - margin - 1*cm, title)
            
            # Sous-titre
            c.setFont("Helvetica", 14)
            subtitle = f"TRC 2025"
            subtitle_width = c.stringWidth(subtitle, "Helvetica", 14)
            subtitle_x = (page_width - subtitle_width) / 2
            c.drawString(subtitle_x, page_height - margin - 2*cm, subtitle)
            
            # Ligne de séparation
            c.setStrokeColor(black)
            c.setLineWidth(2)
            c.line(margin, page_height - margin - 2.5*cm, page_width - margin, page_height - margin - 2.5*cm)
            
            # Statistiques générales
            y_pos = page_height - margin - 4*cm
            c.setFont("Helvetica-Bold", 16)
            c.drawString(margin, y_pos, "📊 STATISTIQUES")
            
            y_pos -= 1*cm
            c.setFont("Helvetica", 12)
            stats_info = [
                f"• Total d'images dans cette catégorie: {len(waste_images)}",
                f"• Format d'impression: 3x3 cm",
                f"• Catégorie: {category.capitalize()}",
            ]
            
            for info in stats_info:
                c.drawString(margin + 0.5*cm, y_pos, info)
                y_pos -= 0.5*cm
            
            # Liste des déchets par zone
            y_pos -= 1*cm
            c.setFont("Helvetica-Bold", 16)
            c.drawString(margin, y_pos, "📋 LISTE DES DÉCHETS")
            
            # Grouper par zone
            zones_data = {}
            for waste_item, _ in waste_images:
                zone = waste_item.zone
                if zone not in zones_data:
                    zones_data[zone] = []
                zones_data[zone].append(waste_item)
            
            y_pos -= 0.8*cm
            for zone, items in zones_data.items():
                # Titre de zone
                c.setFont("Helvetica-Bold", 14)
                zone_title = f"🏢 ZONE {zone.upper()} ({len(items)} déchets)"
                c.drawString(margin + 0.5*cm, y_pos, zone_title)
                y_pos -= 0.6*cm
                
                # Liste des déchets de cette zone
                c.setFont("Helvetica", 11)
                for i, item in enumerate(items, 1):
                    if y_pos < margin + 3*cm:  # Nouvelle page si nécessaire
                        c.showPage()
                        y_pos = page_height - margin - 2*cm
                    
                    waste_info = f"   {i:2d}. {item.name.replace('_', ' ').title()}"
                    c.drawString(margin + 1*cm, y_pos, waste_info)
                    y_pos -= 0.4*cm
                
                y_pos -= 0.3*cm
            
            # Instructions d'utilisation
            if y_pos < margin + 6*cm:  # Nouvelle page si nécessaire
                c.showPage()
                y_pos = page_height - margin - 2*cm
            
            y_pos -= 1*cm
            c.setFont("Helvetica-Bold", 16)
            c.drawString(margin, y_pos, "📖 INSTRUCTIONS D'UTILISATION")
            
            y_pos -= 0.8*cm
            c.setFont("Helvetica", 12)
            instructions = [
                "1. Imprimer ce PDF sur papier A4 standard",
                "2. Chaque ligne contient 10 exemplaires du même déchet",
                "3. Découper chaque image le long des lignes (3x3 cm)",
                "4. Coller les images sur les faces des cubes de compétition",
                "5. Chaque cube représente un déchet de la catégorie spécifiée",
                "",
                "⚠️  IMPORTANT:",
                "• Respecter les dimensions 3x3 cm pour la reconnaissance",
                "• Garder les images bien alignées sur les cubes",
                "• Noter la catégorie et zone de chaque déchet"
            ]
            
            for instruction in instructions:
                if y_pos < margin + 1*cm:  # Nouvelle page si nécessaire
                    c.showPage()
                    y_pos = page_height - margin - 2*cm
                
                c.drawString(margin + 0.5*cm, y_pos, instruction)
                y_pos -= 0.5*cm
            
            # Footer
            c.setFont("Helvetica-Oblique", 10)
            footer_text = f"Généré automatiquement par Competition Waste Generator - {category}"
            footer_width = c.stringWidth(footer_text, "Helvetica-Oblique", 10)
            footer_x = (page_width - footer_width) / 2
            c.drawString(footer_x, margin, footer_text)
            
        except Exception as e:
            logger.error(f"Error creating summary page: {e}")
    
    def _create_images_pages(self, c: canvas.Canvas, category: str, waste_images: List[Tuple[CompetitionWasteItem, bytes]]):
        """Crée les pages avec les images de déchets"""
        try:
            # Calculer les positions
            image_size_points = self.image_size_cm * cm
            row_height = image_size_points + self.spacing
            
            current_y = self.page_height - self.margin - image_size_points
            row_count = 0
            
            logger.info(f"Creating image pages for category: {category}")
            
            for waste_item, image_data in tqdm(waste_images, desc=f"Adding {category} to PDF"):
                # Vérifier si on a besoin d'une nouvelle page
                if current_y < self.margin + image_size_points:
                    c.showPage()
                    current_y = self.page_height - self.margin - image_size_points
                    row_count = 0
                
                # Traiter et redimensionner l'image
                processed_image_data = self._process_image_for_pdf(image_data)
                if not processed_image_data:
                    logger.warning(f"Failed to process image for {waste_item.name}")
                    continue
                
                # Ajouter 10 images identiques sur la ligne
                current_x = self.margin
                for i in range(self.images_per_row):
                    if current_x + image_size_points > self.page_width - self.margin:
                        break
                    
                    # Dessiner l'image
                    c.drawInlineImage(
                        processed_image_data,
                        current_x,
                        current_y,
                        width=image_size_points,
                        height=image_size_points
                    )
                    
                    current_x += image_size_points + self.spacing
                
                current_y -= row_height
                row_count += 1
                
        except Exception as e:
            logger.error(f"Error creating image pages: {e}")
    
    def _process_image_for_pdf(self, image_data: bytes) -> Optional[BytesIO]:
        """Traite et redimensionne une image pour le PDF"""
        try:
            # Ouvrir l'image
            image = Image.open(BytesIO(image_data))
            
            # Redimensionner à la taille exacte (3x3 cm à 300 DPI)
            target_size = (self.image_size_px, self.image_size_px)
            image = image.resize(target_size, Image.Resampling.LANCZOS)
            
            # Convertir en RGB si nécessaire
            if image.mode in ("RGBA", "P"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "RGBA":
                    background.paste(image, mask=image.split()[-1])
                else:
                    background.paste(image)
                image = background
            
            # Retourner directement l'objet PIL Image pour ReportLab
            return image
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return None

class CompetitionDatasetGenerator:
    """Générateur principal du dataset pour la compétition"""
    
    def __init__(self, output_dir: str = "competition_waste_dataset"):
        self.output_dir = Path(output_dir)
        self.freepik_generator = FreepikImageGenerator()
        self.pdf_generator = PDFLayoutGenerator(self.output_dir)
        
        # Configuration
        self.max_workers = 1  # Séquentiel pour éviter les problèmes de rate limit
        
        # Créer les répertoires
        self._setup_directories()
        
        # Charger la configuration des déchets
        self.waste_items = self._load_waste_configuration()
        
        logger.info(f"Initialized generator with {len(self.waste_items)} waste items")
    
    def _setup_directories(self):
        """Créer la structure de répertoires"""
        directories = [
            self.output_dir,
            self.output_dir / "images",
            self.output_dir / "pdfs",
            self.output_dir / "logs",
            self.output_dir / "cache"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _load_waste_configuration(self) -> List[CompetitionWasteItem]:
        """Charge la configuration des déchets pour la compétition"""
        
        # Configuration des 14 types de déchets par zone
        waste_configs = {
            "menagers": {
                "residentielle": [
                    CompetitionWasteItem("bouteille_plastique", "menagers", "residentielle",
                                       "Bouteille en plastique domestique", 
                                       ["transparent", "bleu", "vert"], ["PET", "HDPE"], 
                                       ["bouteille", "cylindrique"]),
                    CompetitionWasteItem("sac_plastique", "menagers", "residentielle",
                                       "Sac plastique de courses",
                                       ["blanc", "noir", "coloré"], ["polyéthylène"],
                                       ["sac", "froissé"]),
                    CompetitionWasteItem("canette_aluminium", "menagers", "residentielle",
                                       "Canette de boisson en aluminium",
                                       ["argenté", "rouge", "bleu"], ["aluminium"],
                                       ["cylindrique", "canette"]),
                    CompetitionWasteItem("carton_alimentaire", "menagers", "residentielle",
                                       "Emballage carton alimentaire",
                                       ["brun", "blanc"], ["carton"], ["boîte", "plat"]),
                    CompetitionWasteItem("reste_alimentaire", "menagers", "residentielle",
                                       "Déchets alimentaires organiques",
                                       ["variable"], ["organique"], ["reste", "épluchure"])
                ],
                "commerciale": [
                    CompetitionWasteItem("papier_bureau", "menagers", "commerciale",
                                       "Papier de bureau usagé",
                                       ["blanc", "bleu"], ["papier"], ["feuille", "document"]),
                    CompetitionWasteItem("gobelet_plastique", "menagers", "commerciale",
                                       "Gobelet plastique jetable",
                                       ["blanc", "transparent"], ["plastique"], ["gobelet"]),
                    CompetitionWasteItem("emballage_alimentaire", "menagers", "commerciale",
                                       "Emballage fast-food",
                                       ["blanc", "coloré"], ["carton", "plastique"], ["boîte", "sachet"]),
                    CompetitionWasteItem("bouteille_verre", "menagers", "commerciale",
                                       "Bouteille en verre",
                                       ["transparent", "vert", "brun"], ["verre"], ["bouteille"]),
                    CompetitionWasteItem("canette_metal", "menagers", "commerciale",
                                       "Canette ou conserve métallique",
                                       ["argenté", "coloré"], ["métal", "aluminium"], ["cylindrique"])
                ],
                "industrielle": [
                    CompetitionWasteItem("film_plastique", "menagers", "industrielle",
                                       "Film plastique d'emballage industriel",
                                       ["transparent", "noir"], ["polyéthylène"], ["film", "rouleau"]),
                    CompetitionWasteItem("carton_ondule", "menagers", "industrielle",
                                       "Carton ondulé d'emballage",
                                       ["brun"], ["carton ondulé"], ["plaque", "boîte"]),
                    CompetitionWasteItem("palette_bois", "menagers", "industrielle",
                                       "Palette en bois usagée",
                                       ["brun", "naturel"], ["bois"], ["palette", "planche"]),
                    CompetitionWasteItem("bidon_plastique", "menagers", "industrielle",
                                       "Bidon plastique industriel",
                                       ["blanc", "bleu"], ["HDPE"], ["bidon", "jerrycan"])
                ]
            },
            "recyclables": {
                "residentielle": [
                    CompetitionWasteItem("journal_magazine", "recyclables", "residentielle",
                                       "Journaux et magazines",
                                       ["blanc", "coloré"], ["papier journal"], ["pile", "magazine"]),
                    CompetitionWasteItem("boite_conserve", "recyclables", "residentielle",
                                       "Boîte de conserve alimentaire",
                                       ["argenté"], ["acier", "fer blanc"], ["cylindrique", "boîte"]),
                    CompetitionWasteItem("bouteille_plastique_propre", "recyclables", "residentielle",
                                       "Bouteille plastique nettoyée",
                                       ["transparent", "bleu"], ["PET"], ["bouteille", "propre"]),
                    CompetitionWasteItem("verre_alimentaire", "recyclables", "residentielle",
                                       "Bocal ou bouteille en verre",
                                       ["transparent", "vert"], ["verre"], ["bocal", "bouteille"]),
                    CompetitionWasteItem("textile_propre", "recyclables", "residentielle",
                                       "Textile en bon état",
                                       ["variable"], ["coton", "synthétique"], ["vêtement", "tissu"])
                ],
                "commerciale": [
                    CompetitionWasteItem("papier_blanc", "recyclables", "commerciale",
                                       "Papier blanc de bureau",
                                       ["blanc"], ["papier"], ["feuille", "rame"]),
                    CompetitionWasteItem("carton_propre", "recyclables", "commerciale",
                                       "Carton d'emballage propre",
                                       ["brun", "blanc"], ["carton"], ["boîte", "plat"]),
                    CompetitionWasteItem("aluminium_propre", "recyclables", "commerciale",
                                       "Aluminium et canettes propres",
                                       ["argenté"], ["aluminium"], ["canette", "feuille"]),
                    CompetitionWasteItem("plastique_rigide", "recyclables", "commerciale",
                                       "Plastique rigide propre",
                                       ["variable"], ["HDPE", "PP"], ["conteneur", "boîte"]),
                    CompetitionWasteItem("verre_commercial", "recyclables", "commerciale",
                                       "Verre commercial (bouteilles, bocaux)",
                                       ["transparent", "vert", "brun"], ["verre"], ["bouteille", "bocal"])
                ],
                "industrielle": [
                    CompetitionWasteItem("metal_ferreux", "recyclables", "industrielle",
                                       "Ferraille et métaux ferreux",
                                       ["gris", "rouillé"], ["acier", "fer"], ["plaque", "poutre", "débris"]),
                    CompetitionWasteItem("metal_non_ferreux", "recyclables", "industrielle",
                                       "Métaux non ferreux (cuivre, aluminium)",
                                       ["cuivré", "argenté"], ["cuivre", "aluminium"], ["fil", "plaque", "profilé"]),
                    CompetitionWasteItem("plastique_industriel", "recyclables", "industrielle",
                                       "Plastiques industriels triés",
                                       ["variable"], ["HDPE", "PP", "PVC"], ["tuyau", "conteneur", "film"]),
                    CompetitionWasteItem("papier_carton_industriel", "recyclables", "industrielle",
                                       "Papiers et cartons industriels",
                                       ["brun", "blanc"], ["carton ondulé", "papier kraft"], ["balle", "plaque"])
                ]
            },
            "dangereux": {
                "residentielle": [
                    CompetitionWasteItem("pile_batterie", "dangereux", "residentielle",
                                       "Piles et petites batteries",
                                       ["noir", "argenté", "coloré"], ["lithium", "alcaline"], ["cylindrique", "rectangulaire"]),
                    CompetitionWasteItem("ampoule_neon", "dangereux", "residentielle",
                                       "Ampoules et tubes néon",
                                       ["blanc", "transparent"], ["verre", "mercure"], ["spirale", "tube", "bulbe"]),
                    CompetitionWasteItem("medicament_perime", "dangereux", "residentielle",
                                       "Médicaments périmés",
                                       ["blanc", "coloré"], ["plastique", "papier"], ["boîte", "flacon", "blister"]),
                    CompetitionWasteItem("produit_nettoyage", "dangereux", "residentielle",
                                       "Produits de nettoyage ménagers",
                                       ["coloré"], ["plastique"], ["flacon", "spray", "bidon"]),
                    CompetitionWasteItem("peinture_solvant", "dangereux", "residentielle",
                                       "Peintures et solvants domestiques",
                                       ["variable"], ["métal", "plastique"], ["pot", "bidon", "aérosol"])
                ],
                "commerciale": [
                    CompetitionWasteItem("cartouche_encre", "dangereux", "commerciale",
                                       "Cartouches d'encre d'imprimante",
                                       ["noir", "coloré"], ["plastique", "métal"], ["cartouche"]),
                    CompetitionWasteItem("produit_chimique_bureau", "dangereux", "commerciale",
                                       "Produits chimiques de bureau",
                                       ["variable"], ["plastique", "verre"], ["flacon", "spray"]),
                    CompetitionWasteItem("equipement_electronique", "dangereux", "commerciale",
                                       "Équipements électroniques usagés",
                                       ["noir", "gris"], ["plastique", "métal"], ["boîtier", "composant"]),
                    CompetitionWasteItem("batterie_vehicule", "dangereux", "commerciale",
                                       "Batteries de véhicules",
                                       ["noir", "rouge"], ["plomb", "acide"], ["rectangulaire", "lourde"]),
                    CompetitionWasteItem("huile_usagee", "dangereux", "commerciale",
                                       "Huiles usagées (moteur, hydraulique)",
                                       ["noir", "brun"], ["plastique", "métal"], ["bidon", "fût"])
                ],
                "industrielle": [
                    CompetitionWasteItem("dechet_chimique", "dangereux", "industrielle",
                                       "Déchets chimiques industriels",
                                       ["variable"], ["plastique", "verre", "métal"], ["fût", "conteneur", "cuve"]),
                    CompetitionWasteItem("dechet_medical", "dangereux", "industrielle",
                                       "Déchets médicaux et hospitaliers",
                                       ["rouge", "jaune"], ["plastique"], ["conteneur", "sac", "boîte"]),
                    CompetitionWasteItem("amiante", "dangereux", "industrielle",
                                       "Matériaux contenant de l'amiante",
                                       ["gris", "blanc"], ["fibrociment"], ["plaque", "tuyau", "debris"]),
                    CompetitionWasteItem("radioactif", "dangereux", "industrielle",
                                       "Déchets radioactifs de faible activité",
                                       ["jaune", "noir"], ["métal", "plastique"], ["fût", "conteneur", "blindé"])
                ]
            }
        }
        
        # Aplatir la configuration en liste
        waste_items = []
        for category, zones in waste_configs.items():
            for zone, items in zones.items():
                waste_items.extend(items)
        
        logger.info(f"Loaded {len(waste_items)} waste configurations")
        return waste_items
    
    def generate_all_images(self) -> Dict[str, List[Tuple[CompetitionWasteItem, bytes]]]:
        """Génère toutes les images en parallèle"""
        logger.info("Starting image generation for all waste items...")
        
        # Organiser par catégorie pour les PDFs
        images_by_category = {"menagers": [], "recyclables": [], "dangereux": []}
        
        # Vérifier le cache existant
        cached_items = self._load_cache()
        
        # Filtrer les éléments déjà générés
        items_to_generate = []
        for item in self.waste_items:
            cache_key = f"{item.category}_{item.zone}_{item.name}"
            if cache_key in cached_items:
                logger.info(f"Using cached image for {item.name}")
                images_by_category[item.category].append((item, cached_items[cache_key]))
            else:
                items_to_generate.append(item)
        
        if not items_to_generate:
            logger.info("All images already cached!")
            return images_by_category
        
        # Générer les images manquantes en parallèle
        logger.info(f"Generating {len(items_to_generate)} new images...")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Soumettre toutes les tâches
            future_to_item = {
                executor.submit(self.freepik_generator.generate_image, item): item
                for item in items_to_generate
            }
            
            # Collecter les résultats avec progress bar
            with tqdm(total=len(future_to_item), desc="Generating images") as pbar:
                for future in as_completed(future_to_item):
                    item = future_to_item[future]
                    try:
                        image_data = future.result()
                        if image_data:
                            images_by_category[item.category].append((item, image_data))
                            # Sauvegarder en cache
                            self._save_to_cache(item, image_data)
                            logger.info(f"✓ Generated: {item.name}")
                        else:
                            logger.error(f"✗ Failed: {item.name}")
                    except Exception as e:
                        logger.error(f"Exception for {item.name}: {e}")
                    
                    pbar.update(1)
        
        return images_by_category
    
    def generate_pdfs(self, images_by_category: Dict[str, List[Tuple[CompetitionWasteItem, bytes]]]) -> List[str]:
        """Génère les PDFs pour chaque catégorie"""
        logger.info("Generating PDFs...")
        
        pdf_paths = []
        
        for category, waste_images in images_by_category.items():
            if waste_images:
                logger.info(f"Creating PDF for category: {category} ({len(waste_images)} items)")
                pdf_path = self.pdf_generator.create_category_pdf(category, waste_images)
                if pdf_path:
                    pdf_paths.append(pdf_path)
            else:
                logger.warning(f"No images for category: {category}")
        
        return pdf_paths
    
    def _load_cache(self) -> Dict[str, bytes]:
        """Charge le cache des images déjà générées"""
        cache_file = self.output_dir / "cache" / "image_cache.json"
        cached_items = {}
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                for key, base64_data in cache_data.items():
                    try:
                        cached_items[key] = base64.b64decode(base64_data)
                    except Exception as e:
                        logger.warning(f"Failed to decode cached image {key}: {e}")
                
                logger.info(f"Loaded {len(cached_items)} cached images")
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        
        return cached_items
    
    def _save_to_cache(self, item: CompetitionWasteItem, image_data: bytes):
        """Sauvegarde une image dans le cache"""
        try:
            cache_dir = self.output_dir / "cache"
            cache_file = cache_dir / "image_cache.json"
            
            # Charger le cache existant
            cache_data = {}
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
            
            # Ajouter la nouvelle image
            cache_key = f"{item.category}_{item.zone}_{item.name}"
            cache_data[cache_key] = base64.b64encode(image_data).decode('utf-8')
            
            # Sauvegarder
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
            
            # Sauvegarder aussi l'image individuelle
            image_file = cache_dir / f"{cache_key}.jpg"
            with open(image_file, 'wb') as f:
                f.write(image_data)
                
        except Exception as e:
            logger.warning(f"Failed to save cache for {item.name}: {e}")
    
    def run_full_generation(self) -> Dict[str, any]:
        """Lance la génération complète du dataset"""
        start_time = time.time()
        
        logger.info("=" * 60)
        logger.info("COMPETITION WASTE DATASET GENERATOR")
        logger.info("=" * 60)
        logger.info(f"Total waste items to generate: {len(self.waste_items)}")
        logger.info(f"Categories: menagers, recyclables, dangereux")
        logger.info(f"Zones: residentielle, commerciale, industrielle")
        logger.info(f"Output directory: {self.output_dir}")
        
        try:
            # Étape 1: Générer toutes les images
            images_by_category = self.generate_all_images()
            
            # Étape 2: Créer les PDFs
            pdf_paths = self.generate_pdfs(images_by_category)
            
            # Statistiques finales
            total_generated = sum(len(images) for images in images_by_category.values())
            elapsed_time = time.time() - start_time
            
            result = {
                "success": True,
                "total_items": len(self.waste_items),
                "generated_images": total_generated,
                "generated_pdfs": len(pdf_paths),
                "pdf_paths": pdf_paths,
                "elapsed_time": elapsed_time,
                "images_by_category": {
                    cat: len(images) for cat, images in images_by_category.items()
                }
            }
            
            logger.info("=" * 60)
            logger.info("GENERATION COMPLETE!")
            logger.info(f"✓ Generated {total_generated}/{len(self.waste_items)} images")
            logger.info(f"✓ Created {len(pdf_paths)} PDF files")
            logger.info(f"✓ Total time: {elapsed_time:.1f} seconds")
            logger.info(f"✓ Output: {self.output_dir}")
            logger.info("=" * 60)
            
            return result
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "elapsed_time": time.time() - start_time
            }

def main():
    """Fonction principale"""
    try:
        # Vérifier les variables d'environnement - au moins une clé API doit être définie
        has_api_key = False
        if os.getenv("FREEPIK_API_KEY"):
            has_api_key = True
        else:
            # Vérifier les clés additionnelles
            for i in range(1, 10):
                if os.getenv(f"FREEPIK_API_KEY_{i}"):
                    has_api_key = True
                    break
        
        if not has_api_key:
            logger.error("Aucune clé API Freepik trouvée!")
            logger.error("Définissez au moins FREEPIK_API_KEY ou FREEPIK_API_KEY_1 dans votre fichier .env")
            return
        
        # Créer et lancer le générateur
        generator = CompetitionDatasetGenerator("competition_waste_dataset")
        result = generator.run_full_generation()
        
        if result["success"]:
            print("\n" + "="*60)
            print("🎉 GENERATION SUCCESSFUL!")
            print(f"📊 Images: {result['generated_images']}/{result['total_items']}")
            print(f"📄 PDFs: {result['generated_pdfs']}")
            print(f"⏱️  Time: {result['elapsed_time']:.1f}s")
            print(f"📁 Output: competition_waste_dataset/")
            print("\n📋 Next steps:")
            print("1. Check the PDFs in competition_waste_dataset/pdfs/")
            print("2. Print the PDFs on A4 paper")
            print("3. Cut the 3x3 cm squares")
            print("4. Apply to your competition cubes")
            print("="*60)
        else:
            print(f"\n❌ Generation failed: {result.get('error', 'Unknown error')}")
            
    except KeyboardInterrupt:
        print("\n⏹️  Generation interrupted by user")
    except Exception as e:
        logger.error(f"Main execution error: {e}")
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
