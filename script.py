import os
import json
import requests
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from dataclasses import dataclass, asdict
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from dotenv import load_dotenv
load_dotenv()

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class WasteConfig:
    """Configuration pour un type de déchet"""
    name: str
    category: str
    zone: str
    colors: List[str]
    materials: List[str]
    shapes: List[str]
    sizes: List[str]
    degradation_states: List[str]

@dataclass
class ZoneConfig:
    """Configuration pour une zone"""
    name: str
    type: str
    environments: List[str]
    lighting_conditions: List[str]
    backgrounds: List[str]
    obstacles: List[str]

@dataclass
class GenerationConfig:
    """Configuration pour la génération d'images"""
    model: str = "google/gemini-2.0-flash-exp:free"
    quality: str = "auto"
    output_format: str = "png"
    resolution: str = "1024x1024"
    batch_size: int = 10
    max_workers: int = 5

class WasteDatasetGenerator:
    """Générateur principal de dataset d'images de déchets"""
    
    def __init__(self, config: GenerationConfig, output_dir: str = "waste_dataset"):
        self.config = config
        self.output_dir = Path(output_dir)
        self.api_key = os.getenv("IMAGE_ROUTER_API_KEY")
        self.api_url = "https://ir-api.myqa.cc/v1/openai/images/generations"
        
        if not self.api_key:
            raise ValueError("IMAGE_ROUTER_API_KEY environment variable not set")
        
        self._setup_directories()
        self._load_configurations()
    
    def _setup_directories(self):
        """Créer la structure de répertoires"""
        directories = [
            self.output_dir,
            self.output_dir / "images",
            self.output_dir / "metadata",
            self.output_dir / "logs"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _load_configurations(self):
        """Charger les configurations des zones et déchets"""
        self.zones = {
            "residential": ZoneConfig(
                name="Quartier résidentiel",
                type="residential",
                environments=["Yamcity", "Cotonou", "Lagos", "Accra", "Bamako", "Lomé"],
                lighting_conditions=["naturelle", "crépuscule", "artificielle"],
                backgrounds=["rue pavée", "devant maison", "jardin", "balcon"],
                obstacles=["piétons", "véhicules garés", "mobilier urbain"]
            ),
            "commercial": ZoneConfig(
                name="Centre commercial",
                type="commercial", 
                environments=["WalMart", "Super U", "China Mall"],
                lighting_conditions=["éclairage LED", "naturelle par verrière", "spots"],
                backgrounds=["parking", "entrée magasin", "zone de stockage", "aire de repos"],
                obstacles=["caddies", "panneaux publicitaires", "jardinières"]
            ),
            "industrial": ZoneConfig(
                name="Zone industrielle",
                type="industrial",
                environments=["GDIZ", "Lagos Industrial Park", "Ouagadougou Tech Zone", 
                           "Bobo-Dioulasso Industrial Estate", "Port Harcourt Energy Zone"],
                lighting_conditions=["projecteurs industriels", "néons", "naturelle harsh"],
                backgrounds=["entrepôt", "zone de stockage", "aire de chargement", "bureau"],
                obstacles=["équipements industriels", "conteneurs", "véhicules lourds"]
            )
        }
        
        self.waste_types = {
            "residential": [
                WasteConfig("bouteille_plastique", "ménager", "residential",
                          ["transparent", "bleu", "vert", "rouge"],
                          ["PET", "HDPE"], ["cylindrique", "carrée"],
                          ["petit", "moyen", "grand"], ["neuf", "usagé", "écrasé"]),
                WasteConfig("sac_plastique", "ménager", "residential",
                          ["blanc", "noir", "coloré"], ["polyéthylène"],
                          ["sac", "froissé"], ["petit", "moyen"], ["neuf", "usagé", "déchiré"]),
                WasteConfig("canette_aluminium", "ménager", "residential",
                          ["argenté", "rouge", "bleu"], ["aluminium"],
                          ["cylindrique"], ["330ml", "500ml"], ["neuf", "cabossé", "écrasé"]),
                WasteConfig("carton", "ménager", "residential",
                          ["brun", "blanc"], ["carton ondulé", "carton simple"],
                          ["boîte", "plat"], ["petit", "moyen", "grand"], ["neuf", "humide", "déchiré"])
            ],
            "commercial": [
                WasteConfig("carton_emballage", "recyclable", "commercial",
                          ["brun", "blanc", "imprimé"], ["carton ondulé"],
                          ["boîte", "plat", "tube"], ["petit", "moyen", "grand", "très grand"],
                          ["neuf", "plié", "déchiré"]),
                WasteConfig("bouteille_verre", "recyclable", "commercial",
                          ["transparent", "vert", "brun"], ["verre"],
                          ["cylindrique", "carrée"], ["petit", "moyen", "grand"],
                          ["neuf", "usagé", "cassé"]),
                WasteConfig("metal_leger", "recyclable", "commercial",
                          ["argenté", "doré", "coloré"], ["aluminium", "acier"],
                          ["cylindrique", "plat", "irrégulier"], ["petit", "moyen"],
                          ["neuf", "rouillé", "cabossé"])
            ],
            "industrial": [
                WasteConfig("batterie", "dangereux", "industrial",
                          ["noir", "bleu", "rouge"], ["lithium", "plomb", "alcaline"],
                          ["cylindrique", "rectangulaire"], ["petit", "moyen", "grand"],
                          ["neuf", "gonflé", "corrodé"]),
                WasteConfig("produit_chimique", "dangereux", "industrial",
                          ["transparent", "coloré"], ["plastique", "verre", "métal"],
                          ["bouteille", "bidon", "fût"], ["petit", "moyen", "grand"],
                          ["intact", "fissuré", "corrodé"]),
                WasteConfig("composant_electronique", "dangereux", "industrial",
                          ["vert", "noir", "multicolore"], ["PCB", "plastique", "métal"],
                          ["rectangulaire", "carré", "irrégulier"], ["petit", "moyen"],
                          ["fonctionnel", "cassé", "brûlé"])
            ]
        }
    
    def generate_prompt(self, waste: WasteConfig, zone: ZoneConfig, 
                       variations: Dict[str, str]) -> str:
        """Générer un prompt détaillé pour l'image"""
        base_prompt = f"""
        Photographie réaliste d'un déchet en grand centre sur l'image.
        
        DÉCHET:
        - Type: {waste.name}
        - Catégorie: {waste.category}
        - Couleur: {variations['color']}
        - Matériau: {variations['material']}
        - Forme: {variations['shape']}
        - Taille: {variations['size']}
        - État: {variations['degradation']}
        
        ENVIRONNEMENT:
        - Zone: {zone.name}
        - Lieu: {variations['environment']}
        - Éclairage: {variations['lighting']}
        - Arrière-plan: {variations['background']}
        - Obstacle proche: {variations.get('obstacle', 'aucun')}
        
        STYLE:
        - Photo haute résolution, très réaliste
        - Éclairage naturel et contrasté
        - Netteté parfaite sur le déchet et le cube
        - Profondeur de champ naturelle
        - Couleurs vives et saturées
        - Style documentaire/scientifique
        """
        
        return base_prompt.strip()
    
    def generate_image_sync(self, prompt: str) -> Optional[str]:
        """Générer une image de façon synchrone"""
        try:
            payload = {
                "prompt": prompt,
                "model": self.config.model,
                "quality": self.config.quality
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(self.api_url, json=payload, headers=headers)
            response.raise_for_status()
            
            image_b64 = response.json()["data"][0]['b64_json']
            return image_b64
            
        except Exception as e:
            logger.error(f"Erreur génération image: {e}")
            return None
    
    def save_image(self, image_b64: str, metadata: Dict, filename: str) -> bool:
        """Sauvegarder l'image et ses métadonnées"""
        try:
            # Sauvegarder l'image
            image_path = self.output_dir / "images" / f"{filename}.{self.config.output_format}"
            image_data = base64.b64decode(image_b64)
            
            with open(image_path, 'wb') as f:
                f.write(image_data)
            
            # Sauvegarder les métadonnées
            metadata_path = self.output_dir / "metadata" / f"{filename}.json"
            metadata['image_path'] = str(image_path)
            metadata['generated_at'] = datetime.now().isoformat()
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde {filename}: {e}")
            return False
    
    def generate_variations(self, waste: WasteConfig, zone: ZoneConfig) -> List[Dict[str, str]]:
        """Générer toutes les variations possibles pour un déchet dans une zone"""
        variations = []
        
        for color in waste.colors:
            for material in waste.materials:
                for shape in waste.shapes:
                    for size in waste.sizes:
                        for degradation in waste.degradation_states:
                            for environment in zone.environments:
                                for lighting in zone.lighting_conditions:
                                    for background in zone.backgrounds:
                                        variations.append({
                                            'color': color,
                                            'material': material,
                                            'shape': shape,
                                            'size': size,
                                            'degradation': degradation,
                                            'environment': environment,
                                            'lighting': lighting,
                                            'background': background
                                        })
        
        return variations
    
    def generate_dataset(self, num_images_per_type: int = 50, 
                        zones_filter: Optional[List[str]] = None) -> Dict[str, int]:
        """Générer le dataset complet"""
        stats = {"total": 0, "success": 0, "failed": 0}
        
        zones_to_process = zones_filter or list(self.zones.keys())
        
        for zone_key in zones_to_process:
            zone = self.zones[zone_key]
            waste_types = self.waste_types[zone_key]
            
            logger.info(f"Génération pour zone: {zone.name}")
            
            for waste in waste_types:
                logger.info(f"  Génération pour déchet: {waste.name}")
                
                # Générer les variations
                variations = self.generate_variations(waste, zone)
                
                # Limiter le nombre d'images
                selected_variations = variations[:num_images_per_type]
                
                # Génération par batch
                for i in range(0, len(selected_variations), self.config.batch_size):
                    batch = selected_variations[i:i + self.config.batch_size]
                    
                    with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                        futures = []
                        
                        for j, variation in enumerate(batch):
                            prompt = self.generate_prompt(waste, zone, variation)
                            filename = f"{zone_key}_{waste.name}_{i+j:04d}"
                            
                            metadata = {
                                'waste_type': waste.name,
                                'zone': zone_key,
                                'category': waste.category,
                                'variations': variation,
                                'prompt': prompt
                            }
                            
                            future = executor.submit(self._process_single_image, 
                                                   prompt, metadata, filename)
                            futures.append(future)
                        
                        # Attendre les résultats
                        for future in as_completed(futures):
                            success = future.result()
                            stats["total"] += 1
                            if success:
                                stats["success"] += 1
                            else:
                                stats["failed"] += 1
                    
                    # Pause entre les batches
                    time.sleep(1)
        
        # Sauvegarder les statistiques
        self._save_generation_stats(stats)
        return stats
    
    def _process_single_image(self, prompt: str, metadata: Dict, filename: str) -> bool:
        """Traiter une seule image"""
        try:
            image_b64 = self.generate_image_sync(prompt)
            if image_b64:
                return self.save_image(image_b64, metadata, filename)
            return False
        except Exception as e:
            logger.error(f"Erreur traitement {filename}: {e}")
            return False
    
    def _save_generation_stats(self, stats: Dict[str, int]):
        """Sauvegarder les statistiques de génération"""
        stats_path = self.output_dir / "generation_stats.json"
        stats['timestamp'] = datetime.now().isoformat()
        
        with open(stats_path, 'w') as f:
            json.dump(stats, f, indent=2)
    
    def export_annotations(self, format_type: str = "coco") -> str:
        """Exporter les annotations dans différents formats"""
        if format_type == "coco":
            return self._export_coco_format()
        elif format_type == "yolo":
            return self._export_yolo_format()
        else:
            raise ValueError(f"Format non supporté: {format_type}")
    
    def _export_coco_format(self) -> str:
        """Exporter au format COCO"""
        # Implementation pour format COCO
        pass
    
    def _export_yolo_format(self) -> str:
        """Exporter au format YOLO"""
        # Implementation pour format YOLO
        pass

# Exemple d'utilisation
if __name__ == "__main__":
    # Configuration
    config = GenerationConfig(
        batch_size=5,
        max_workers=3,
        resolution="1024x1024"
    )
    
    # Créer le générateur
    generator = WasteDatasetGenerator(config, "waste_dataset")
    
    # Générer le dataset
    print("Début de la génération du dataset...")
    stats = generator.generate_dataset(
        num_images_per_type=20,  # 20 images par type de déchet
        zones_filter=["residential", "commercial", "industrial"]  # Optionnel: filtrer les zones
    )
    
    print(f"Génération terminée:")
    print(f"  Total: {stats['total']}")
    print(f"  Succès: {stats['success']}")
    print(f"  Échecs: {stats['failed']}")
    
    # Exporter les annotations
    # generator.export_annotations("coco")