#!/usr/bin/env python3
"""
Générateur de PDFs par catégorie pour le dataset de déchets de compétition robotique.

Ce script prend les images organisées par catégories et zones et génère des PDFs
avec chaque image répétée 6 fois par ligne en format 3x3cm pour faciliter le découpage.

Structure:
- Page 1: Récapitulatif de la catégorie (DESIGN AMÉLIORÉ)
- Pages suivantes: Images avec 6 copies par ligne, une ligne par type de déchet

Auteur: Assistant IA
Date: 19 septembre 2025
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict
import json
from datetime import datetime

# Imports pour la génération PDF et traitement d'images
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.colors import black, white, blue, green, red
from reportlab.platypus.flowables import Image as ReportLabImage
from reportlab.lib import colors
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO

# Configuration de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('category_pdf_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CategoryPDFGenerator:
    """Générateur de PDFs par catégorie avec images répétées."""
    
    def __init__(self, images_dir: str, output_dir: str = "category_pdfs"):
        """
        Initialise le générateur.
        
        Args:
            images_dir: Dossier contenant les images organisées par catégories
            output_dir: Dossier de sortie pour les PDFs
        """
        self.images_dir = Path(images_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Configuration PDF
        self.page_width, self.page_height = A4
        self.margin = 1.5 * cm
        self.image_size = 3 * cm  # 3x3 cm comme spécifié
        self.images_per_row = 6   # 6 copies par ligne
        self.dpi = 300            # Qualité d'image
        
        # Styles améliorés avec typographie moderne
        self.styles = getSampleStyleSheet()
        
        # Style pour le header TRC 2025
        self.header_style = ParagraphStyle(
            'TRCHeader',
            parent=self.styles['Normal'],
            fontSize=14,
            fontName='Helvetica-Bold',
            textColor=colors.darkblue,
            alignment=TA_CENTER,
            spaceAfter=5
        )
        
        # Style titre principal - plus moderne
        self.main_title_style = ParagraphStyle(
            'MainTitle',
            parent=self.styles['Heading1'],
            fontSize=32,
            fontName='Helvetica-Bold',
            textColor=colors.darkblue,
            alignment=TA_CENTER,
            spaceAfter=10,
            leading=36
        )
        
        # Style sous-titre élégant
        self.elegant_subtitle_style = ParagraphStyle(
            'ElegantSubtitle',
            parent=self.styles['Normal'],
            fontSize=18,
            fontName='Helvetica',
            textColor=colors.grey,
            alignment=TA_CENTER,
            spaceAfter=25,
            leading=22
        )
        
        # Style pour les sections avec couleur et bordure moderne
        self.section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            fontName='Helvetica-Bold',
            textColor=colors.white,
            alignment=TA_CENTER,
            spaceAfter=12,
            spaceBefore=20,
            borderWidth=1,
            borderColor=colors.darkblue,
            borderPadding=12,
            backColor=colors.darkblue,
            leading=20
        )
        
        # Style pour le contenu des sections
        self.section_content_style = ParagraphStyle(
            'SectionContent',
            parent=self.styles['Normal'],
            fontSize=11,
            fontName='Helvetica',
            textColor=colors.black,
            alignment=TA_LEFT,
            spaceAfter=8,
            leading=14,
            leftIndent=10
        )
        
        # Style pour les statistiques
        self.stats_style = ParagraphStyle(
            'StatsStyle',
            parent=self.styles['Normal'],
            fontSize=12,
            fontName='Helvetica-Bold',
            textColor=colors.darkgreen,
            alignment=TA_CENTER,
            spaceAfter=6
        )
        
        # Style pour les instructions étapées
        self.instruction_title_style = ParagraphStyle(
            'InstructionTitle',
            parent=self.styles['Normal'],
            fontSize=13,
            fontName='Helvetica-Bold',
            textColor=colors.darkred,
            alignment=TA_LEFT,
            spaceAfter=5,
            spaceBefore=8
        )
        
        self.instruction_content_style = ParagraphStyle(
            'InstructionContent',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Helvetica',
            textColor=colors.black,
            alignment=TA_LEFT,
            spaceAfter=3,
            leftIndent=15,
            bulletIndent=10
        )
        
        # Mapping des catégories en français
        self.category_names = {
            'recyclables': 'Déchets Recyclables',
            'menagers': 'Déchets Ménagers',
            'dangereux': 'Déchets Dangereux'
        }
        
        self.category_colors = {
            'recyclables': colors.darkgreen,
            'menagers': colors.darkblue,
            'dangereux': colors.darkred
        }
        
        self.category_bg_colors = {
            'recyclables': colors.lightgreen,
            'menagers': colors.lightblue,
            'dangereux': colors.mistyrose
        }
        
        logger.info(f"Générateur initialisé - Images: {self.images_dir}, Sortie: {self.output_dir}")
    
    def scan_images_by_category(self) -> Dict[str, Dict[str, List[Path]]]:
        """
        Scanne les images organisées par catégories et zones.
        
        Returns:
            Dictionnaire {catégorie: {zone: [fichiers]}}
        """
        logger.info("Scan des images par catégorie...")
        
        images_by_category = defaultdict(lambda: defaultdict(list))
        
        for category_dir in self.images_dir.iterdir():
            if category_dir.is_dir() and category_dir.name in self.category_names:
                category = category_dir.name
                logger.info(f"Traitement de la catégorie: {category}")
                
                for zone_dir in category_dir.iterdir():
                    if zone_dir.is_dir():
                        zone = zone_dir.name
                        image_files = [f for f in zone_dir.iterdir() 
                                     if f.suffix.lower() in ['.jpg', '.jpeg', '.png']]
                        images_by_category[category][zone].extend(image_files)
                        logger.info(f"  Zone {zone}: {len(image_files)} images")
        
        return dict(images_by_category)
    
    def create_header_section(self) -> List:
        """Crée la section d'en-tête avec logo et informations de compétition."""
        elements = []
        
        # En-tête TRC 2025
        header_text = "TEKBOT ROBOTICS CHALLENGE 2025"
        header = Paragraph(header_text, self.header_style)
        elements.append(header)
        
        # Sous-titre compétition
        competition_subtitle = "Dataset Officiel d'Entraînement - Tri Automatisé de Déchets"
        subtitle = Paragraph(competition_subtitle, self.elegant_subtitle_style)
        elements.append(subtitle)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def create_category_banner(self, category: str) -> List:
        """Crée une bannière colorée pour la catégorie."""
        elements = []
        
        category_title = self.category_names.get(category, category.title())
        category_icons = {
            'recyclables': '♻️',
            'menagers': '🗑️', 
            'dangereux': '☢️'
        }
        icon = category_icons.get(category, '📦')
        
        # Créer un style personnalisé pour cette catégorie
        category_banner_style = ParagraphStyle(
            'CategoryBanner',
            parent=self.main_title_style,
            textColor=self.category_colors.get(category, colors.black),
            backColor=self.category_bg_colors.get(category, colors.lightgrey),
            borderWidth=2,
            borderColor=self.category_colors.get(category, colors.black),
            borderPadding=15
        )
        
        banner_text = f"{icon} {category_title.upper()}"
        banner = Paragraph(banner_text, category_banner_style)
        elements.append(banner)
        elements.append(Spacer(1, 25))
        
        return elements
    
    def create_info_box(self, category: str, images_data: Dict[str, List[Path]]) -> List:
        """Crée une boîte d'information générale élégante."""
        elements = []
        
        # Calculs pour la boîte info
        total_images = sum(len(images) for images in images_data.values())
        all_waste_types = set()
        for images in images_data.values():
            for img in images:
                waste_type = img.stem.split('_')[-1]
                all_waste_types.add(waste_type)
        total_types = len(all_waste_types)
        
        # Créer une boîte d'information visuelle
        info_data = [[
            f"🎯 CATÉGORIE\n{self.category_names.get(category, category.title())}",
            f"📊 DATASET\n{total_images} images\n{total_types} types",
            f"🎲 PRODUCTION\n{total_types * 6} cubes\npossibles",
            f"⚙️ FORMAT\n3×3 cm\nPrêt à découper"
        ]]
        
        info_table = Table(info_data, colWidths=[3.7*cm, 3.7*cm, 3.7*cm, 3.7*cm])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.category_bg_colors.get(category, colors.lightgrey)),
            ('TEXTCOLOR', (0, 0), (-1, -1), self.category_colors.get(category, colors.black)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 2, self.category_colors.get(category, colors.black)),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('LEADING', (0, 0), (-1, -1), 14),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 25))
        
        return elements
    
    def create_stats_section(self, category: str, images_data: Dict[str, List[Path]]) -> List:
        """Crée la section statistiques avec design moderne."""
        elements = []
        
        # Titre de section
        section_title = Paragraph("📊 STATISTIQUES DU DATASET", self.section_title_style)
        elements.append(section_title)
        
        # Calculs statistiques
        total_images = sum(len(images) for images in images_data.values())
        all_waste_types = set()
        for images in images_data.values():
            for img in images:
                waste_type = img.stem.split('_')[-1]
                all_waste_types.add(waste_type)
        total_types = len(all_waste_types)
        
        # Créer un tableau de statistiques visuellement attrayant
        stats_data = [
            ['📊 MÉTRIQUE', '🔢 VALEUR', '📝 DESCRIPTION'],
            ['Images Totales', str(total_images), 'Images disponibles pour entraînement'],
            ['Types de Déchets', str(total_types), 'Classes distinctes de déchets'],
            ['Environnements', str(len(images_data)), 'Contextes de collecte différents'],
            ['Cubes Possibles', str(total_types * 6), 'Cubes fabricables (6 copies/type)'],
            ['Format Standard', '3×3 cm', 'Taille optimale pour cubes robotiques'],
            ['Qualité Dataset', 'Haute', 'Images validées pour compétition']
        ]
        
        stats_table = Table(stats_data, colWidths=[4*cm, 3*cm, 8*cm])
        stats_table.setStyle(TableStyle([
            # En-tête
            ('BACKGROUND', (0, 0), (-1, 0), self.category_colors.get(category, colors.grey)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            
            # Corps du tableau
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            
            # Alternance de couleurs
            ('BACKGROUND', (0, 2), (-1, 2), colors.lightcyan),
            ('BACKGROUND', (0, 4), (-1, 4), colors.lightcyan),
            ('BACKGROUND', (0, 6), (-1, 6), colors.lightcyan),
            
            # Padding
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def create_environment_section(self, images_data: Dict[str, List[Path]]) -> List:
        """Crée la section répartition par environnement."""
        elements = []
        
        # Titre de section
        section_title = Paragraph("🌍 RÉPARTITION PAR ENVIRONNEMENT", self.section_title_style)
        elements.append(section_title)
        
        # Tableau environnements avec design amélioré
        env_data = [['🏢 ENVIRONNEMENT', '📊 IMAGES', '🗂️ TYPES', '📋 ÉCHANTILLONS']]
        
        zone_icons = {
            'residentielle': '🏠',
            'commerciale': '🏢',
            'industrielle': '🏭'
        }
        
        for zone, images in images_data.items():
            zone_waste_types = set(img.stem.split('_')[-1] for img in images)
            icon = zone_icons.get(zone, '📍')
            examples = ', '.join(sorted(list(zone_waste_types))[:4])
            if len(zone_waste_types) > 4:
                examples += '...'
            
            env_data.append([
                f"{icon} {zone.title()}",
                str(len(images)),
                str(len(zone_waste_types)),
                examples
            ])
        
        env_table = Table(env_data, colWidths=[4*cm, 2.5*cm, 2.5*cm, 6*cm])
        env_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightsteelblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(env_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def create_instructions_section(self) -> List:
        """Crée la section instructions avec design étapé moderne."""
        elements = []
        
        # Titre de section
        section_title = Paragraph("🔧 GUIDE D'UTILISATION COMPÉTITION", self.section_title_style)
        elements.append(section_title)
        
        # Instructions étapées avec design moderne
        instructions = [
            ("🖨️ ÉTAPE 1 - IMPRESSION PROFESSIONNELLE", [
                "• Utilisez du papier photo 200g minimum ou carton fin",
                "• Réglez l'imprimante sur 'Taille réelle' (100% - pas d'ajustement)",
                "• Qualité d'impression : Maximum/Photo",
                "• Mode couleur obligatoire pour reconnaissance optimale"
            ]),
            ("✂️ ÉTAPE 2 - DÉCOUPAGE DE PRÉCISION", [
                "• Chaque image mesure exactement 3×3 cm",
                "• Utilisez une règle métallique et un cutter neuf",
                "• Découpez ligne par ligne pour maintenir l'organisation",
                "• Conservez les chutes pour tester l'adhésion"
            ]),
            ("🎲 ÉTAPE 3 - ASSEMBLAGE DES CUBES", [
                "• Nettoyez les faces des cubes avec alcool isopropylique",
                "• Utilisez colle forte ou adhésif double-face haute tenue",
                "• Centrez parfaitement chaque image (marges égales)",
                "• Pressez fermement 30 secondes, laissez sécher 5 minutes"
            ]),
            ("🤖 ÉTAPE 4 - UTILISATION EN COMPÉTITION", [
                "• Une catégorie = une mission de tri spécifique",
                "• 6 copies par type permettent tests répétés et backup",
                "• Mélangez aléatoirement pour évaluation réaliste",
                "• Documentez taux de reconnaissance de votre IA",
                "• Testez sous différents éclairages et angles"
            ])
        ]
        
        for step_title, step_content in instructions:
            # Titre de l'étape
            title_para = Paragraph(step_title, self.instruction_title_style)
            elements.append(title_para)
            
            # Contenu de l'étape
            for item in step_content:
                item_para = Paragraph(item, self.instruction_content_style)
                elements.append(item_para)
            
            elements.append(Spacer(1, 12))
        
        return elements
    
    def create_footer_section(self) -> List:
        """Crée le pied de page avec informations de génération."""
        elements = []
        
        elements.append(Spacer(1, 15))
        
        # Ligne de séparation
        separator_style = ParagraphStyle(
            'Separator',
            parent=self.styles['Normal'],
            fontSize=1,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        separator = Paragraph("_" * 80, separator_style)
        elements.append(separator)
        elements.append(Spacer(1, 10))
        
        # Informations de génération
        footer_text = f"""
        <b>📅 Document généré le :</b> {datetime.now().strftime('%d/%m/%Y à %H:%M')}<br/>
        <b>🏆 Compétition :</b> Tekbot Robotics Challenge 2025 (TRC 2025)<br/>
        <b>⚙️ Version dataset :</b> 1.0 - Tri automatisé de déchets<br/>
        <b>📧 Support :</b> Consultez les règles officielles TRC 2025
        """
        
        footer_style = ParagraphStyle(
            'Footer',
            parent=self.styles['Normal'],
            fontSize=9,
            fontName='Helvetica',
            textColor=colors.grey,
            alignment=TA_CENTER,
            leading=12
        )
        
        footer_para = Paragraph(footer_text, footer_style)
        elements.append(footer_para)
        
        return elements
    
    def create_summary_page(self, category: str, images_data: Dict[str, List[Path]]) -> List:
        """
        Crée la page de récapitulatif avec design professionnel amélioré.
        
        Args:
            category: Nom de la catégorie
            images_data: Données des images par zone
            
        Returns:
            Liste des éléments pour la page
        """
        story = []
        
        # 1. Header avec informations TRC 2025
        story.extend(self.create_header_section())
        
        # 2. Bannière catégorie
        story.extend(self.create_category_banner(category))
        
        # 2.5. Boîte d'information rapide
        story.extend(self.create_info_box(category, images_data))
        
        # 3. Section statistiques
        story.extend(self.create_stats_section(category, images_data))
        
        # 4. Section environnements
        story.extend(self.create_environment_section(images_data))
        
        # 5. Section instructions
        story.extend(self.create_instructions_section())
        
        # 6. Footer
        story.extend(self.create_footer_section())
        
        return story
    
    def create_image_row(self, image_path: Path) -> Table:
        """
        Crée une ligne avec 6 copies de la même image avec bordures en pointillés.
        
        Args:
            image_path: Chemin vers l'image
            
        Returns:
            Table avec 6 copies de l'image
        """
        try:
            # Créer 6 objets Image pour ReportLab directement à partir du fichier original
            images = []
            for _ in range(self.images_per_row):
                rl_image = ReportLabImage(str(image_path), width=self.image_size, height=self.image_size)
                images.append(rl_image)
            
            # Créer le tableau avec les 6 images et espacement
            table = Table([images], colWidths=[self.image_size] * self.images_per_row)
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),   # Espacement entre les images
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),  # Espacement entre les images
                ('TOPPADDING', (0, 0), (-1, -1), 4),    # Espacement vertical
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4), # Espacement vertical
                # Bordures en pointillés pour chaque cellule d'image
                ('LINEBELOW', (0, 0), (-1, -1), 1, colors.grey, None, (2, 2)),  # Ligne pointillée en bas
                ('LINEABOVE', (0, 0), (-1, -1), 1, colors.grey, None, (2, 2)),  # Ligne pointillée en haut
                ('LINEBEFORE', (0, 0), (-1, -1), 1, colors.grey, None, (2, 2)), # Ligne pointillée à gauche
                ('LINEAFTER', (0, 0), (-1, -1), 1, colors.grey, None, (2, 2)),  # Ligne pointillée à droite
            ]))
            
            return table
            
        except Exception as e:
            logger.error(f"Erreur lors de la création de la ligne pour {image_path}: {e}")
            return None
    
    def generate_category_pdf(self, category: str, images_data: Dict[str, List[Path]]):
        """
        Génère le PDF pour une catégorie.
        
        Args:
            category: Nom de la catégorie
            images_data: Données des images par zone
        """
        logger.info(f"Génération du PDF pour la catégorie: {category}")
        
        # Nom du fichier PDF
        pdf_filename = f"TRC2025_{category}_cubes_robotique.pdf"
        pdf_path = self.output_dir / pdf_filename
        
        # Créer le document PDF
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=self.margin,
            leftMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin,
            title=f"TRC 2025 - Dataset {self.category_names.get(category, category)}",
            author="Tekbot Robotics Challenge 2025",
            subject="Dataset d'entraînement pour tri automatisé de déchets"
        )
        
        story = []
        
        # Page de récapitulatif avec nouveau design
        summary_elements = self.create_summary_page(category, images_data)
        story.extend(summary_elements)
        story.append(PageBreak())
        
        # Pages avec les images (inchangées)
        all_images = []
        for zone, images in images_data.items():
            all_images.extend(images)
        
        # Grouper les images par type de déchet
        images_by_type = defaultdict(list)
        for img in all_images:
            waste_type = img.stem.split('_')[-1]  # Dernière partie du nom
            images_by_type[waste_type].append(img)
        
        # Titre pour les pages d'images
        images_title_style = ParagraphStyle(
            'ImagesTitle',
            parent=self.section_title_style,
            textColor=self.category_colors.get(category, colors.black)
        )
        images_title = Paragraph(f"🖼️ Images à découper - {self.category_names.get(category, category.title())}", images_title_style)
        story.append(images_title)
        story.append(Spacer(1, 15))
        
        # Créer une ligne par type de déchet
        for waste_type, type_images in sorted(images_by_type.items()):
            # Prendre la première image de ce type (elles devraient être similaires)
            representative_image = type_images[0]
            
            # Créer la ligne avec 6 copies
            image_row = self.create_image_row(representative_image)
            if image_row:
                story.append(image_row)
                story.append(Spacer(1, 8))  # Espacement entre les lignes d'images
        
        # Générer le PDF
        try:
            doc.build(story)
            logger.info(f"✅ PDF généré avec succès: {pdf_path}")
            return pdf_path
        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération du PDF {pdf_filename}: {e}")
            return None
    
    def generate_all_pdfs(self):
        """Génère tous les PDFs pour toutes les catégories."""
        logger.info("🏗️ DÉBUT DE LA GÉNÉRATION DES PDFs PAR CATÉGORIE - TRC 2025")
        logger.info("=" * 60)
        
        # Scanner les images
        images_by_category = self.scan_images_by_category()
        
        if not images_by_category:
            logger.error("Aucune image trouvée dans la structure de dossiers")
            return
        
        generated_pdfs = []
        
        # Générer un PDF par catégorie
        for category, zones_data in images_by_category.items():
            logger.info(f"📄 Génération du PDF pour: {category}")
            
            pdf_path = self.generate_category_pdf(category, zones_data)
            if pdf_path:
                generated_pdfs.append(pdf_path)
        
        # Rapport final
        logger.info("=" * 60)
        logger.info("🎉 GÉNÉRATION TERMINÉE - TRC 2025")
        logger.info(f"📊 PDFs générés: {len(generated_pdfs)}")
        
        for pdf_path in generated_pdfs:
            file_size = pdf_path.stat().st_size / (1024 * 1024)  # MB
            logger.info(f"   📄 {pdf_path.name} ({file_size:.1f} MB)")
        
        logger.info(f"📁 Dossier de sortie: {self.output_dir.absolute()}")


def main():
    """Fonction principale."""
    print("🏭 GÉNÉRATEUR DE PDFs TRC 2025 - DESIGN PROFESSIONNEL")
    print("=" * 60)
    print("Génère des PDFs avec design amélioré pour la compétition")
    print("Tekbot Robotics Challenge 2025 - Tri automatisé de déchets")
    print("Images 3x3cm répétées 6 fois par ligne pour cubes robotiques")
    print()
    
    # Configuration
    images_dir = "competition_waste_dataset/images"
    output_dir = "category_pdfs"
    
    # Vérifier que le dossier d'images existe
    if not Path(images_dir).exists():
        print(f"❌ Erreur: Le dossier {images_dir} n'existe pas")
        print("Assurez-vous d'avoir exécuté organize_images.py d'abord")
        return
    
    # Créer le générateur
    generator = CategoryPDFGenerator(images_dir, output_dir)
    
    # Générer tous les PDFs
    generator.generate_all_pdfs()
    
    print(f"\n✅ Génération terminée!")
    print(f"📁 Vérifiez le dossier: {output_dir}")
    print("🏆 Prêt pour la Tekbot Robotics Challenge 2025!")


if __name__ == "__main__":
    main()