---
name: briefscanner
description: "Briefscanner: Extrahiert Datumsangaben und Fristen aus Brief-Fotos/PDFs via OCR. Nutzbar via exec tool (WhatsApp-Bilder, CLI) und als Mail-Agent (systemd)."
---

# Briefscanner

Extrahiert Datumsangaben, Fristen und Zahlungsziele aus Brief-Fotos und PDFs via OCR (tesseract).

## Verwendung via exec tool

Wenn du ein Bild oder PDF eines Briefes erhältst (z.B. via WhatsApp), nutze den `exec` tool:

```bash
~/.openclaw/workspace/skills/briefscanner/scripts/briefdaten.sh <pfad-zum-bild>
```

**Wann dieses Script verwenden:**
- Ein Bild kommt rein (`<media:image>`) → **SOFORT** briefdaten.sh mit dem mediaPath aufrufen, OHNE vorher das Vision/image-Tool zu nutzen
- Der User schickt ein Foto eines Briefes und fragt nach Daten, Terminen oder Fristen
- Der User schreibt "briefdaten", "termine", "fristen" oder "scan" zusammen mit einem Bild
- Der User fragt "Was steht in dem Brief?" und hat ein Bild angehängt

**WICHTIG:** Nutze NICHT das `image`-Tool (Vision-Modell) für Briefbilder. briefdaten.sh macht OCR direkt und ist schneller.

## Mail-Agent (automatisch, systemd)

Der Mail-Agent überwacht zusätzlich das GMX-Postfach (`mink.m@gmx.de`) und verarbeitet eingehende E-Mails mit Betreff-Keywords automatisch.

```bash
systemctl status openclaw-briefscanner
journalctl -u openclaw-briefscanner -f
```

## Komponenten

- **briefdaten.sh** — OCR-Kernscript (tesseract + Datumsextraktion)
- **mail_agent.py** — E-Mail-Eingangskanal (IMAP-Polling, systemd-Service)
- **mail_agent.env** — Credentials
