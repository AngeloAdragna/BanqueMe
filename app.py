import sys
import subprocess
import sqlite3
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, make_response
import csv
import io

app = Flask(__name__)
# OBLIGATOIRE : Flask a besoin d'une clé secrète pour sécuriser les messages (sessions)
app.secret_key = "super_cle_secrete_banqueme" 

def get_db_connection():
    conn = sqlite3.connect('banqueMe.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/lancer_parsing')
def lancer_parsing():
    try:
        # Utilisation de sys.executable pour garantir le bon environnement python
        subprocess.run([sys.executable, 'parser.py'], check=True)
        # Message de succès
        flash("Les mails ont été synchronisés avec succès !", "success")
    except Exception as e:
        print(f"Erreur lors du parsing : {e}")
        # Message d'erreur
        flash(f"Échec de la synchronisation : {e}", "danger")
        
    return redirect(url_for('index'))

@app.route('/')
def index():
    conn = get_db_connection()
    
    # Récupération des filtres
    f_annee = request.args.get('annee', '2025')
    f_mois = request.args.get('mois', '')
    f_cat = request.args.get('categorie', '')

    # 1. Onglet Tri : Transactions "À classer" (Sécurité : strip pour les espaces)
    a_classer = conn.execute("""
        SELECT * FROM detaillee 
        WHERE sous_categorie LIKE 'À classer' 
           OR sous_categorie LIKE 'A classer'
    """).fetchall()
   
    # Liste simple pour le Drag & Drop et la saisie
    categories = conn.execute("SELECT sous_categorie FROM categorie WHERE sous_categorie != 'À classer' ORDER BY sous_categorie").fetchall()
    
    # NOUVEAU : Liste complète (avec budget) pour l'onglet de gestion
    categories_completes = conn.execute("""
        SELECT c.id_categorie, c.nom_categorie, c.sous_categorie, IFNULL(p.montant_mensuel_prevu, 0) as prevu
        FROM categorie c
        LEFT JOIN previsionnel p ON c.sous_categorie = p.sous_categorie AND p.annee = ?
        WHERE c.sous_categorie != 'À classer'
        ORDER BY c.nom_categorie, c.sous_categorie
    """, (f_annee,)).fetchall()
    # 2. Construction de la requête filtrée pour le Réel
    query_reel = "FROM detaillee WHERE sous_categorie != 'À classer' AND annee = ?"
    params_reel = [f_annee]
    
    if f_cat:
        query_reel += " AND sous_categorie = ?"
        params_reel.append(f_cat)
    if f_mois:
        query_reel += " AND jour_mois LIKE ?"
        params_reel.append(f"%{f_mois}%")

    # Données pour l'historique
    historique = conn.execute(f"SELECT * {query_reel} ORDER BY id_transaction DESC", params_reel).fetchall()

    # 3. Comparaison Prévu vs Réel (Pour le résumé et les graphs)
    comparaison = conn.execute(f"""
        SELECT 
            c.sous_categorie,
            IFNULL(p.montant_mensuel_prevu, 0) as montant_prevu,
            -- On ajoute IFNULL(...) ici pour transformer les calculs vides en 0
            IFNULL(ABS(SUM(CASE WHEN d.annee = ? { "AND d.jour_mois LIKE ?" if f_mois else "" } THEN d.montant ELSE 0 END)), 0) as montant_reel
        FROM categorie c
        LEFT JOIN previsionnel p ON c.sous_categorie = p.sous_categorie AND p.annee = ?
        LEFT JOIN detaillee d ON c.sous_categorie = d.sous_categorie
        WHERE c.sous_categorie != 'À classer'
        GROUP BY c.sous_categorie
        -- On a supprimé le HAVING pour que toutes les catégories s'affichent, même celles à 0€
        ORDER BY montant_reel DESC, c.sous_categorie ASC
    """, [f_annee, f"%{f_mois}%", f_annee] if f_mois else [f_annee, f_annee]).fetchall()

    conn.close()
    
    # Préparation des labels et données pour Chart.js
    labels = [r['sous_categorie'] for r in comparaison]
    data_reel = [r['montant_reel'] for r in comparaison]
    data_prevu = [r['montant_prevu'] for r in comparaison]
    
   # --- 4. CALCUL DES STATISTIQUES (KPIs) ---
    total_reel = sum(data_reel)
    
    # Si on regarde toute l'année (pas de mois sélectionné), le budget prévu est sur 12 mois
    multiplicateur_mois = 1 if f_mois else 12
    total_prevu = sum(data_prevu) * multiplicateur_mois
    
    # Écart : Positif = Économies réalisées, Négatif = Dépassement
    ecart = total_prevu - total_reel
    
    # Logique pour la tendance (couleur et clé de traduction)
    if total_reel == 0:
        tendance_key = "trendWaiting"
        tendance_color = "var(--text-muted)" # Gris
    elif ecart >= 0:
        tendance_key = "trendGood"
        tendance_color = "var(--success)" # Vert
    elif ecart >= -100: # Tolérance de dépassement (ex: 100€)
        tendance_key = "trendWarning"
        tendance_color = "#b8860b" # Or/Moutarde
    else:
        tendance_key = "trendDanger"
        tendance_color = "var(--danger)" # Rouge

    return render_template('index.html', 
                           a_classer=a_classer, 
                           categories=categories,
                           categories_completes=categories_completes, # Ton ajout précédent
                           comparaison=comparaison, 
                           historique=historique,
                           filtre_annee=f_annee, filtre_mois=f_mois, filtre_cat=f_cat,
                           labels=labels, data_reel=data_reel, data_prevu=data_prevu,
                           # NOUVEAUX PARAMÈTRES ENVOYÉS AU HTML :
                           total_reel=round(total_reel, 2),
                           ecart=round(ecart, 2),
                           tendance_key=tendance_key,
                           tendance_color=tendance_color)

@app.route('/update_category', methods=['POST'])
def update_category():
    data = request.get_json()
    conn = get_db_connection()
    conn.execute("UPDATE detaillee SET sous_categorie = ? WHERE id_transaction = ?", 
                 (data.get('new_category'), data.get('transaction_id')))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/ajouter_manuel', methods=['POST'])
def ajouter_manuel():
    conn = get_db_connection()
    conn.execute("INSERT INTO detaillee (sous_categorie, montant, jour_mois, annee, commentaire) VALUES (?, ?, ?, ?, ?)",
                 (request.form.get('categorie'), float(request.form.get('montant').replace(',', '.')), 
                  request.form.get('jour_mois'), int(request.form.get('annee')), request.form.get('commentaire')))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/ajouter_categorie', methods=['POST'])
def ajouter_categorie():
    nom_cat = request.form.get('nom_categorie')
    sous_cat = request.form.get('sous_categorie')
    prevu = float(request.form.get('montant_prevu', 0))
    annee = int(request.form.get('annee', 2025))
    
    conn = get_db_connection()
    try:
        # 1. Ajout de la catégorie
        conn.execute("INSERT INTO categorie (nom_categorie, sous_categorie) VALUES (?, ?)", (nom_cat, sous_cat))
        # 2. Ajout de son budget prévisionnel
        conn.execute("INSERT INTO previsionnel (sous_categorie, montant_mensuel_prevu, annee) VALUES (?, ?, ?)", (sous_cat, prevu, annee))
        conn.commit()
        flash(f"Catégorie '{sous_cat}' ajoutée avec succès !", "success")
    except sqlite3.IntegrityError:
        flash("Erreur : Cette sous-catégorie existe déjà.", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('index'))

@app.route('/supprimer_categorie/<int:id_cat>/<string:sous_cat>', methods=['POST'])
def supprimer_categorie(id_cat, sous_cat):
    conn = get_db_connection()
    # Sécurité : On vérifie si la catégorie est utilisée dans des transactions
    utilisation = conn.execute("SELECT COUNT(*) as count FROM detaillee WHERE sous_categorie = ?", (sous_cat,)).fetchone()
    
    if utilisation['count'] > 0:
        flash(f"Impossible : '{sous_cat}' est utilisée dans {utilisation['count']} transaction(s).", "danger")
    else:
        conn.execute("DELETE FROM previsionnel WHERE sous_categorie = ?", (sous_cat,))
        conn.execute("DELETE FROM categorie WHERE id_categorie = ?", (id_cat,))
        conn.commit()
        flash(f"Catégorie '{sous_cat}' supprimée.", "success")
        
    conn.close()
    return redirect(url_for('index'))

@app.route('/export/csv')
def export_csv():
    f_annee = request.args.get('annee', '2025')
    f_mois = request.args.get('mois', '')
    
    conn = get_db_connection()
    query = "SELECT jour_mois, annee, sous_categorie, montant, commentaire FROM detaillee WHERE sous_categorie != 'À classer'"
    params = []
    
    if f_annee:
        query += " AND annee = ?"
        params.append(f_annee)
    if f_mois:
        query += " AND jour_mois LIKE ?"
        params.append(f"%{f_mois}%")
        
    query += " ORDER BY id_transaction DESC"
    transactions = conn.execute(query, params).fetchall()
    conn.close()

    # Création du fichier CSV en mémoire
    si = io.StringIO()
    # Séparateur point-virgule pour une ouverture parfaite dans le Excel français
    cw = csv.writer(si, delimiter=';') 
    cw.writerow(['Jour/Mois', 'Année', 'Catégorie', 'Montant (€)', 'Description'])
    
    for t in transactions:
        cw.writerow([t['jour_mois'], t['annee'], t['sous_categorie'], t['montant'], t['commentaire']])

    # Préparation de la réponse pour le téléchargement
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=export_budget.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8-sig" # utf-8-sig pour les accents sur Excel
    
    return output

if __name__ == '__main__':
    app.run(debug=True)