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

# --- Regex ultra-tolérante avec groupes nommés ---
# Gère les espaces des milliers, les signes +/-, et les inversions d'affichage HTML
pattern = re.compile(
    r'(?P<libelle>[^.\n]{3,60}?)\s+'
    r'(?P<date>\d{1,2}(?:er)?\s+[a-zA-Zà-ÿÀ-Ÿû]+\s+\d{4})\s+'
    r'(?P<montant>[+-]?[\d\s\xa0]+[,.]\d{2})\s?€',
    re.IGNORECASE
)
# Cas alternatif si la banque place le montant avant la date dans le code HTML
pattern_alt = re.compile(
    r'(?P<libelle>[^.\n]{3,60}?)\s+'
    r'(?P<montant>[+-]?[\d\s\xa0]+[,.]\d{2})\s?€\s+'
    r'(?P<date>\d{1,2}(?:er)?\s+[a-zA-Zà-ÿÀ-Ÿû]+\s+\d{4})',
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
                # SECRET DE PARSING : Forcer un saut de ligne entre les balises pour éviter que les mots se collent
                text = soup.get_text(separator='\n', strip=True)
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
        body = get_body(msg)

        # SECURITE : On vérifie l'existence du mot-clé dans l'objet OU dans le corps du mail
        if "alerte" not in subject.lower() and "Opération liée à l'alerte" not in body:
            continue
        
        # On tente l'extraction dans les deux sens de lecture possibles
        match = pattern.search(body) or pattern_alt.search(body)
        
        if match:
            libelle = match.group('libelle').strip()
            date_str = match.group('date')
            
            # Nettoyage robuste du montant (suppression des espaces des milliers et insécables)
            montant_str = match.group('montant').replace(' ', '').replace('\xa0', '').replace(',', '.')
            montant = float(montant_str)
            
            # RÉCUPÉRATION DU MESSAGE-ID UNIQUE
            msg_id = msg.get("Message-ID")
            
            try:
                date_clean = date_str.replace('er ', ' ')
                parts = date_clean.split()
                jour_mois = f"{parts[0]}-{parts[1][:4]}"
                annee = int(parts[2])
            except:
                jour_mois = date_str
                annee = datetime.now().year

            transactions_a_inserer.append(('À classer', montant, jour_mois, annee, libelle, msg_id))

# --- Insertion sécurisée dans la DB ---
if transactions_a_inserer:
    cursor.executemany('''
        INSERT OR IGNORE INTO detaillee (sous_categorie, montant, jour_mois, annee, commentaire, id_message) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', transactions_a_inserer)
    
    conn.commit()
    print(f" {cursor.rowcount} NOUVELLES transactions insérées dans banqueMe.db !")
else:
    print(" Aucune nouvelle transaction trouvée.")

conn.close()