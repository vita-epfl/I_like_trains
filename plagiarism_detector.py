#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Détecteur de plagiat pour les fichiers d'agents.
Ce script analyse les fichiers Python dans le dossier @common/agents/agents_to_evaluate
et génère un rapport des similitudes entre chaque paire de fichiers.
"""

import os
import re
import sys
import difflib
import itertools
import ast
import tokenize
import io
import concurrent.futures
import time
from collections import Counter
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Set, Any

# Configuration
AGENTS_DIR = Path("common/agents/agents_to_evaluate")
STAFF_PREFIX = "staff_"  # Préfixe pour les fichiers de référence de l'équipe
SIMILARITY_THRESHOLD = 0.8  # Seuil à partir duquel la similarité est suspecte
MIN_CODE_LENGTH = 100  # Longueur minimale de code pour éviter les faux positifs sur les petits fichiers
MAX_WORKERS = 4  # Nombre de workers pour le traitement parallèle
VERBOSE = False  # Afficher les détails pendant l'analyse

class CodeNormalizer:
    """Classe pour normaliser le code Python afin d'améliorer la détection de similitude."""
    
    @staticmethod
    def remove_comments_and_docstrings(source_code: str) -> str:
        """Supprime les commentaires et les docstrings du code source."""
        io_obj = io.StringIO(source_code)
        out = ""
        prev_toktype = tokenize.INDENT
        last_lineno = -1
        last_col = 0
        
        try:
            for tok in tokenize.generate_tokens(io_obj.readline):
                token_type = tok[0]
                token_string = tok[1]
                start_line, start_col = tok[2]
                end_line, end_col = tok[3]
                
                # Saute les commentaires et les docstrings
                if token_type == tokenize.COMMENT:
                    continue
                if token_type == tokenize.STRING:
                    if prev_toktype != tokenize.INDENT:
                        # C'est une docstring
                        continue
                
                # Ajoute des lignes manquantes
                if start_line > last_lineno:
                    last_col = 0
                if start_col > last_col:
                    out += " " * (start_col - last_col)
                
                out += token_string
                last_col = end_col
                last_lineno = end_line
                prev_toktype = token_type
        except tokenize.TokenError:
            # Gère les erreurs de syntaxe dans le code source
            return source_code
        
        return out
    
    @staticmethod
    def normalize_code(source_code: str) -> str:
        """Normalise le code pour la comparaison."""
        # Supprime les commentaires et les docstrings
        code = CodeNormalizer.remove_comments_and_docstrings(source_code)
        
        # Supprime les espaces, tabulations et sauts de ligne
        code = re.sub(r'\s+', ' ', code)
        
        # Supprime les chaînes littérales
        code = re.sub(r'".*?"', '""', code)
        code = re.sub(r"'.*?'", "''", code)
        
        # Normalisation des noms de variables (simplifié)
        # Une normalisation plus avancée pourrait remplacer tous les noms de variables
        # par des placeholders génériques, mais cela nécessiterait une analyse syntaxique complète
        
        return code.strip()
    
    @staticmethod
    def extract_functions_and_methods(source_code: str) -> List[str]:
        """Extrait les fonctions et méthodes du code source."""
        try:
            tree = ast.parse(source_code)
            functions = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_source = ast.get_source_segment(source_code, node)
                    if func_source:
                        functions.append(func_source)
            
            return functions
        except SyntaxError:
            # En cas d'erreur de syntaxe, retourne une liste vide
            return []

class SimilarityDetector:
    """Classe pour détecter les similitudes entre fichiers de code."""
    
    @staticmethod
    def compute_sequence_similarity(code1: str, code2: str) -> float:
        """Calcule la similarité de séquence entre deux blocs de code."""
        # Optimisation : utiliser quick_ratio pour plus de rapidité avec une précision raisonnable
        matcher = difflib.SequenceMatcher(None, code1, code2)
        return matcher.quick_ratio()
    
    @staticmethod
    def compute_token_similarity(code1: str, code2: str) -> float:
        """Calcule la similarité basée sur les tokens entre deux blocs de code."""
        tokens1 = code1.split()
        tokens2 = code2.split()
        
        # Créer des compteurs de tokens
        counter1 = Counter(tokens1)
        counter2 = Counter(tokens2)
        
        # Calculer l'intersection des tokens
        common_tokens = set(counter1.keys()) & set(counter2.keys())
        if not common_tokens:
            return 0.0
        
        # Calcule de la similarité cosinus
        dot_product = sum(counter1[token] * counter2[token] for token in common_tokens)
        magnitude1 = np.sqrt(sum(count**2 for count in counter1.values()))
        magnitude2 = np.sqrt(sum(count**2 for count in counter2.values()))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
            
        return dot_product / (magnitude1 * magnitude2)
    
    @staticmethod
    def compute_function_similarity(functions1: List[str], functions2: List[str]) -> Tuple[float, List[Tuple[int, int, float]]]:
        """Calcule la similarité entre les fonctions de deux fichiers."""
        if not functions1 or not functions2:
            return 0.0, []
        
        # Normaliser toutes les fonctions
        norm_funcs1 = [CodeNormalizer.normalize_code(f) for f in functions1]
        norm_funcs2 = [CodeNormalizer.normalize_code(f) for f in functions2]
        
        # Optimisation: limiter le nombre de comparaisons en ignorant les fonctions trop petites
        valid_funcs1 = [(i, f) for i, f in enumerate(norm_funcs1) if len(f) > MIN_CODE_LENGTH]
        valid_funcs2 = [(i, f) for i, f in enumerate(norm_funcs2) if len(f) > MIN_CODE_LENGTH]
        
        # Calculer la similarité entre chaque paire de fonctions valides
        similarity_matrix = []
        for i, func1 in valid_funcs1:
            for j, func2 in valid_funcs2:
                sim = SimilarityDetector.compute_sequence_similarity(func1, func2)
                similarity_matrix.append((i, j, sim))
        
        # Trier par similarité décroissante
        similarity_matrix.sort(key=lambda x: x[2], reverse=True)
        
        # Calculer la similarité globale (moyenne des meilleures correspondances)
        if not similarity_matrix:
            return 0.0, []
        
        # Prendre uniquement les meilleures correspondances pour chaque fonction
        best_matches = {}
        for i, j, sim in similarity_matrix:
            if i not in best_matches or best_matches[i][2] < sim:
                best_matches[i] = (i, j, sim)
        
        if not best_matches:
            return 0.0, similarity_matrix
            
        total_sim = sum(sim for _, _, sim in best_matches.values())
        avg_sim = total_sim / len(best_matches)
        
        return avg_sim, similarity_matrix
    
    @staticmethod
    def compute_file_similarity(file1_path: str, file2_path: str) -> Dict[str, Any]:
        """Calcule diverses métriques de similarité entre deux fichiers."""
        try:
            with open(file1_path, 'r', encoding='utf-8') as f1, open(file2_path, 'r', encoding='utf-8') as f2:
                code1 = f1.read()
                code2 = f2.read()
                
                # Vérifier la taille minimale
                if len(code1) < MIN_CODE_LENGTH or len(code2) < MIN_CODE_LENGTH:
                    return {
                        "sequence_similarity": 0.0,
                        "token_similarity": 0.0,
                        "function_similarity": 0.0,
                        "matched_functions": [],
                        "overall_similarity": 0.0
                    }
                
                # Normaliser le code
                norm_code1 = CodeNormalizer.normalize_code(code1)
                norm_code2 = CodeNormalizer.normalize_code(code2)
                
                # Calcul de la similarité de séquence
                seq_sim = SimilarityDetector.compute_sequence_similarity(norm_code1, norm_code2)
                
                # Calcul de la similarité de tokens
                token_sim = SimilarityDetector.compute_token_similarity(norm_code1, norm_code2)
                
                # Extraction et comparaison des fonctions
                functions1 = CodeNormalizer.extract_functions_and_methods(code1)
                functions2 = CodeNormalizer.extract_functions_and_methods(code2)
                func_sim, matched_funcs = SimilarityDetector.compute_function_similarity(functions1, functions2)
                
                # Similarité globale (moyenne pondérée)
                overall_sim = (seq_sim * 0.3) + (token_sim * 0.3) + (func_sim * 0.4)
                
                return {
                    "sequence_similarity": seq_sim,
                    "token_similarity": token_sim,
                    "function_similarity": func_sim,
                    "matched_functions": matched_funcs,
                    "overall_similarity": overall_sim
                }
        except Exception as e:
            print(f"Erreur lors de la comparaison des fichiers {file1_path} et {file2_path}: {e}")
            return {
                "sequence_similarity": 0.0,
                "token_similarity": 0.0,
                "function_similarity": 0.0,
                "matched_functions": [],
                "overall_similarity": 0.0,
                "error": str(e)
            }

class PlagiarismReporter:
    """Classe pour générer des rapports de plagiat."""
    
    @staticmethod
    def calculate_cheating_probability(similarity: float) -> float:
        """Calcule une probabilité de triche basée sur la similarité."""
        if similarity < 0.5:
            # Similarité faible, probabilité faible
            return similarity * 0.2
        elif similarity < 0.7:
            # Similarité moyenne, probabilité modérée
            return 0.1 + similarity * 0.5
        else:
            # Haute similarité, probabilité élevée
            return 0.3 + similarity * 0.7
    
    @staticmethod
    def generate_report(similarity_results: List[Dict[str, Any]], file_pairs: List[Tuple[str, str]]) -> None:
        """Génère un rapport détaillé des similarités."""
        print("\n" + "="*80)
        print(" RAPPORT DE SIMILARITÉ ENTRE LES AGENTS ".center(80, "="))
        print("="*80 + "\n")
        
        # Trier les résultats par similarité globale décroissante
        sorted_results = sorted(zip(similarity_results, file_pairs), 
                               key=lambda x: x[0]["overall_similarity"], 
                               reverse=True)
        
        # Afficher les résultats
        for i, (result, (file1, file2)) in enumerate(sorted_results):
            # Ne montrer que les paires ayant une similarité significative
            if result["overall_similarity"] < 0.4:
                continue
                
            prob = PlagiarismReporter.calculate_cheating_probability(result["overall_similarity"])
            
            print(f"{i+1}. Comparaison: {os.path.basename(file1)} <-> {os.path.basename(file2)}")
            print(f"   Similarité globale: {result['overall_similarity']:.2f} (Probabilité de triche: {prob:.2f})")
            print(f"   Similarité de séquence: {result['sequence_similarity']:.2f}")
            print(f"   Similarité de tokens: {result['token_similarity']:.2f}")
            print(f"   Similarité de fonctions: {result['function_similarity']:.2f}")
            
            # Afficher les fonctions les plus similaires
            if result["matched_functions"]:
                top_matches = result["matched_functions"][:3]  # Afficher les 3 meilleures correspondances
                print("   Fonctions les plus similaires:")
                for i1, i2, sim in top_matches:
                    if sim > 0.7:  # Ne montrer que les correspondances significatives
                        print(f"     - Fonction {i1+1} dans {os.path.basename(file1)} <-> Fonction {i2+1} dans {os.path.basename(file2)}: {sim:.2f}")
            
            print("-"*80)
        
        # Résumé des résultats
        high_sim_count = sum(1 for r, _ in sorted_results if r["overall_similarity"] > SIMILARITY_THRESHOLD)
        print("\nRÉSUMÉ:")
        print(f"Total des paires analysées: {len(sorted_results)}")
        print(f"Paires avec similarité élevée (>{SIMILARITY_THRESHOLD}): {high_sim_count}")
        
        # Afficher les paires les plus suspectes
        if high_sim_count > 0:
            print("\nPAIRES LES PLUS SUSPECTES:")
            for i, (result, (file1, file2)) in enumerate(sorted_results):
                if result["overall_similarity"] > SIMILARITY_THRESHOLD:
                    prob = PlagiarismReporter.calculate_cheating_probability(result["overall_similarity"])
                    print(f"{i+1}. {os.path.basename(file1)} <-> {os.path.basename(file2)}: " +
                          f"Similarité {result['overall_similarity']:.2f}, Probabilité de triche: {prob:.2f}")
        
        print("\n" + "="*80)

def process_file_pair(pair_info):
    """Traite une paire de fichiers en parallèle."""
    index, total, file1, file2 = pair_info
    if VERBOSE:
        print(f"Analyse de la paire {index+1}/{total}: {os.path.basename(file1)} <-> {os.path.basename(file2)}")
    return SimilarityDetector.compute_file_similarity(file1, file2)

def show_progress(done, total, width=50):
    """Affiche une barre de progression."""
    percent = int(100 * done / total)
    filled = int(width * done / total)
    bar = '█' * filled + '-' * (width - filled)
    sys.stdout.write(f"\r[{bar}] {percent}% ({done}/{total})")
    sys.stdout.flush()

def main():
    """Fonction principale du détecteur de plagiat."""
    start_time = time.time()
    print("Démarrage du détecteur de similarité pour les agents...")
    
    # Vérifier si le dossier existe
    agents_path = Path(AGENTS_DIR)
    if not agents_path.exists() or not agents_path.is_dir():
        print(f"Erreur: Le dossier {AGENTS_DIR} n'existe pas ou n'est pas un répertoire.")
        sys.exit(1)
    
    # Récupérer tous les fichiers Python du dossier
    python_files = [str(f) for f in agents_path.glob("*.py") if f.is_file()]
    
    # Filtrer les fichiers staff si nécessaire
    student_files = [f for f in python_files if not os.path.basename(f).startswith(STAFF_PREFIX)]
    
    if not student_files:
        print("Aucun fichier d'agent étudiant trouvé.")
        sys.exit(0)
    
    print(f"Trouvé {len(student_files)} fichiers d'agents à analyser.")
    
    # Générer toutes les paires de fichiers à comparer
    file_pairs = list(itertools.combinations(student_files, 2))
    total_pairs = len(file_pairs)
    print(f"Comparaison de {total_pairs} paires de fichiers...")
    
    # Préparer les arguments pour le traitement parallèle
    pair_infos = [(i, total_pairs, file1, file2) for i, (file1, file2) in enumerate(file_pairs)]
    
    # Utiliser un ThreadPoolExecutor pour paralléliser les comparaisons
    similarity_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_file_pair, pair_info) for pair_info in pair_infos]
        
        # Afficher la progression
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            show_progress(i+1, total_pairs)
            similarity_results.append(future.result())
    
    print("\nAnalyse des fichiers terminée. Génération du rapport...")
    
    # Générer le rapport
    PlagiarismReporter.generate_report(similarity_results, file_pairs)
    
    elapsed_time = time.time() - start_time
    print(f"Analyse terminée en {elapsed_time:.2f} secondes.")

if __name__ == "__main__":
    main()
