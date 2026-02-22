import imaplib
import email
import os
import re
import sqlite3
from email.header import decode_header
from bs4 import BeautifulSoup
from datetime import datetime

# --- Variables d'environnement ---
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
if not EMAIL_ACCOUNT or not EMAIL_PASSWORD:
    raise RuntimeError("Variables d'environnement EMAIL_ACCOUNT ou EMAIL_PASSWORD non définies")

# --- Connexion IMAP ---
mail = imaplib.IMAP4_SSL("imap.gmail.com")
mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
status, _ = mail.select("banque")
status, messages = mail.search(None, 'ALL')
messages = messages[0].split()
print(f"{len(messages)} mails trouvés dans le label 'banque'")

# --- Regex libellé/date/montant ---
pattern = re.compile(
    r'(.+?)\s*(\d{1,2} [a-zéû]+ \d{4})\s*([+-]?\d+[,.]\d{2})\s?€',
    re.IGNORECASE
)

# --- Fonctions utilitaires ---
def get_body(msg):
    body = ""
    for part in msg.walk():
        if part.get_content_maintype() == "multipart": continue
        if part.get("Content-Disposition") and "attachment" in part.get("Content-Disposition"): continue
        try:
            payload = part.get_payload(decode=True)
            if not payload: continue
            charset = part.get_content_charset() or 'utf-8'
            text = payload.decode(charset, errors="ignore")
            if part.get_content_type() == "text/html":
                soup = BeautifulSoup(text, "html.parser")
                text = soup.get_text()
            body += text + "\n"
        except: continue
    return body.strip()

def get_subject(msg):
    subject, encoding = decode_header(msg['Subject'])[0]
    if isinstance(subject, bytes):
        subject = subject.decode(encoding or 'utf-8', errors='ignore')
    return subject

# =========================================================
# BASE DE DONNÉES
# =========================================================
conn = sqlite3.connect('banqueMe.db')
cursor = conn.cursor()

# On s'assure que la catégorie par défaut existe
cursor.execute('''INSERT OR IGNORE INTO categorie (nom_categorie, sous_categorie) VALUES ('À classer', 'À classer')''')

transactions_a_inserer = []

# --- Parcours des mails ---
if messages:
    status, data = mail.fetch(b','.join(messages), '(RFC822)')
    
    for i in range(0, len(data), 2):
        if len(data[i]) < 2: continue
        msg = email.message_from_bytes(data[i][1])
        subject = get_subject(msg)

        if "Opération liée à l'alerte" not in subject:
            continue

        body = get_body(msg)
        match = pattern.search(body)
        
        if match:
            libelle = match.group(1).strip()
            date_str = match.group(2)
            montant = float(match.group(3).replace(',', '.'))
            
            # RÉCUPÉRATION DU MESSAGE-ID UNIQUE
            msg_id = msg.get("Message-ID")
            
            try:
                parts = date_str.split()
                jour_mois = f"{parts[0]}-{parts[1][:4]}"
                annee = int(parts[2])
            except:
                jour_mois = date_str
                annee = datetime.now().year

            # On ajoute le msg_id à la fin du tuple
            transactions_a_inserer.append(('A classer', montant, jour_mois, annee, libelle, msg_id))

# --- Insertion sécurisée dans la DB ---
if transactions_a_inserer:
    # L'utilisation de INSERT OR IGNORE est la clé : 
    # Si le msg_id existe déjà, SQLite passe à la ligne suivante sans faire d'erreur
    cursor.executemany('''
        INSERT OR IGNORE INTO detaillee (sous_categorie, montant, jour_mois, annee, commentaire, id_message) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', transactions_a_inserer)
    
    conn.commit()
    # rowcount permet de savoir combien de lignes ont RÉELLEMENT été ajoutées (en ignorant les doublons)
    print(f" {cursor.rowcount} NOUVELLES transactions insérées dans banqueMe.db !")
else:
    print(" Aucune transaction trouvée.")

conn.close()