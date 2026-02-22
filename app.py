import sys
import subprocess
import sqlite3
from flask import Flask, render_template, request, jsonify, redirect, url_for

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('banqueMe.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/lancer_parsing')
def lancer_parsing():
    try:
        # Utilisation de sys.executable pour garantir le bon environnement python
        subprocess.run([sys.executable, 'parser.py'], check=True)
    except Exception as e:
        print(f"Erreur lors du parsing : {e}")
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
   
    # Liste des catégories
    categories = conn.execute("SELECT sous_categorie FROM categorie WHERE sous_categorie != 'À classer' ORDER BY sous_categorie").fetchall()
    
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
    # Cette requête calcule la somme réelle par catégorie et cherche le prévisionnel correspondant
    comparaison = conn.execute(f"""
        SELECT 
            c.sous_categorie,
            IFNULL(p.montant_mensuel_prevu, 0) as montant_prevu,
            ABS(SUM(CASE WHEN d.annee = ? { "AND d.jour_mois LIKE ?" if f_mois else "" } THEN d.montant ELSE 0 END)) as montant_reel
        FROM categorie c
        LEFT JOIN previsionnel p ON c.sous_categorie = p.sous_categorie AND p.annee = ?
        LEFT JOIN detaillee d ON c.sous_categorie = d.sous_categorie
        WHERE c.sous_categorie != 'À classer'
        GROUP BY c.sous_categorie
        HAVING montant_reel > 0 OR montant_prevu > 0
        ORDER BY montant_reel DESC
    """, [f_annee, f"%{f_mois}%", f_annee] if f_mois else [f_annee, f_annee]).fetchall()

    conn.close()
    
    # Préparation des labels et données pour Chart.js
    labels = [r['sous_categorie'] for r in comparaison]
    data_reel = [r['montant_reel'] for r in comparaison]
    data_prevu = [r['montant_prevu'] for r in comparaison]
    
    return render_template('index.html', 
                           a_classer=a_classer, 
                           categories=categories, 
                           comparaison=comparaison, 
                           historique=historique,
                           filtre_annee=f_annee, filtre_mois=f_mois, filtre_cat=f_cat,
                           labels=labels, data_reel=data_reel, data_prevu=data_prevu)

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

if __name__ == '__main__':
    app.run(debug=True)