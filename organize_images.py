#!/usr/bin/env python3
"""
Organisateur d'images de déchets par catégories et zones
=======================================================

Ce script organise automatiquement les images générées dans une structure
de dossiers organisée par catégories et zones.

Structure finale :
images/
├── menagers/
│   ├── residentielle/
│   ├── commerciale/
│   └── industrielle/
├── dangereux/
│   ├── residentielle/
│   ├── commerciale/
│   └── industrielle/
└── recyclables/
    ├── residentielle/
    ├── commerciale/
    └── industrielle/

Auteur: Assistant IA
Date: Septembre 2025
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Tuple
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ImageOrganizer:
    """Organisateur d'images par catégories et zones"""

    def __init__(self, images_dir: str):
        self.images_dir = Path(images_dir)
        self.stats = {
            'total_files': 0,
            'organized_files': 0,
            'categories': {},
            'errors': []
        }

        # Vérifier que le dossier existe
        if not self.images_dir.exists():
            raise FileNotFoundError(f"Dossier images non trouvé: {self.images_dir}")

        logger.info(f"Initialisation de l'organisateur pour: {self.images_dir}")

    def parse_filename(self, filename: str) -> Tuple[str, str, str]:
        """
        Parse le nom de fichier pour extraire catégorie, zone et nom du déchet

        Format attendu: {category}_{zone}_{waste_name}.jpg
        Exemple: dangereux_commerciale_batterie_ordinateur.jpg
        """
        if not filename.endswith('.jpg'):
            raise ValueError(f"Format non supporté: {filename}")

        # Retirer l'extension
        name_without_ext = filename[:-4]

        # Séparer par underscores
        parts = name_without_ext.split('_')

        if len(parts) < 3:
            raise ValueError(f"Nom de fichier invalide: {filename}")

        # Les deux premiers éléments sont catégorie et zone
        category = parts[0]
        zone = parts[1]

        # Le reste est le nom du déchet
        waste_name = '_'.join(parts[2:])

        return category, zone, waste_name

    def create_directory_structure(self):
        """Crée la structure de dossiers organisée"""
        categories = ['menagers', 'dangereux', 'recyclables']
        zones = ['residentielle', 'commerciale', 'industrielle']

        for category in categories:
            for zone in zones:
                dir_path = self.images_dir / category / zone
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Dossier créé: {dir_path}")

    def organize_images(self) -> Dict[str, any]:
        """Organise toutes les images dans la structure de dossiers"""
        logger.info("Début de l'organisation des images...")

        # Créer la structure de dossiers
        self.create_directory_structure()

        # Lister tous les fichiers .jpg
        image_files = list(self.images_dir.glob('*.jpg'))
        self.stats['total_files'] = len(image_files)

        logger.info(f"Trouvé {len(image_files)} fichiers image à organiser")

        # Organiser chaque fichier
        for image_file in image_files:
            try:
                # Parser le nom de fichier
                category, zone, waste_name = self.parse_filename(image_file.name)

                # Créer le chemin de destination
                dest_dir = self.images_dir / category / zone
                dest_file = dest_dir / image_file.name

                # Déplacer le fichier
                shutil.move(str(image_file), str(dest_file))

                # Mettre à jour les statistiques
                if category not in self.stats['categories']:
                    self.stats['categories'][category] = {}
                if zone not in self.stats['categories'][category]:
                    self.stats['categories'][category][zone] = 0
                self.stats['categories'][category][zone] += 1

                self.stats['organized_files'] += 1

                logger.debug(f"Organisé: {image_file.name} -> {category}/{zone}/")

            except Exception as e:
                error_msg = f"Erreur avec {image_file.name}: {e}"
                logger.error(error_msg)
                self.stats['errors'].append(error_msg)

        return self.stats

    def print_summary(self):
        """Affiche un résumé de l'organisation"""
        print("\n" + "="*60)
        print("📁 ORGANISATION DES IMAGES TERMINÉE")
        print("="*60)

        print(f"📊 Statistiques:")
        print(f"   • Total de fichiers: {self.stats['total_files']}")
        print(f"   • Fichiers organisés: {self.stats['organized_files']}")
        print(f"   • Erreurs: {len(self.stats['errors'])}")

        print(f"\n📂 Structure créée:")
        for category, zones in self.stats['categories'].items():
            print(f"   📁 {category}/")
            for zone, count in zones.items():
                print(f"      📁 {zone}/ ({count} fichiers)")

        if self.stats['errors']:
            print(f"\n❌ Erreurs rencontrées:")
            for error in self.stats['errors'][:5]:  # Afficher max 5 erreurs
                print(f"   • {error}")
            if len(self.stats['errors']) > 5:
                print(f"   • ... et {len(self.stats['errors']) - 5} autres erreurs")

        print(f"\n✅ Organisation terminée avec succès!")
        print(f"📍 Dossier organisé: {self.images_dir}")

    def verify_organization(self) -> bool:
        """Vérifie que l'organisation s'est bien déroulée"""
        logger.info("Vérification de l'organisation...")

        # Vérifier qu'il n'y a plus de fichiers .jpg à la racine
        root_files = list(self.images_dir.glob('*.jpg'))
        if root_files:
            logger.warning(f"⚠️ {len(root_files)} fichiers toujours à la racine")
            return False

        # Compter les fichiers dans les sous-dossiers
        total_organized = 0
        for category_dir in self.images_dir.iterdir():
            if category_dir.is_dir():
                for zone_dir in category_dir.iterdir():
                    if zone_dir.is_dir():
                        files_in_zone = list(zone_dir.glob('*.jpg'))
                        total_organized += len(files_in_zone)

        if total_organized != self.stats['organized_files']:
            logger.error(f"⚠️ Incohérence: {total_organized} fichiers trouvés vs {self.stats['organized_files']} organisés")
            return False

        logger.info(f"✅ Vérification réussie: {total_organized} fichiers correctement organisés")
        return True


def main():
    """Fonction principale"""
    try:
        # Configuration du dossier images
        images_dir = "/home/yoann/Workspace/AI/TRC_AI/competition_waste_dataset/images"

        print("🗂️ ORGANISATEUR D'IMAGES DE DÉCHETS")
        print("="*50)
        print(f"Dossier à organiser: {images_dir}")

        # Créer l'organisateur
        organizer = ImageOrganizer(images_dir)

        # Organiser les images
        stats = organizer.organize_images()

        # Vérifier l'organisation
        if organizer.verify_organization():
            organizer.print_summary()
        else:
            print("❌ Problème détecté dans l'organisation")
            return 1

        return 0

    except Exception as e:
        logger.error(f"Erreur lors de l'organisation: {e}")
        print(f"❌ Erreur: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
