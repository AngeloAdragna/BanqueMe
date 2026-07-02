import sys
import subprocess
import sqlite3
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, make_response
import csv
import io
from datetime import datetime

app = Flask(__name__)
app.secret_key = "super_cle_secrete_banqueme" 
ANNEE_COURANTE = str(datetime.now().year)

def get_db_connection():
    conn = sqlite3.connect('banqueMe.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    
    # Table des catégories
    conn.execute('''
    CREATE TABLE IF NOT EXISTS categorie (
        id_categorie INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_categorie TEXT NOT NULL,
        sous_categorie TEXT NOT NULL UNIQUE,
        sens TEXT DEFAULT 'DEPENSE'
    )
    ''')
    
    # Table des transactions
    conn.execute('''
    CREATE TABLE IF NOT EXISTS detaillee (
        id_transaction INTEGER PRIMARY KEY AUTOINCREMENT,
        jour_mois TEXT,
        annee INTEGER,
        montant REAL,
        commentaire TEXT,
        sous_categorie TEXT,
        FOREIGN KEY (sous_categorie) REFERENCES categorie(sous_categorie)
    )
    ''')
    
    # Table du prévisionnel annuel
    conn.execute('''
    CREATE TABLE IF NOT EXISTS previsionnel (
        id_prev INTEGER PRIMARY KEY AUTOINCREMENT,
        sous_categorie TEXT NOT NULL,
        montant_mensuel_prevu REAL NOT NULL,
        annee INTEGER NOT NULL,
        UNIQUE(sous_categorie, annee)
    )
    ''')
    
    # Table des exceptions mensuelles
    conn.execute('''
    CREATE TABLE IF NOT EXISTS previsionnel_exception (
        id_exc INTEGER PRIMARY KEY AUTOINCREMENT,
        sous_categorie TEXT NOT NULL,
        annee INTEGER NOT NULL,
        mois TEXT NOT NULL,
        montant REAL NOT NULL,
        FOREIGN KEY (sous_categorie) REFERENCES categorie(sous_categorie),
        UNIQUE(sous_categorie, annee, mois)
    )
    ''')
    
    conn.commit()
    conn.close()

init_db()

def get_redirect_url(f_annee, f_mois, f_cat, f_groupe):
    return url_for('index', annee=f_annee, mois=f_mois, categorie=f_cat, groupe=f_groupe)

@app.route('/lancer_parsing')
def lancer_parsing():
    try:
        subprocess.run([sys.executable, 'parser.py'], check=True)
        flash("Les mails ont été synchronisés avec succès !", "success")
    except Exception as e:
        print(f"Erreur lors du parsing : {e}")
        flash(f"Échec de la synchronisation : {e}", "danger")
        
    return redirect(url_for('index'))

@app.route('/')
def index():
    conn = get_db_connection()
    
    f_annee = request.args.get('annee', ANNEE_COURANTE)
    f_mois = request.args.get('mois', '')
    f_cat = request.args.get('categorie', '')
    f_groupe = request.args.get('groupe', '')

    a_classer = conn.execute("""
        SELECT * FROM detaillee 
        WHERE sous_categorie LIKE 'À classer' 
           OR sous_categorie LIKE 'A classer'
    """).fetchall()
   
    categories = conn.execute("SELECT sous_categorie FROM categorie WHERE sous_categorie != 'À classer' ORDER BY sous_categorie").fetchall()
    groupes = conn.execute("SELECT DISTINCT nom_categorie FROM categorie WHERE sous_categorie != 'À classer' ORDER BY nom_categorie").fetchall()
    
    categories_completes = conn.execute("""
        SELECT c.id_categorie, c.nom_categorie, c.sous_categorie, c.sens, IFNULL(p.montant_mensuel_prevu, 0) as prevu
        FROM categorie c
        LEFT JOIN previsionnel p ON c.sous_categorie = p.sous_categorie AND p.annee = ?
        WHERE c.sous_categorie != 'À classer'
        ORDER BY c.nom_categorie, c.sous_categorie
    """, (f_annee,)).fetchall()

    query_hist = "FROM detaillee d JOIN categorie c ON d.sous_categorie = c.sous_categorie WHERE d.sous_categorie != 'À classer' AND d.annee = ?"
    params_hist = [f_annee]
    
    if f_cat:
        query_hist += " AND d.sous_categorie = ?"
        params_hist.append(f_cat)
    if f_groupe:
        query_hist += " AND c.nom_categorie = ?"
        params_hist.append(f_groupe)
    if f_mois:
        query_hist += " AND d.jour_mois LIKE ?"
        params_hist.append(f"%{f_mois}%")

    historique = conn.execute(f"SELECT d.*, c.nom_categorie {query_hist} ORDER BY d.id_transaction DESC", params_hist).fetchall()

    where_comp = "WHERE c.sous_categorie != 'À classer'"
    params_comp = []

    if f_mois:
        query_comp = """
            SELECT 
                c.nom_categorie,
                c.sous_categorie,
                c.sens,
                IFNULL(pe.montant, IFNULL(p.montant_mensuel_prevu, 0)) as montant_prevu,
                IFNULL(ABS(SUM(CASE WHEN d.annee = ? AND d.jour_mois LIKE ? THEN d.montant ELSE 0 END)), 0) as montant_reel
            FROM categorie c
            LEFT JOIN previsionnel p ON c.sous_categorie = p.sous_categorie AND p.annee = ?
            LEFT JOIN previsionnel_exception pe ON c.sous_categorie = pe.sous_categorie AND pe.annee = ? AND pe.mois = ?
            LEFT JOIN detaillee d ON c.sous_categorie = d.sous_categorie
        """
        params_comp.extend([f_annee, f"%{f_mois}%", f_annee, f_annee, f_mois])
    else:
        query_comp = """
            SELECT 
                c.nom_categorie,
                c.sous_categorie,
                c.sens,
                (IFNULL(p.montant_mensuel_prevu, 0) * (12 - IFNULL(pe_stats.compte, 0)) + IFNULL(pe_stats.somme, 0)) as montant_prevu,
                IFNULL(ABS(SUM(CASE WHEN d.annee = ? THEN d.montant ELSE 0 END)), 0) as montant_reel
            FROM categorie c
            LEFT JOIN previsionnel p ON c.sous_categorie = p.sous_categorie AND p.annee = ?
            LEFT JOIN (
                SELECT sous_categorie, SUM(montant) as somme, COUNT(*) as compte
                FROM previsionnel_exception
                WHERE annee = ?
                GROUP BY sous_categorie
            ) pe_stats ON c.sous_categorie = pe_stats.sous_categorie
            LEFT JOIN detaillee d ON c.sous_categorie = d.sous_categorie
        """
        params_comp.extend([f_annee, f_annee, f_annee])

    if f_cat:
        where_comp += " AND c.sous_categorie = ?"
        params_comp.append(f_cat)
    if f_groupe:
        where_comp += " AND c.nom_categorie = ?"
        params_comp.append(f_groupe)

    query_comp += f" {where_comp} GROUP BY c.sous_categorie ORDER BY montant_reel DESC, c.sous_categorie ASC"
    comparaison = conn.execute(query_comp, params_comp).fetchall()

    exceptions_raw = conn.execute("SELECT sous_categorie, mois, montant FROM previsionnel_exception WHERE annee = ?", (f_annee,)).fetchall()
    exceptions_dict = {}
    for r in exceptions_raw:
        if r['sous_categorie'] not in exceptions_dict:
            exceptions_dict[r['sous_categorie']] = {}
        exceptions_dict[r['sous_categorie']][r['mois']] = r['montant']

    annees_dispo_raw = conn.execute("SELECT DISTINCT annee FROM previsionnel ORDER BY annee DESC").fetchall()
    annees_dispo = [r['annee'] for r in annees_dispo_raw]
    
    depenses_par_mois = [0] * 12
    revenus_par_mois = [0] * 12
    mois_index = {'janv':0, 'févr':1, 'mars':2, 'avr':3, 'mai':4, 'juin':5, 'juil':6, 'août':7, 'sept':8, 'oct':9, 'nov':10, 'déc':11}
    
    transactions_annee = conn.execute("""
        SELECT d.jour_mois, d.montant, c.sens 
        FROM detaillee d
        JOIN categorie c ON d.sous_categorie = c.sous_categorie
        WHERE d.annee = ? AND d.sous_categorie != 'À classer'
    """, (f_annee,)).fetchall()
    
    for t in transactions_annee:
        parts = t['jour_mois'].split('-')
        mois_key = parts[-1] 
        if mois_key in mois_index:
            if t['sens'] == 'REVENU':
                revenus_par_mois[mois_index[mois_key]] += t['montant']
            else:
                depenses_par_mois[mois_index[mois_key]] += t['montant']

    conn.close()
    
    labels_depenses = []
    data_reel_depenses = []
    data_prevu_depenses = []

    labels_revenus = []
    data_reel_revenus = []
    data_prevu_revenus = []

    total_depenses_reel = 0
    total_depenses_prevu = 0
    total_revenus_reel = 0
    total_revenus_prevu = 0

    for r in comparaison:
        reel = r['montant_reel']
        prevu = r['montant_prevu']
        
        if r['sens'] == 'REVENU':
            total_revenus_reel += reel
            total_revenus_prevu += prevu
            labels_revenus.append(r['sous_categorie'])
            data_reel_revenus.append(reel)
            data_prevu_revenus.append(prevu)
        else:
            total_depenses_reel += reel
            total_depenses_prevu += prevu
            labels_depenses.append(r['sous_categorie'])
            data_reel_depenses.append(reel)
            data_prevu_depenses.append(prevu)

    reste_reel = total_revenus_reel - total_depenses_reel
    reste_prevu = total_revenus_prevu - total_depenses_prevu
    performance_epargne = reste_reel - reste_prevu

    if performance_epargne > 0:
        perf_color = "var(--success)"
        perf_text = "Super ! Vous avez économisé plus que prévu."
    elif performance_epargne < 0:
        perf_color = "var(--danger)"
        perf_text = "Attention, vous avez moins de reste à vivre que prévu."
    else:
        perf_color = "var(--text-muted)"
        perf_text = "Vous êtes exactement sur votre prévisionnel."


    return render_template('index.html', 
                           a_classer=a_classer, categories=categories, groupes=groupes,
                           categories_completes=categories_completes, comparaison=comparaison, historique=historique,
                           filtre_annee=f_annee, filtre_mois=f_mois, filtre_cat=f_cat, filtre_groupe=f_groupe,
                           
                           labels=labels_depenses, data_reel=data_reel_depenses, data_prevu=data_prevu_depenses,
                           labels_revenus=labels_revenus, data_reel_revenus=data_reel_revenus, data_prevu_revenus=data_prevu_revenus,
                           
                           total_depenses_reel=round(total_depenses_reel, 2),
                           total_depenses_prevu=round(total_depenses_prevu, 2),
                           total_revenus_reel=round(total_revenus_reel, 2),
                           total_revenus_prevu=round(total_revenus_prevu, 2),
                           reste_reel=round(reste_reel, 2),
                           reste_prevu=round(reste_prevu, 2),
                           performance_epargne=round(performance_epargne, 2),
                           perf_color=perf_color,
                           perf_text=perf_text,
                           exceptions_dict=exceptions_dict,
                           annees_dispo=annees_dispo,
                           depenses_par_mois=depenses_par_mois,
                           revenus_par_mois=revenus_par_mois)

@app.route('/update_category', methods=['POST'])
def update_category():
    data = request.get_json()
    conn = get_db_connection()
    conn.execute("UPDATE detaillee SET sous_categorie = ? WHERE id_transaction = ?", 
                 (data.get('new_category'), data.get('transaction_id')))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/modifier_transaction', methods=['POST'])
def modifier_transaction():
    id_trans = request.form.get('id_transaction')
    sous_cat = request.form.get('sous_categorie')
    montant = float(request.form.get('montant').replace(',', '.'))
    jour_mois = request.form.get('jour_mois')
    annee = int(request.form.get('annee'))
    commentaire = request.form.get('commentaire')
    
    conn = get_db_connection()
    conn.execute("""
        UPDATE detaillee 
        SET sous_categorie = ?, montant = ?, jour_mois = ?, annee = ?, commentaire = ? 
        WHERE id_transaction = ?
    """, (sous_cat, montant, jour_mois, annee, commentaire, id_trans))
    conn.commit()
    conn.close()
    flash("Transaction modifiée avec succès !", "success")
    return redirect(get_redirect_url(request.form.get('annee_persist'), request.form.get('mois_persist'), request.form.get('categorie_persist'), request.form.get('groupe_persist')))

@app.route('/supprimer_transaction', methods=['POST'])
def supprimer_transaction():
    id_trans = request.form.get('id_transaction')
    conn = get_db_connection()
    conn.execute("DELETE FROM detaillee WHERE id_transaction = ?", (id_trans,))
    conn.commit()
    conn.close()
    flash("Transaction supprimée avec succès.", "success")
    return redirect(get_redirect_url(request.form.get('annee_persist'), request.form.get('mois_persist'), request.form.get('categorie_persist'), request.form.get('groupe_persist')))

@app.route('/ajouter_manuel', methods=['POST'])
def ajouter_manuel():
    raw_date = request.form.get('jour_mois')
    date_obj = datetime.strptime(raw_date, '%Y-%m-%d')
    mois_noms = ['janv', 'févr', 'mars', 'avr', 'mai', 'juin', 'juil', 'août', 'sept', 'oct', 'nov', 'déc']
    jour_mois_format = f"{date_obj.day:02d}-{mois_noms[date_obj.month - 1]}"
    annee = date_obj.year

    conn = get_db_connection()
    conn.execute("INSERT INTO detaillee (sous_categorie, montant, jour_mois, annee, commentaire) VALUES (?, ?, ?, ?, ?)",
                 (request.form.get('categorie'), float(request.form.get('montant').replace(',', '.')), 
                  jour_mois_format, annee, request.form.get('commentaire')))
    conn.commit()
    conn.close()
    
    flash("Transaction ajoutée manuellement.", "success")
    return redirect(get_redirect_url(request.form.get('annee_persist'), request.form.get('mois_persist'), request.form.get('categorie_persist'), request.form.get('groupe_persist')))

@app.route('/ajouter_categorie', methods=['POST'])
def ajouter_categorie():
    nom_cat = request.form.get('nom_categorie')
    sous_cat = request.form.get('sous_categorie')
    sens = request.form.get('sens', 'DEPENSE')
    
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO categorie (nom_categorie, sous_categorie, sens) VALUES (?, ?, ?)", (nom_cat, sous_cat, sens))
        conn.commit()
        flash(f"Catégorie '{sous_cat}' ajoutée avec succès !", "success")
    except sqlite3.IntegrityError:
        flash("Erreur : Cette sous-catégorie existe déjà.", "danger")
    finally:
        conn.close()
    return redirect(get_redirect_url(request.form.get('annee_persist'), request.form.get('mois_persist'), request.form.get('categorie_persist'), request.form.get('groupe_persist')))

@app.route('/modifier_categorie', methods=['POST'])
def modifier_categorie():
    id_cat = request.form.get('id_categorie')
    ancien_sous_cat = request.form.get('ancien_sous_categorie')
    nouveau_nom_cat = request.form.get('nom_categorie')
    nouveau_sous_cat = request.form.get('sous_categorie')
    sens = request.form.get('sens', 'DEPENSE')
    
    conn = get_db_connection()
    try:
        conn.execute("PRAGMA foreign_keys = OFF;")
        conn.execute("UPDATE categorie SET nom_categorie = ?, sous_categorie = ?, sens = ? WHERE id_categorie = ?", (nouveau_nom_cat, nouveau_sous_cat, sens, id_cat))
        conn.execute("UPDATE detaillee SET sous_categorie = ? WHERE sous_categorie = ?", (nouveau_sous_cat, ancien_sous_cat))
        conn.execute("UPDATE previsionnel SET sous_categorie = ? WHERE sous_categorie = ?", (nouveau_sous_cat, ancien_sous_cat))
        conn.execute("UPDATE previsionnel_exception SET sous_categorie = ? WHERE sous_categorie = ?", (nouveau_sous_cat, ancien_sous_cat))
        conn.commit()
        flash(f"Catégorie '{nouveau_sous_cat}' mise à jour.", "success")
    except sqlite3.IntegrityError:
        flash("Erreur : Ce nom de sous-catégorie existe déjà.", "danger")
    finally:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.close()
    return redirect(get_redirect_url(request.form.get('annee_persist'), request.form.get('mois_persist'), request.form.get('categorie_persist'), request.form.get('groupe_persist')))

@app.route('/sauvegarder_planification', methods=['POST'])
def sauvegarder_planification():
    sous_cat = request.form.get('sous_categorie')
    annee = int(request.form.get('annee'))
    montant_defaut = float(request.form.get('montant_defaut', 0))
    
    liste_mois = ['janv', 'févr', 'mars', 'avr', 'mai', 'juin', 'juil', 'août', 'sept', 'oct', 'nov', 'déc']
    
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO previsionnel (sous_categorie, montant_mensuel_prevu, annee) 
        VALUES (?, ?, ?) 
        ON CONFLICT(sous_categorie, annee) 
        DO UPDATE SET montant_mensuel_prevu = excluded.montant_mensuel_prevu
    """, (sous_cat, montant_defaut, annee))
    
    conn.execute("DELETE FROM previsionnel_exception WHERE sous_categorie = ? AND annee = ?", (sous_cat, annee))
    
    for mois in liste_mois:
        val = request.form.get(f"exc_{mois}")
        if val and val.strip() != "":
            conn.execute("""
                INSERT INTO previsionnel_exception (sous_categorie, annee, mois, montant) 
                VALUES (?, ?, ?, ?)
            """, (sous_cat, annee, mois, float(val)))
            
    conn.commit()
    conn.close()
    flash(f"Budget pour '{sous_cat}' enregistré avec succès !", "success")
    return redirect(get_redirect_url(request.form.get('annee_persist'), request.form.get('mois_persist'), request.form.get('categorie_persist'), request.form.get('groupe_persist')))

@app.route('/copier_budget', methods=['POST'])
def copier_budget():
    annee_source = int(request.form.get('annee_source'))
    annee_cible = int(request.form.get('annee_cible'))
    
    if annee_source == annee_cible:
        flash("Impossible de copier une année sur elle-même.", "warning")
        return redirect(get_redirect_url(request.form.get('annee_persist'), request.form.get('mois_persist'), request.form.get('categorie_persist'), request.form.get('groupe_persist')))
        
    conn = get_db_connection()
    budgets = conn.execute("SELECT sous_categorie, montant_mensuel_prevu FROM previsionnel WHERE annee = ?", (annee_source,)).fetchall()
    for b in budgets:
        conn.execute("""
            INSERT INTO previsionnel (sous_categorie, montant_mensuel_prevu, annee) 
            VALUES (?, ?, ?) 
            ON CONFLICT(sous_categorie, annee) 
            DO UPDATE SET montant_mensuel_prevu = excluded.montant_mensuel_prevu
        """, (b['sous_categorie'], b['montant_mensuel_prevu'], annee_cible))
        
    exceptions = conn.execute("SELECT sous_categorie, mois, montant FROM previsionnel_exception WHERE annee = ?", (annee_source,)).fetchall()
    for e in exceptions:
        conn.execute("""
            INSERT INTO previsionnel_exception (sous_categorie, annee, mois, montant) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT(sous_categorie, annee, mois)
            DO UPDATE SET montant = excluded.montant
        """, (e['sous_categorie'], annee_cible, e['mois'], e['montant']))
        
    conn.commit()
    conn.close()
    
    flash(f"La planification de l'année {annee_source} a été copiée vers {annee_cible} !", "success")
    return redirect(get_redirect_url(request.form.get('annee_persist'), request.form.get('mois_persist'), request.form.get('categorie_persist'), request.form.get('groupe_persist')))

@app.route('/supprimer_categorie/<int:id_cat>/<string:sous_cat>', methods=['POST'])
def supprimer_categorie(id_cat, sous_cat):
    conn = get_db_connection()
    utilisation = conn.execute("SELECT COUNT(*) as count FROM detaillee WHERE sous_categorie = ?", (sous_cat,)).fetchone()
    
    if utilisation['count'] > 0:
        flash(f"Impossible : '{sous_cat}' est utilisée dans {utilisation['count']} transaction(s).", "danger")
    else:
        conn.execute("DELETE FROM previsionnel WHERE sous_categorie = ?", (sous_cat,))
        conn.execute("DELETE FROM categorie WHERE id_categorie = ?", (id_cat,))
        conn.commit()
        flash(f"Catégorie '{sous_cat}' supprimée.", "success")
        
    conn.close()
    return redirect(get_redirect_url(request.form.get('annee_persist'), request.form.get('mois_persist'), request.form.get('categorie_persist'), request.form.get('groupe_persist')))

@app.route('/export/csv')
def export_csv():
    f_annee = request.args.get('annee', ANNEE_COURANTE)
    f_mois = request.args.get('mois', '')
    f_cat = request.args.get('categorie', '')
    f_groupe = request.args.get('groupe', '')
    
    conn = get_db_connection()
    query = "SELECT d.jour_mois, d.annee, c.nom_categorie, d.sous_categorie, d.montant, d.commentaire FROM detaillee d JOIN categorie c ON d.sous_categorie = c.sous_categorie WHERE d.sous_categorie != 'À classer'"
    params = []
    
    if f_annee: query += " AND d.annee = ?"; params.append(f_annee)
    if f_mois: query += " AND d.jour_mois LIKE ?"; params.append(f"%{f_mois}%")
    if f_cat: query += " AND d.sous_categorie = ?"; params.append(f_cat)
    if f_groupe: query += " AND c.nom_categorie = ?"; params.append(f_groupe)
        
    query += " ORDER BY d.id_transaction DESC"
    transactions = conn.execute(query, params).fetchall()
    conn.close()

    si = io.StringIO()
    cw = csv.writer(si, delimiter=';') 
    cw.writerow(['Jour/Mois', 'Année', 'Groupe', 'Catégorie', 'Montant (€)', 'Description'])
    
    for t in transactions:
        cw.writerow([t['jour_mois'], t['annee'], t['nom_categorie'], t['sous_categorie'], t['montant'], t['commentaire']])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=export_budget.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8-sig" 
    
    return output

if __name__ == '__main__':
    app.run(debug=True)