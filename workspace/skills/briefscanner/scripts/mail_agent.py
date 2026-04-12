#!/usr/bin/env python3
"""
OpenClaw Briefdaten Mail-Agent
Überwacht ein GMX-Postfach per IMAP, extrahiert Datumsangaben aus
Bild-/PDF-Anhängen und sendet die Ergebnisse als Antwort-Mail zurück.

Verwendung:
    python3 mail_agent.py

Konfiguration via Umgebungsvariablen:
    MAIL_USER       — E-Mail-Adresse (z.B. mink.m@gmx.de)
    MAIL_PASSWORD   — Passwort oder App-Passwort
    MAIL_IMAP_HOST  — IMAP-Server (default: imap.gmx.net)
    MAIL_SMTP_HOST  — SMTP-Server (default: mail.gmx.net)
    POLL_INTERVAL   — Abfrageintervall in Sekunden (default: 60)
"""

import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import os
import sys
import tempfile
import subprocess
import time
import signal
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [mail-agent] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mail-agent")

# --- Config ---
MAIL_USER = os.environ.get("MAIL_USER", "mink.m@gmx.de")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
IMAP_HOST = os.environ.get("MAIL_IMAP_HOST", "imap.gmx.net")
IMAP_PORT = int(os.environ.get("MAIL_IMAP_PORT", "993"))
SMTP_HOST = os.environ.get("MAIL_SMTP_HOST", "mail.gmx.net")
SMTP_PORT = int(os.environ.get("MAIL_SMTP_PORT", "587"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "60"))
BRIEFDATEN_SCRIPT = os.path.expanduser("~/.openclaw/workspace/skills/briefscanner/scripts/briefdaten.sh")
SUBJECT_KEYWORDS = ["briefdaten", "termine", "fristen", "datumsangaben"]

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".pdf"}

running = True


def signal_handler(_sig, _frame):
    global running
    log.info("Beende...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def decode_subject(msg):
    """Decode email subject header."""
    raw = msg.get("Subject", "")
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def get_sender(msg):
    """Extract sender email address."""
    raw = msg.get("From", "")
    # Handle "Name <email>" format
    if "<" in raw and ">" in raw:
        return raw[raw.index("<") + 1 : raw.index(">")]
    return raw


def extract_attachments(msg):
    """Extract supported file attachments, return list of (filename, bytes)."""
    attachments = []
    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        if "attachment" not in content_disposition and "inline" not in content_disposition:
            continue

        filename = part.get_filename()
        if not filename:
            continue

        # Decode filename if needed
        decoded_parts = decode_header(filename)
        decoded_name = ""
        for fpart, charset in decoded_parts:
            if isinstance(fpart, bytes):
                decoded_name += fpart.decode(charset or "utf-8", errors="replace")
            else:
                decoded_name += fpart
        filename = decoded_name

        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue

        data = part.get_payload(decode=True)
        if data:
            attachments.append((filename, data))

    return attachments


def run_briefdaten(filepath):
    """Run the briefdaten.sh script on a file and return the output."""
    try:
        result = subprocess.run(
            [BRIEFDATEN_SCRIPT, filepath],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.stdout or result.stderr or "Keine Ausgabe."
    except subprocess.TimeoutExpired:
        return "Fehler: Zeitüberschreitung bei der Verarbeitung."
    except Exception as e:
        return f"Fehler: {e}"


def send_reply(sender, subject, message_id, results_text):
    """Send a reply email with the extracted dates."""
    reply = MIMEMultipart()
    reply["From"] = MAIL_USER
    reply["To"] = sender
    reply["Subject"] = f"Re: {subject}"
    if message_id:
        reply["In-Reply-To"] = message_id
        reply["References"] = message_id

    body = f"""Hallo,

hier sind die extrahierten Datumsangaben aus deinem Brief:

{results_text}

---
Gesendet von OpenClaw Briefdaten-Agent 🦞
"""
    reply.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(MAIL_USER, MAIL_PASSWORD)
            server.send_message(reply)
        log.info(f"Antwort gesendet an {sender}")
        return True
    except Exception as e:
        log.error(f"Fehler beim Senden: {e}")
        return False


def process_email(mail_conn, email_id):
    """Process a single email: extract attachments, run briefdaten, reply."""
    _, data = mail_conn.fetch(email_id, "(RFC822)")
    raw_email = data[0][1]
    msg = email.message_from_bytes(raw_email)

    subject = decode_subject(msg)
    sender = get_sender(msg)
    message_id = msg.get("Message-ID", "")

    log.info(f"Neue Mail von {sender}: {subject}")

    attachments = extract_attachments(msg)
    if not attachments:
        log.info("  Keine unterstützten Anhänge gefunden, überspringe.")
        # Mark as seen anyway
        mail_conn.store(email_id, "+FLAGS", "\\Seen")
        return

    all_results = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for filename, data in attachments:
            filepath = os.path.join(tmpdir, filename)
            with open(filepath, "wb") as f:
                f.write(data)

            log.info(f"  Verarbeite: {filename}")
            result = run_briefdaten(filepath)
            all_results.append(f"=== {filename} ===\n{result}")

    results_text = "\n\n".join(all_results)

    if send_reply(sender, subject, message_id, results_text):
        mail_conn.store(email_id, "+FLAGS", "\\Seen")
        log.info("  Fertig, als gelesen markiert.")
    else:
        log.warning("  Antwort konnte nicht gesendet werden.")


def check_inbox():
    """Connect to IMAP, check for unread emails with the keyword."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=30)
        mail.login(MAIL_USER, MAIL_PASSWORD)
        mail.select("INBOX")

        # Search for unread emails with subject containing any keyword
        search_criteria = " ".join(
            [f'OR SUBJECT "{kw}"' for kw in SUBJECT_KEYWORDS[1:]]
        )
        # IMAP OR chains: (OR (OR a b) c) ...
        # Simpler: search UNSEEN, then filter subject in Python
        _, message_ids = mail.search(None, "(UNSEEN)")

        ids = message_ids[0].split()
        if not ids:
            mail.logout()
            return

        for email_id in ids:
            try:
                _, data = mail.fetch(email_id, "(BODY.PEEK[HEADER.FIELDS (SUBJECT)])")
                header = data[0][1].decode("utf-8", errors="replace").lower()
                if any(kw in header for kw in SUBJECT_KEYWORDS):
                    log.info(f"Treffer gefunden (Mail-ID {email_id.decode()})")
                    process_email(mail, email_id)
                # else: skip, leave as unread
            except Exception as e:
                log.error(f"Fehler bei Mail {email_id}: {e}")

        mail.logout()
    except imaplib.IMAP4.error as e:
        log.error(f"IMAP-Fehler: {e}")
    except Exception as e:
        log.error(f"Verbindungsfehler: {e}")


def main():
    if not MAIL_PASSWORD:
        print("Fehler: MAIL_PASSWORD nicht gesetzt.")
        print("Verwendung: MAIL_PASSWORD='dein-passwort' python3 mail_agent.py")
        sys.exit(1)

    if not os.path.isfile(BRIEFDATEN_SCRIPT):
        print(f"Fehler: {BRIEFDATEN_SCRIPT} nicht gefunden.")
        sys.exit(1)

    log.info(f"📬 Mail-Agent gestartet für {MAIL_USER}")
    log.info(f"   Suche nach Betreff mit: {', '.join(SUBJECT_KEYWORDS)}")
    log.info(f"   Prüfintervall: {POLL_INTERVAL}s")
    log.info(f"   IMAP: {IMAP_HOST}:{IMAP_PORT}")
    log.info(f"   SMTP: {SMTP_HOST}:{SMTP_PORT}")

    while running:
        check_inbox()
        for _ in range(POLL_INTERVAL):
            if not running:
                break
            time.sleep(1)

    log.info("Mail-Agent beendet.")


if __name__ == "__main__":
    main()
