#!/usr/bin/env python3
"""
Générateur d'images de déchets pour compétition de robotique - VERSION CORRIGÉE
===============================================================================

Génère des images de déchets via l'API Freepik pour une compétition de robotique.
Organise les déchets en 3 catégories (Ménagers, Dangereux, Recyclables) 
avec 42 images par catégorie = 126 images total.

CORRECTIONS MAJEURES:
- Réparation de la qualité PDF (images floues/pixelisées)
- Simplification de la gestion des clés API 
- Correction de la distribution: 42 images par catégorie

Auteur: Assistant IA (Version corrigée)
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
    """Générateur d'images via l'API Freepik avec utilisation simultanée des clés"""
    
    def __init__(self):
        # CORRECTION: Vraie gestion simultanée des clés API
        self.api_keys = self._load_api_keys()
        
        if not self.api_keys:
            raise ValueError("Aucune clé API Freepik configurée")
        
        self.api_base_url = "https://api.freepik.com/v1/ai/text-to-image"
        self.max_retries = 2
        self.base_delay = 2.0
        
        # Statistiques par clé pour monitoring
        self.key_stats = {key: {"success": 0, "failed": 0} for key in self.api_keys}
        
        logger.info(f"Initialized with {len(self.api_keys)} API keys for simultaneous use")
    
    def _load_api_keys(self) -> List[str]:
        """Charge toutes les clés API disponibles"""
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
        
        # CORRECTION: Validation simple sans test complexe
        valid_keys = []
        for i, key in enumerate(keys):
            if len(key) > 10:  # Validation basique de longueur
                valid_keys.append(key)
                logger.info(f"API Key {i+1}: {key[:8]}... loaded")
            else:
                logger.warning(f"API Key {i+1}: Invalid format, skipped")
        
        return valid_keys
    
    def get_next_api_key(self) -> str:
        """Distribution équitable des clés pour utilisation simultanée"""
        # Utiliser la clé avec le moins d'utilisations pour équilibrer la charge
        return min(self.api_keys, key=lambda k: self.key_stats[k]["success"] + self.key_stats[k]["failed"])
    
    def generate_image(self, waste_item: CompetitionWasteItem) -> Optional[bytes]:
        """Interface de compatibilité - utilise la première clé disponible"""
        return self.generate_image_with_key(waste_item, self.get_next_api_key())
    
    def generate_image_with_key(self, waste_item: CompetitionWasteItem, assigned_key: str) -> Optional[bytes]:
        """Génère une image avec une clé API spécifique assignée"""
        try:
            prompt = self._build_simple_prompt(waste_item)
            logger.info(f"[Key {assigned_key[:8]}...] Generating: {waste_item.name}")
            
            for attempt in range(self.max_retries + 1):
                try:
                    if attempt > 0:
                        delay = self.base_delay * attempt + random.uniform(0, 1)
                        time.sleep(delay)
                        logger.info(f"[Key {assigned_key[:8]}...] Retry {attempt} for {waste_item.name}")
                    
                    image_data = self._generate_with_specific_key(prompt, assigned_key)
                    if image_data:
                        self.key_stats[assigned_key]["success"] += 1
                        logger.info(f"[Key {assigned_key[:8]}...] ✓ {waste_item.name}")
                        return image_data
                        
                except Exception as e:
                    logger.warning(f"[Key {assigned_key[:8]}...] Attempt {attempt + 1} failed for {waste_item.name}: {e}")
                    if attempt == self.max_retries:
                        self.key_stats[assigned_key]["failed"] += 1
            
            logger.error(f"[Key {assigned_key[:8]}...] ✗ All attempts failed for {waste_item.name}")
            return None
            
        except Exception as e:
            logger.error(f"[Key {assigned_key[:8]}...] Exception for {waste_item.name}: {e}")
            self.key_stats[assigned_key]["failed"] += 1
            return None
    
    def _build_simple_prompt(self, waste_item: CompetitionWasteItem) -> str:
        """CORRECTION: Prompt court et efficace"""
        # Prompts courts et précis
        base_descriptions = {
            "menagers": "household garbage waste",
            "recyclables": "recyclable waste material", 
            "dangereux": "hazardous waste container"
        }
        
        zone_context = {
            "residentielle": "home",
            "commerciale": "office", 
            "industrielle": "factory"
        }
        
        base = base_descriptions.get(waste_item.category, "waste")
        context = zone_context.get(waste_item.zone, "")
        
        # Prompt final court
        prompt = f"realistic {waste_item.name.replace('_', ' ')} {base} from {context}, used dirty refuse, white background"
        
        return prompt
    
    def _generate_with_specific_key(self, prompt: str, api_key: str) -> Optional[bytes]:
        """Génère une image avec une clé API spécifique"""
        headers = {
            "x-freepik-api-key": api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "prompt": prompt,
            "aspect_ratio": "square_1_1",
            "guidance_scale": 3.0,
        }
        
        # Créer la tâche
        response = requests.post(
            f"{self.api_base_url}/seedream",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"Task creation failed: {response.status_code}")
        
        task_data = response.json()
        task_id = task_data.get("data", {}).get("task_id")
        
        if not task_id:
            raise Exception("No task_id received")
        
        # Attendre la completion
        image_url = self._wait_for_completion(task_id, api_key)
        if not image_url:
            raise Exception("Image generation timeout")
        
        # Télécharger l'image
        img_response = requests.get(image_url, timeout=60)
        if img_response.status_code == 200:
            return img_response.content
        else:
            raise Exception(f"Download failed: {img_response.status_code}")
    
    def get_statistics(self) -> Dict[str, Dict[str, int]]:
        """Retourne les statistiques d'utilisation par clé"""
        return self.key_stats.copy()
    
    def _wait_for_completion(self, task_id: str, api_key: str, max_wait: int = 60) -> Optional[str]:
        """Attend la completion de la tâche"""
        headers = {"x-freepik-api-key": api_key}
        check_url = f"{self.api_base_url}/seedream/{task_id}"
        
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
                time.sleep(5)
        
        return None

class PDFLayoutGenerator:
    """Générateur de mise en page PDF pour les cubes de déchets - VERSION CORRIGÉE"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.image_size_cm = 3.0
        
        # CORRECTION: DPI et conversion corrects
        self.dpi = 300
        self.image_size_px = int(self.image_size_cm * self.dpi / 2.54)  # Conversion cm vers pixels
        
        # Configuration PDF
        self.page_width, self.page_height = A4
        self.margin = 1 * cm
        self.spacing = 0.2 * cm
        self.images_per_row = 10
        
        logger.info(f"PDF config: {self.image_size_px}px images, {self.dpi} DPI")
    
    def create_category_pdf(self, category: str, waste_images: List[Tuple[CompetitionWasteItem, bytes]]) -> str:
        """Crée un PDF pour une catégorie de déchets"""
        try:
            pdf_filename = f"competition_waste_{category}.pdf"
            pdf_path = self.output_dir / pdf_filename
            
            c = canvas.Canvas(str(pdf_path), pagesize=A4)
            
            # Page de résumé
            self._create_summary_page(c, category, waste_images)
            c.showPage()
            
            # Pages d'images avec qualité corrigée
            self._create_high_quality_images_pages(c, category, waste_images)
            
            c.save()
            logger.info(f"✓ PDF created: {pdf_path}")
            return str(pdf_path)
            
        except Exception as e:
            logger.error(f"Error creating PDF for {category}: {e}")
            return None
    
    def _create_high_quality_images_pages(self, c: canvas.Canvas, category: str, waste_images: List[Tuple[CompetitionWasteItem, bytes]]):
        """CORRECTION: Pages d'images haute qualité sans flou"""
        try:
            image_size_points = self.image_size_cm * cm
            row_height = image_size_points + self.spacing
            
            current_y = self.page_height - self.margin - image_size_points
            
            for waste_item, image_data in tqdm(waste_images, desc=f"Adding {category} to PDF"):
                # Nouvelle page si nécessaire
                if current_y < self.margin + image_size_points:
                    c.showPage()
                    current_y = self.page_height - self.margin - image_size_points
                
                # CORRECTION: Traitement haute qualité de l'image
                processed_image = self._process_image_high_quality(image_data)
                if not processed_image:
                    logger.warning(f"Failed to process image for {waste_item.name}")
                    continue
                
                # Ajouter 10 images identiques sur la ligne
                current_x = self.margin
                for i in range(self.images_per_row):
                    if current_x + image_size_points > self.page_width - self.margin:
                        break
                    
                    # CORRECTION: Utilisation correcte de drawImage avec BytesIO
                    c.drawImage(
                        processed_image,
                        current_x,
                        current_y,
                        width=image_size_points,
                        height=image_size_points,
                        preserveAspectRatio=True
                    )
                    
                    current_x += image_size_points + self.spacing
                
                current_y -= row_height
                
        except Exception as e:
            logger.error(f"Error creating image pages: {e}")
    
    def _process_image_high_quality(self, image_data: bytes) -> Optional[BytesIO]:
        """CORRECTION: Traitement haute qualité pour éviter le flou"""
        try:
            # Ouvrir l'image source
            source_image = Image.open(BytesIO(image_data))
            
            # CORRECTION: Redimensionnement haute qualité avec anti-aliasing
            target_size = (self.image_size_px, self.image_size_px)
            
            # Utiliser LANCZOS pour la meilleure qualité de redimensionnement
            processed_image = source_image.resize(target_size, Image.Resampling.LANCZOS)
            
            # Convertir en RGB si nécessaire (éviter les problèmes RGBA)
            if processed_image.mode in ("RGBA", "P"):
                background = Image.new("RGB", processed_image.size, (255, 255, 255))
                if processed_image.mode == "RGBA":
                    background.paste(processed_image, mask=processed_image.split()[-1])
                else:
                    background.paste(processed_image)
                processed_image = background
            
            # CORRECTION: Sauvegarder en BytesIO avec DPI explicite et haute qualité
            output = BytesIO()
            processed_image.save(
                output, 
                format='JPEG', 
                quality=95,  # Haute qualité JPEG
                dpi=(self.dpi, self.dpi),  # DPI explicite
                optimize=False  # Pas d'optimisation qui pourrait dégrader
            )
            output.seek(0)
            
            logger.debug(f"Processed image: {target_size} at {self.dpi} DPI")
            return output
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return None
    
    def _create_summary_page(self, c: canvas.Canvas, category: str, waste_images: List[Tuple[CompetitionWasteItem, bytes]]):
        """Page de résumé simplifiée"""
        page_width, page_height = A4
        margin = 2 * cm
        
        # Titre
        c.setFont("Helvetica-Bold", 24)
        title = f"DATASET DÉCHETS - {category.upper()}"
        title_width = c.stringWidth(title, "Helvetica-Bold", 24)
        title_x = (page_width - title_width) / 2
        c.drawString(title_x, page_height - margin - 1*cm, title)
        
        # Statistiques
        y_pos = page_height - margin - 4*cm
        c.setFont("Helvetica", 14)
        stats = [
            f"Total d'images: {len(waste_images)}",
            f"Format: 3x3 cm à {self.dpi} DPI",
            f"Catégorie: {category.capitalize()}",
            "",
            "Instructions:",
            "1. Imprimer sur papier A4",
            "2. Découper chaque carré 3x3 cm", 
            "3. Coller sur les cubes de compétition"
        ]
        
        for stat in stats:
            c.drawString(margin, y_pos, stat)
            y_pos -= 0.7*cm

class CompetitionDatasetGenerator:
    """Générateur principal du dataset pour la compétition - VERSION CORRIGÉE"""
    
    def __init__(self, output_dir: str = "competition_waste_dataset"):
        self.output_dir = Path(output_dir)
        self.freepik_generator = FreepikImageGenerator()
        self.pdf_generator = PDFLayoutGenerator(self.output_dir)
        
        self.max_workers = 2  # Légèrement parallélisé
        
        self._setup_directories()
        
        # CORRECTION: Configuration corrigée pour 42 items par catégorie
        self.waste_items = self._load_corrected_waste_configuration()
        
        logger.info(f"Initialized with {len(self.waste_items)} waste items")
        logger.info(f"Distribution: {self._count_by_category()}")
    
    def _setup_directories(self):
        """Créer la structure de répertoires"""
        directories = [
            self.output_dir,
            self.output_dir / "images", 
            self.output_dir / "pdfs",
            self.output_dir / "cache"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _load_corrected_waste_configuration(self) -> List[CompetitionWasteItem]:
        """CORRECTION: Configuration pour exactement 42 items par catégorie"""
        
        # 14 types de base par catégorie, répartis sur les 3 zones
        waste_types = {
            "menagers": [
                # Zone résidentielle (14 items)
                ("bouteille_plastique_eau", "residentielle", "Bouteille d'eau plastique domestique", ["transparent", "bleu"], ["PET"], ["bouteille"]),
                ("sac_plastique_courses", "residentielle", "Sac plastique de supermarché", ["blanc", "noir"], ["LDPE"], ["sac"]),
                ("canette_soda", "residentielle", "Canette de soda aluminium", ["rouge", "bleu"], ["aluminium"], ["cylindrique"]),
                ("boite_cereales", "residentielle", "Boîte de céréales carton", ["coloré"], ["carton"], ["rectangulaire"]),
                ("reste_fruit", "residentielle", "Reste de fruits organiques", ["variable"], ["organique"], ["épluchure"]),
                ("journal_quotidien", "residentielle", "Journal quotidien papier", ["noir", "blanc"], ["papier"], ["pages"]),
                ("pot_yaourt", "residentielle", "Pot de yaourt plastique", ["blanc"], ["polystyrène"], ["pot"]),
                ("bouteille_lait", "residentielle", "Bouteille de lait plastique", ["blanc"], ["HDPE"], ["bouteille"]),
                ("boite_conserve_tomate", "residentielle", "Boîte de conserve tomates", ["rouge"], ["fer blanc"], ["cylindrique"]),
                ("sachet_chips", "residentielle", "Sachet de chips métallisé", ["argenté"], ["aluminium"], ["sachet"]),
                ("gobelet_cafe", "residentielle", "Gobelet café carton", ["brun"], ["carton"], ["gobelet"]),
                ("emballage_biscuit", "residentielle", "Emballage de biscuits plastique", ["coloré"], ["plastique"], ["sachet"]),
                ("bouteille_huile", "residentielle", "Bouteille d'huile verre", ["vert"], ["verre"], ["bouteille"]),
                ("barquette_viande", "residentielle", "Barquette viande polystyrène", ["blanc"], ["polystyrène"], ["barquette"]),
                
                # Zone commerciale (14 items)
                ("gobelet_distributeur", "commerciale", "Gobelet distributeur plastique", ["blanc"], ["PS"], ["gobelet"]),
                ("canette_cafe", "commerciale", "Canette café métallique", ["noir"], ["aluminium"], ["cylindrique"]),
                ("emballage_sandwich", "commerciale", "Emballage sandwich carton", ["blanc"], ["carton"], ["triangulaire"]),
                ("bouteille_eau_bureau", "commerciale", "Bouteille eau bureau plastique", ["transparent"], ["PET"], ["bouteille"]),
                ("sachet_sucre", "commerciale", "Sachet sucre papier", ["blanc"], ["papier"], ["sachet"]),
                ("barquette_salade", "commerciale", "Barquette salade plastique", ["transparent"], ["PET"], ["rectangulaire"]),
                ("pot_sauce", "commerciale", "Pot sauce plastique", ["blanc"], ["PP"], ["pot"]),
                ("canette_the", "commerciale", "Canette thé glacé", ["vert"], ["aluminium"], ["cylindrique"]),
                ("emballage_croissant", "commerciale", "Emballage croissanterie", ["transparent"], ["plastique"], ["sachet"]),
                ("bouteille_jus", "commerciale", "Bouteille jus de fruit", ["orange"], ["PET"], ["bouteille"]),
                ("boite_pizza", "commerciale", "Boîte pizza carton", ["blanc"], ["carton ondulé"], ["carrée"]),
                ("gobelet_glace", "commerciale", "Gobelet glace carton", ["coloré"], ["carton"], ["conique"]),
                ("sachet_ketchup", "commerciale", "Sachet ketchup plastique", ["rouge"], ["plastique"], ["sachet"]),
                ("bouteille_smoothie", "commerciale", "Bouteille smoothie plastique", ["coloré"], ["PET"], ["bouteille"]),
                
                # Zone industrielle (14 items)
                ("bidon_eau_5L", "industrielle", "Bidon eau 5L industriel", ["bleu"], ["HDPE"], ["bidon"]),
                ("sac_ciment", "industrielle", "Sac ciment papier kraft", ["brun"], ["papier kraft"], ["sac"]),
                ("feuillard_acier", "industrielle", "Feuillard acier d'emballage", ["gris"], ["acier"], ["bande"]),
                ("film_plastique_palette", "industrielle", "Film plastique palette", ["transparent"], ["LDPE"], ["film"]),
                ("bidon_huile_moteur", "industrielle", "Bidon huile moteur plastique", ["noir"], ["HDPE"], ["bidon"]),
                ("carton_ondule_grand", "industrielle", "Grand carton ondulé", ["brun"], ["carton ondulé"], ["plaque"]),
                ("sangle_textile", "industrielle", "Sangle textile d'arrimage", ["coloré"], ["polyester"], ["sangle"]),
                ("jerrycan_20L", "industrielle", "Jerrycan 20L plastique", ["rouge"], ["HDPE"], ["jerrycan"]),
                ("palette_bois_cassee", "industrielle", "Palette bois cassée", ["brun"], ["bois"], ["palette"]),
                ("big_bag_vide", "industrielle", "Big bag textile vide", ["blanc"], ["polypropylène"], ["sac"]),
                ("tuyau_plastique", "industrielle", "Tuyau plastique souple", ["noir"], ["PVC"], ["tuyau"]),
                ("caisse_plastique", "industrielle", "Caisse plastique industrielle", ["gris"], ["PP"], ["caisse"]),
                ("fût_metal_200L", "industrielle", "Fût métallique 200L", ["bleu"], ["acier"], ["cylindrique"]),
                ("rouleau_carton", "industrielle", "Rouleau carton d'emballage", ["brun"], ["carton"], ["cylindrique"])
            ],
            
            "recyclables": [
                # Zone résidentielle (14 items)
                ("bouteille_verre_vin", "residentielle", "Bouteille vin verre propre", ["vert"], ["verre"], ["bouteille"]),
                ("journal_propre", "residentielle", "Journal papier propre", ["blanc"], ["papier journal"], ["pile"]),
                ("canette_alu_propre", "residentielle", "Canette aluminium propre", ["argenté"], ["aluminium"], ["cylindrique"]),
                ("boite_carton_propre", "residentielle", "Boîte carton alimentaire propre", ["brun"], ["carton"], ["boîte"]),
                ("bouteille_plastique_propre", "residentielle", "Bouteille plastique nettoyée", ["transparent"], ["PET"], ["bouteille"]),
                ("bocal_verre_propre", "residentielle", "Bocal verre alimentaire propre", ["transparent"], ["verre"], ["bocal"]),
                ("magazine_propre", "residentielle", "Magazine papier glacé", ["coloré"], ["papier glacé"], ["magazine"]),
                ("boite_metal_propre", "residentielle", "Boîte métal conserve propre", ["argenté"], ["fer blanc"], ["cylindrique"]),
                ("carton_lait_propre", "residentielle", "Carton lait tétrapack propre", ["blanc"], ["carton plastifié"], ["tétrapack"]),
                ("vetement_coton", "residentielle", "Vêtement coton usagé", ["variable"], ["coton"], ["textile"]),
                ("chaussure_cuir", "residentielle", "Chaussure cuir usagée", ["brun"], ["cuir"], ["chaussure"]),
                ("livre_papier", "residentielle", "Livre papier usagé", ["variable"], ["papier"], ["livre"]),
                ("sac_tissu", "residentielle", "Sac tissu réutilisable", ["variable"], ["tissu"], ["sac"]),
                ("bouteille_verre_huile", "residentielle", "Bouteille huile verre propre", ["vert"], ["verre"], ["bouteille"]),
                
                # Zone commerciale (14 items)
                ("papier_bureau_blanc", "commerciale", "Papier bureau blanc A4", ["blanc"], ["papier"], ["feuilles"]),
                ("carton_emballage", "commerciale", "Carton emballage commercial", ["brun"], ["carton ondulé"], ["boîte"]),
                ("canette_boisson_propre", "commerciale", "Canette boisson nettoyée", ["coloré"], ["aluminium"], ["cylindrique"]),
                ("bouteille_eau_propre", "commerciale", "Bouteille eau PET propre", ["transparent"], ["PET"], ["bouteille"]),
                ("verre_restaurant", "commerciale", "Verre restaurant cassé", ["transparent"], ["verre"], ["verre"]),
                ("plastique_rigide_propre", "commerciale", "Plastique rigide PP propre", ["variable"], ["PP"], ["conteneur"]),
                ("metal_canette_grande", "commerciale", "Grande canette métal 50cl", ["coloré"], ["aluminium"], ["cylindrique"]),
                ("carton_pizza_propre", "commerciale", "Carton pizza sans graisse", ["blanc"], ["carton"], ["carré"]),
                ("bouteille_verre_biere", "commerciale", "Bouteille bière verre brune", ["brun"], ["verre"], ["bouteille"]),
                ("papier_journal_commercial", "commerciale", "Journaux distribution gratuite", ["coloré"], ["papier journal"], ["pile"]),
                ("emballage_carton_sec", "commerciale", "Emballage carton sec", ["variable"], ["carton"], ["boîte"]),
                ("plastique_transparent", "commerciale", "Plastique transparent PET", ["transparent"], ["PET"], ["conteneur"]),
                ("metal_conserve_grande", "commerciale", "Grande conserve métal 1L", ["argenté"], ["fer blanc"], ["cylindrique"]),
                ("verre_bocal_1L", "commerciale", "Bocal verre 1L commercial", ["transparent"], ["verre"], ["bocal"]),
                
                # Zone industrielle (14 items)
                ("ferraille_acier", "industrielle", "Ferraille acier découpée", ["gris"], ["acier"], ["debris"]),
                ("aluminium_industriel", "industrielle", "Aluminium industriel massif", ["argenté"], ["aluminium"], ["plaque"]),
                ("cuivre_fil", "industrielle", "Fil cuivre électrique", ["cuivré"], ["cuivre"], ["bobine"]),
                ("plastique_HDPE_industriel", "industrielle", "Plastique HDPE industriel", ["coloré"], ["HDPE"], ["bloc"]),
                ("carton_ondule_industriel", "industrielle", "Carton ondulé industriel", ["brun"], ["carton ondulé"], ["plaque"]),
                ("papier_kraft_industriel", "industrielle", "Papier kraft industriel", ["brun"], ["papier kraft"], ["rouleau"]),
                ("metal_inox", "industrielle", "Acier inoxydable industriel", ["argenté"], ["inox"], ["plaque"]),
                ("plastique_PP_industriel", "industrielle", "Polypropylène industriel", ["variable"], ["PP"], ["conteneur"]),
                ("verre_industriel", "industrielle", "Verre industriel cassé", ["transparent"], ["verre"], ["debris"]),
                ("bronze_industriel", "industrielle", "Bronze industriel usagé", ["bronze"], ["bronze"], ["pièce"]),
                ("plastique_PVC_tuyau", "industrielle", "Tuyau PVC industriel", ["gris"], ["PVC"], ["tuyau"]),
                ("carton_compacte", "industrielle", "Carton compacté industriel", ["brun"], ["carton"], ["balle"]),
                ("metal_zinc", "industrielle", "Zinc industriel oxydé", ["gris"], ["zinc"], ["plaque"]),
                ("plastique_PE_film", "industrielle", "Film PE industriel", ["transparent"], ["PE"], ["film"])
            ],
            
            "dangereux": [
                # Zone résidentielle (14 items) 
                ("pile_alcaline", "residentielle", "Pile alcaline AA/AAA usée", ["noir"], ["alcaline"], ["cylindrique"]),
                ("batterie_telephone", "residentielle", "Batterie téléphone lithium", ["noir"], ["lithium"], ["rectangulaire"]),
                ("ampoule_led_cassee", "residentielle", "Ampoule LED cassée", ["blanc"], ["verre", "électronique"], ["ampoule"]),
                ("tube_neon_casse", "residentielle", "Tube néon cassé mercure", ["blanc"], ["verre", "mercure"], ["tube"]),
                ("medicament_expire", "residentielle", "Médicaments expirés", ["blanc", "coloré"], ["plastique"], ["boîte", "flacon"]),
                ("produit_nettoyage_vide", "residentielle", "Produit nettoyage domestique vide", ["coloré"], ["plastique"], ["flacon"]),
                ("peinture_pot_vide", "residentielle", "Pot peinture domestique vide", ["variable"], ["métal"], ["pot"]),
                ("aerosol_vide", "residentielle", "Aérosol domestique vide", ["coloré"], ["métal"], ["cylindrique"]),
                ("thermometre_mercure", "residentielle", "Thermomètre mercure cassé", ["argenté"], ["verre", "mercure"], ["tube"]),
                ("pile_bouton", "residentielle", "Pile bouton lithium", ["argenté"], ["lithium"], ["ronde"]),
                ("chargeur_telephone", "residentielle", "Chargeur téléphone défaillant", ["noir"], ["plastique", "métal"], ["câble"]),
                ("produit_jardinage", "residentielle", "Produit jardinage toxique", ["coloré"], ["plastique"], ["bidon"]),
                ("huile_vidange", "residentielle", "Huile vidange moteur domestique", ["noir"], ["plastique"], ["bidon"]),
                ("solvant_bricolage", "residentielle", "Solvant bricolage domestique", ["variable"], ["métal"], ["bidon"]),
                ("insecticide_aerosol", "residentielle", "Insecticide aérosol vide", ["coloré"], ["métal"], ["cylindrique"]),
                ("dechets_electronique", "residentielle", "Déchets électroniques domestiques", ["noir"], ["plastique", "métal"], ["appareil"]),
                ("produit_chimique_piscine", "residentielle", "Produit chimique piscine", ["bleu"], ["plastique"], ["bidon"]),
                
                # Zone commerciale (14 items)
                ("cartouche_imprimante", "commerciale", "Cartouche imprimante usée", ["noir", "coloré"], ["plastique"], ["cartouche"]),
                ("batterie_ordinateur", "commerciale", "Batterie ordinateur portable", ["noir"], ["lithium"], ["rectangulaire"]),
                ("ecran_lcd_casse", "commerciale", "Écran LCD cassé", ["noir"], ["verre", "mercure"], ["plat"]),
                ("produit_chimique_labo", "commerciale", "Produit chimique laboratoire", ["variable"], ["verre"], ["flacon"]),
                ("huile_hydraulique", "commerciale", "Huile hydraulique usée", ["rouge"], ["plastique"], ["bidon"]),
                ("batterie_vehicule_12V", "commerciale", "Batterie véhicule 12V", ["noir"], ["plomb", "acide"], ["rectangulaire"]),
                ("liquide_refroidissement", "commerciale", "Liquide refroidissement auto", ["vert"], ["plastique"], ["bidon"]),
                ("cartouche_toner", "commerciale", "Cartouche toner laser", ["noir"], ["plastique"], ["cylindrique"]),
                ("produit_photographique", "commerciale", "Produit développement photo", ["brun"], ["plastique"], ["flacon"]),
                ("disque_dur_defaillant", "commerciale", "Disque dur défaillant", ["gris"], ["métal"], ["rectangulaire"]),
                ("condensateur_pcb", "commerciale", "Condensateur PCB usé", ["gris"], ["métal"], ["cylindrique"]),
                ("liquide_frein", "commerciale", "Liquide frein automobile", ["jaune"], ["plastique"], ["flacon"]),
                ("batterie_ups", "commerciale", "Batterie onduleur UPS", ["noir"], ["plomb"], ["rectangulaire"]),
                ("produit_colle_industriel", "commerciale", "Colle industrielle époxy", ["variable"], ["métal"], ["tube"]),
                
                # Zone industrielle (14 items) - CORRECTION: exactement 14 pour avoir 42 total
                ("dechet_chimique_fût", "industrielle", "Déchet chimique en fût", ["bleu"], ["métal"], ["fût"]),
                ("dechet_medical_hopital", "industrielle", "Déchet médical hospitalier", ["rouge"], ["plastique"], ["conteneur"]),
                ("amiante_plaque", "industrielle", "Plaque fibrociment amiante", ["gris"], ["fibrociment"], ["plaque"]),
                ("dechet_radioactif_faible", "industrielle", "Déchet radioactif faible activité", ["jaune"], ["métal"], ["fût"]),
                ("solvant_industriel", "industrielle", "Solvant industriel chloré", ["transparent"], ["métal"], ["bidon"]),
                ("acide_industriel", "industrielle", "Acide industriel concentré", ["transparent"], ["plastique"], ["jerrycan"]),
                ("mercure_industriel", "industrielle", "Mercure industriel contaminé", ["argenté"], ["métal"], ["flacon"]),
                ("cyanure_industriel", "industrielle", "Résidu cyanure industriel", ["blanc"], ["plastique"], ["sac"]),
                ("pcb_transformateur", "industrielle", "PCB transformateur électrique", ["noir"], ["métal"], ["cuve"]),
                ("chrome_hexavalent", "industrielle", "Chrome hexavalent galvanoplastie", ["jaune"], ["plastique"], ["cuve"]),
                ("formaldehyde_industriel", "industrielle", "Formaldéhyde industriel", ["transparent"], ["verre"], ["flacon"]),
                ("pesticide_industriel", "industrielle", "Pesticide industriel concentré", ["coloré"], ["métal"], ["bidon"]),
                ("plomb_batterie_industriel", "industrielle", "Batterie industrielle plomb", ["gris"], ["plomb"], ["rectangulaire"]),
                ("dechet_pharmaceutique", "industrielle", "Déchet pharmaceutique industriel", ["variable"], ["verre"], ["flacon"])
            ]
        }
        
        # Aplatir la configuration en une seule liste
        waste_items = []
        for category, items_list in waste_types.items():
            for name, zone, description, colors, materials, forms in items_list:
                waste_items.append(CompetitionWasteItem(
                    name=name,
                    category=category, 
                    zone=zone,
                    description=description,
                    colors=colors,
                    materials=materials,
                    typical_forms=forms
                ))
        
        logger.info(f"Loaded configuration: {self._count_items_by_category(waste_items)}")
        return waste_items
    
    def _count_items_by_category(self, items: List[CompetitionWasteItem]) -> Dict[str, int]:
        """Compte les items par catégorie"""
        counts = {"menagers": 0, "recyclables": 0, "dangereux": 0}
        for item in items:
            if item.category in counts:
                counts[item.category] += 1
        return counts
    
    def _count_by_category(self) -> Dict[str, int]:
        """Compte les éléments par catégorie"""
        return self._count_items_by_category(self.waste_items)
    
    def generate_all_images(self) -> Dict[str, List[Tuple[CompetitionWasteItem, bytes]]]:
        """Génère toutes les images avec gestion de cache"""
        logger.info("Starting image generation...")
        
        # Organiser par catégorie
        images_by_category = {"menagers": [], "recyclables": [], "dangereux": []}
        
        # Charger le cache
        cached_items = self._load_cache()
        
        # Séparer les éléments cachés et à générer
        items_to_generate = []
        for item in self.waste_items:
            cache_key = f"{item.category}_{item.zone}_{item.name}"
            if cache_key in cached_items:
                logger.info(f"Using cached: {item.name}")
                images_by_category[item.category].append((item, cached_items[cache_key]))
            else:
                items_to_generate.append(item)
        
        if not items_to_generate:
            logger.info("All images cached!")
            return images_by_category
        
        logger.info(f"Generating {len(items_to_generate)} new images...")
        
        # Générer en parallèle limité
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {
                executor.submit(self.freepik_generator.generate_image, item): item
                for item in items_to_generate
            }
            
            with tqdm(total=len(future_to_item), desc="Generating") as pbar:
                for future in as_completed(future_to_item):
                    item = future_to_item[future]
                    try:
                        image_data = future.result()
                        if image_data:
                            images_by_category[item.category].append((item, image_data))
                            self._save_to_cache(item, image_data)
                            logger.info(f"✓ {item.name}")
                        else:
                            logger.error(f"✗ {item.name}")
                    except Exception as e:
                        logger.error(f"Exception {item.name}: {e}")
                    
                    pbar.update(1)
        
        return images_by_category
    
    def generate_pdfs(self, images_by_category: Dict[str, List[Tuple[CompetitionWasteItem, bytes]]]) -> List[str]:
        """Génère les PDFs pour chaque catégorie"""
        logger.info("Generating PDFs...")
        
        pdf_paths = []
        for category, waste_images in images_by_category.items():
            if waste_images:
                logger.info(f"Creating PDF: {category} ({len(waste_images)} items)")
                pdf_path = self.pdf_generator.create_category_pdf(category, waste_images)
                if pdf_path:
                    pdf_paths.append(pdf_path)
            else:
                logger.warning(f"No images for category: {category}")
        
        return pdf_paths
    
    def _load_cache(self) -> Dict[str, bytes]:
        """Charge le cache des images"""
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
        """Sauvegarde en cache"""
        try:
            cache_dir = self.output_dir / "cache"
            cache_file = cache_dir / "image_cache.json"
            
            # Charger cache existant
            cache_data = {}
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
            
            # Ajouter nouvelle image
            cache_key = f"{item.category}_{item.zone}_{item.name}"
            cache_data[cache_key] = base64.b64encode(image_data).decode('utf-8')
            
            # Sauvegarder
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
            
            # Image individuelle
            image_file = cache_dir / f"{cache_key}.jpg"
            with open(image_file, 'wb') as f:
                f.write(image_data)
                
        except Exception as e:
            logger.warning(f"Failed to save cache for {item.name}: {e}")
    
    def run_full_generation(self) -> Dict[str, any]:
        """Lance la génération complète"""
        start_time = time.time()
        
        logger.info("="*60)
        logger.info("COMPETITION WASTE DATASET GENERATOR - VERSION CORRIGÉE")
        logger.info("="*60)
        logger.info(f"Configuration: {self._count_by_category()}")
        logger.info(f"Total items: {len(self.waste_items)}")
        
        try:
            # Générer images avec utilisation simultanée des clés
            images_by_category = self.generate_all_images()
            
            # Créer PDFs
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
                },
                "api_key_stats": self.freepik_generator.get_statistics()
            }
            
            logger.info("="*60)
            logger.info("GENERATION TERMINÉE AVEC UTILISATION SIMULTANÉE DES CLÉS!")
            logger.info(f"✓ Images: {total_generated}/{len(self.waste_items)}")
            logger.info(f"✓ PDFs: {len(pdf_paths)}")  
            logger.info(f"✓ Répartition: {result['images_by_category']}")
            logger.info(f"✓ Temps: {elapsed_time:.1f}s")
            logger.info(f"✓ Clés API utilisées: {len(self.freepik_generator.api_keys)}")
            logger.info("="*60)
            
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
        # Vérifier les clés API
        has_api_key = bool(os.getenv("FREEPIK_API_KEY"))
        for i in range(1, 10):
            if os.getenv(f"FREEPIK_API_KEY_{i}"):
                has_api_key = True
                break
        
        if not has_api_key:
            logger.error("Aucune clé API Freepik trouvée!")
            logger.error("Définissez FREEPIK_API_KEY ou FREEPIK_API_KEY_1 dans votre .env")
            return
        
        # Lancer la génération
        generator = CompetitionDatasetGenerator("competition_waste_dataset")
        result = generator.run_full_generation()
        
        if result["success"]:
            print("\n" + "="*60)
            print("🎉 GENERATION RÉUSSIE!")
            print(f"📊 Images: {result['generated_images']}/{result['total_items']}")
            print(f"📄 PDFs: {result['generated_pdfs']}")
            print(f"📈 Répartition: {result['images_by_category']}")
            print(f"⏱️  Temps: {result['elapsed_time']:.1f}s")
            print(f"📁 Dossier: competition_waste_dataset/")
            print("\n📋 Étapes suivantes:")
            print("1. Vérifier les PDFs dans competition_waste_dataset/pdfs/")
            print("2. Imprimer sur papier A4")
            print("3. Découper les carrés 3x3 cm")  
            print("4. Coller sur vos cubes de compétition")
            print("="*60)
        else:
            print(f"\n❌ Échec: {result.get('error', 'Erreur inconnue')}")
            
    except KeyboardInterrupt:
        print("\n⏹️  Génération interrompue")
    except Exception as e:
        logger.error(f"Erreur principale: {e}")
        print(f"\n❌ Erreur: {e}")

if __name__ == "__main__":
    main()