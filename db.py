import sqlite3

# 1. Création (ou ouverture) du fichier .db
conn = sqlite3.connect('banqueMe.db')
cursor = conn.cursor()

# 2. Création des tables
cursor.execute('''
CREATE TABLE IF NOT EXISTS categorie (
    id_categorie INTEGER PRIMARY KEY AUTOINCREMENT,
    nom_categorie TEXT NOT NULL,
    sous_categorie TEXT NOT NULL UNIQUE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS detaillee (
    id_transaction INTEGER PRIMARY KEY AUTOINCREMENT,
    sous_categorie TEXT NOT NULL,
    montant REAL NOT NULL,
    jour_mois TEXT,
    annee INTEGER,
    commentaire TEXT,
    id_message TEXT UNIQUE,
    FOREIGN KEY (sous_categorie) REFERENCES categorie(sous_categorie)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS previsionnel (
    id_prev INTEGER PRIMARY KEY AUTOINCREMENT,
    sous_categorie TEXT NOT NULL,
    montant_mensuel_prevu REAL NOT NULL,
    annee INTEGER NOT NULL,
    FOREIGN KEY (sous_categorie) REFERENCES categorie(sous_categorie),
    UNIQUE(sous_categorie, annee)
)
''')

# 3. Remplissage des Catégories
categories_data = [
    ('Assurance', 'voiture'),
    ('Assurance', 'logement'),
    ('Assurance', 'civile'),
    ('Logement', 'loyer Avignon'),
    ('Banque', 'CB'),
    ('Etat', 'cotisation'),
    ('Etat', 'impots'),
    ('Voiture', 'essence'),
    ('Voiture', 'reparation'),
    ('Abonnement', 'Netflix'),
    ('Abonnement', 'youtube music'),
    ('Abonnement', 'Cinepass'),
    ('Entretien', 'linge'),
    ('Nourriture', 'crous'),
    ('Nourriture', 'cantine ISC'),
    ('Nourriture', 'courses'),
    ('Nourriture', 'restaurant'),
    ('Cadeau', 'cadeau'),
    ('Salaire', 'salaire brut'),
    ('Salaire', 'prime'),
    ('Salaire', 'depannage'),
    ('Aide', 'APL'),
    ('Aide', 'Action logement'),
    ('Aide', 'Prime activite'),
    ('Aide', 'pension'),
    ('Système', 'À classer')
]
cursor.executemany('''INSERT OR IGNORE INTO categorie (nom_categorie, sous_categorie) VALUES (?, ?)''', categories_data)

# 4. Remplissage du PRÉVISIONNEL 2025 (Les métriques de tes objectifs)
previsionnel_data = [
    ('voiture', 38.19, 2025),
    ('logement', 4.62, 2025),
    ('civile', 2.00, 2025),
    ('loyer Avignon', 348.00, 2025),
    ('CB', 11.10, 2025),
    ('cotisation', 78.66, 2025),
    ('essence', 150.00, 2025),
    ('reparation', 0.00, 2025),
    ('Netflix', 7.99, 2025),
    ('youtube music', 5.49, 2025),
    ('Cinepass', 18.40, 2025),
    ('linge', 6.00, 2025),
    ('crous', 10.00, 2025),
    ('cantine ISC', 45.00, 2025),
    ('courses', 100.00, 2025),
    ('restaurant', 50.00, 2025),
    ('cadeau', 50.00, 2025),
    ('salaire brut', 1199.69, 2025),
    ('APL', 168.00, 2025),
    ('Action logement', 100.00, 2025),
    ('Prime activite', 200.00, 2025),
    ('pension', 0.00, 2025)
]
cursor.executemany('''INSERT OR IGNORE INTO previsionnel (sous_categorie, montant_mensuel_prevu, annee) VALUES (?, ?, ?)''', previsionnel_data)

# 5. Remplissage des dépenses réelles (Historique)
depenses_data = [
    ('loyer Avignon', 348.30, '22-sept', 2025, None),
    ('loyer Avignon', 348.30, '18-oct', 2025, None),
    ('loyer Avignon', 348.30, '15-nov', 2025, None),
    ('CB', 11.10, '16-sept', 2025, None),
    ('CB', 11.10, '16-oct', 2025, None),
    ('CB', 11.10, None, 2025, 'Frais mois de novembre'),
    ('cotisation', 78.66, None, 2025, 'Mois de septembre'),
    ('cotisation', 78.66, None, 2025, 'Mois de octobre'),
    ('essence', 65.00, None, 2025, 'Mois de septembre'),
    ('essence', 30.39, '01-oct', 2025, None),
    ('essence', 29.10, '26-oct', 2025, None),
    ('essence', 30.01, '15-nov', 2025, None),
    ('Netflix', 7.99, '30-sept', 2025, None),
    ('Netflix', 7.99, '29-oct', 2025, None),
    ('Netflix', 7.99, None, 2025, 'Mois de novembre'),
    ('youtube music', 5.49, '08-nov', 2025, None),
    ('Cinepass', 13.50, '22-oct', 2025, None),
    ('Cinepass', 18.40, '06-nov', 2025, None),
    ('linge', 3.00, '16-sept', 2025, None),
    ('linge', 6.00, '05-oct', 2025, None),
    ('linge', 9.00, '15-nov', 2025, None),
    ('crous', 30.00, None, 2025, 'Mois de septembre'),
    ('cantine ISC', 20.00, None, 2025, 'Mois de septembre'),
    ('cantine ISC', 46.78, '01-oct', 2025, None),
    ('courses', 40.00, None, 2025, 'Mois de septembre'),
    ('courses', 40.00, None, 2025, 'Mois de octobre'),
    ('courses', 39.00, '08-nov', 2025, None),
    ('restaurant', 50.00, None, 2025, 'Mois de septembre'),
    ('restaurant', 27.90, '30-oct', 2025, None),
    ('restaurant', 10.00, None, 2025, 'Mois de novembre'),
    ('cadeau', 27.99, '24-oct', 2025, None),
    ('cadeau', -14.00, '24-oct', 2025, 'Remboursement'),
    ('cadeau', 5.00, '16-oct', 2025, None),
    ('cadeau', 1.00, '10-oct', 2025, None),
    ('salaire brut', 1199.69, '01-oct', 2025, None),
    ('salaire brut', 1199.69, '03-nov', 2025, None),
    ('depannage', 20.00, None, 2025, 'Mois de octobre'),
    ('APL', 168.00, None, 2025, 'Mois de septembre'),
    ('APL', 168.00, None, 2025, 'Mois de octobre'),
    ('Action logement', 100.00, '28-oct', 2025, None)
]

# On utilise INSERT OR IGNORE pour éviter les erreurs si tu relances le script
cursor.executemany('''
    INSERT OR IGNORE INTO detaillee (sous_categorie, montant, jour_mois, annee, commentaire) 
    VALUES (?, ?, ?, ?, ?)
''', depenses_data)

conn.commit()
conn.close()

print("Base de données complète avec prévisionnel 2025 créée !")