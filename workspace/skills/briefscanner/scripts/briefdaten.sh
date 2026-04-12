#!/bin/bash
# briefdaten.sh — Extrahiert Datumsangaben aus Brief-Bildern oder PDFs
# Verwendung: briefdaten.sh <bild.jpg|dokument.pdf>

set -euo pipefail

if [ $# -eq 0 ]; then
    echo "Verwendung: briefdaten.sh <bild.jpg|bild.png|dokument.pdf>"
    echo "Extrahiert alle Datumsangaben aus einem Brief."
    exit 1
fi

INPUT="$1"
if [ ! -f "$INPUT" ]; then
    echo "Fehler: Datei '$INPUT' nicht gefunden."
    exit 1
fi

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

EXT="${INPUT##*.}"
EXT_LOWER=$(echo "$EXT" | tr '[:upper:]' '[:lower:]')

echo "📄 Verarbeite: $INPUT"
echo ""

# Text extrahieren
if [ "$EXT_LOWER" = "pdf" ]; then
    # PDF: erst pdftotext, dann OCR als Fallback
    TEXT=$(pdftotext "$INPUT" - 2>/dev/null || true)
    if [ -z "$TEXT" ] || [ "$(echo "$TEXT" | wc -w)" -lt 10 ]; then
        echo "   (Gescanntes PDF erkannt — nutze OCR)"
        pdftoppm -png -r 300 "$INPUT" "$TMPDIR/page"
        TEXT=""
        for PAGE in "$TMPDIR"/page-*.png; do
            [ -f "$PAGE" ] || continue
            PAGEBASE="$TMPDIR/ocr_$(basename "$PAGE" .png)"
            tesseract "$PAGE" "$PAGEBASE" -l deu 2>/dev/null
            PAGE_TEXT=$(cat "${PAGEBASE}.txt" 2>/dev/null || true)
            TEXT="$TEXT"$'\n'"$PAGE_TEXT"
        done
    fi
else
    # Bild: auto-orient + OCR (Datei-Output ist zuverlässiger als stdout)
    convert -auto-orient "$INPUT" "$TMPDIR/oriented.png" 2>/dev/null
    tesseract "$TMPDIR/oriented.png" "$TMPDIR/ocr_result" -l deu 2>/dev/null
    TEXT=$(cat "$TMPDIR/ocr_result.txt" 2>/dev/null || true)
fi

if [ -z "$TEXT" ]; then
    echo "❌ Konnte keinen Text aus dem Dokument extrahieren."
    exit 1
fi

echo "📅 Gefundene Datumsangaben:"
echo "---"

# Datumsangaben extrahieren mit grep
# Format DD.MM.YYYY oder DD.MM.YY
DATES_DOT=$(echo "$TEXT" | grep -oP '\d{1,2}\.\s?\d{1,2}\.\s?\d{2,4}' | sort -t. -k3,3n -k2,2n -k1,1n | uniq || true)

# Format "D. Monat YYYY" (mit Jahreszahl)
DATES_TEXT=$(echo "$TEXT" | grep -oiP '\d{1,2}\.\s+(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+\d{4}' | sort | uniq || true)

# Format "D. Monat" (ohne Jahreszahl, z.B. "16. April")
DATES_TEXT_NOYEAR=$(echo "$TEXT" | grep -oiP '\d{1,2}\.\s+(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)(?!\s+\d{4})' | sort | uniq || true)

# Format YYYY-MM-DD
DATES_ISO=$(echo "$TEXT" | grep -oP '\d{4}-\d{2}-\d{2}' | sort | uniq || true)

# Fristangaben
FRISTEN=$(echo "$TEXT" | grep -oiP '(innerhalb von \d+ (Tagen|Wochen)|bis zum \d{1,2}\.\s?\d{1,2}\.\s?\d{2,4}|Frist[:\s]+\d{1,2}\.\s?\d{1,2}\.\s?\d{2,4}|Zahlungsziel[:\s]+\d{1,2}\.\s?\d{1,2}\.\s?\d{2,4}|gültig bis \d{1,2}\.\s?\d{1,2}\.\s?\d{2,4})' | sort | uniq || true)

# Kontext für jedes Datum finden
N=1
print_date_with_context() {
    local date="$1"
    local escaped_date
    escaped_date=$(echo "$date" | sed 's/[.]/\\./g')
    # Zeile mit Datum finden für Kontext
    local context
    context=$(echo "$TEXT" | grep -i "$escaped_date" | head -1 | sed 's/^[[:space:]]*//' | cut -c1-120)
    if [ -n "$context" ]; then
        echo "$N. **$date** — $context"
    else
        echo "$N. **$date**"
    fi
    N=$((N + 1))
}

FOUND=0

if [ -n "$DATES_TEXT" ]; then
    while IFS= read -r d; do
        [ -n "$d" ] && print_date_with_context "$d" && FOUND=1
    done <<< "$DATES_TEXT"
fi

if [ -n "$DATES_TEXT_NOYEAR" ]; then
    while IFS= read -r d; do
        [ -n "$d" ] && print_date_with_context "$d" && FOUND=1
    done <<< "$DATES_TEXT_NOYEAR"
fi

if [ -n "$DATES_DOT" ]; then
    while IFS= read -r d; do
        [ -n "$d" ] && print_date_with_context "$d" && FOUND=1
    done <<< "$DATES_DOT"
fi

if [ -n "$DATES_ISO" ]; then
    while IFS= read -r d; do
        [ -n "$d" ] && print_date_with_context "$d" && FOUND=1
    done <<< "$DATES_ISO"
fi

if [ -n "$FRISTEN" ]; then
    echo ""
    echo "⏰ Fristangaben:"
    while IFS= read -r f; do
        [ -n "$f" ] && echo "   • $f"
    done <<< "$FRISTEN"
fi

if [ "$FOUND" -eq 0 ] && [ -z "$FRISTEN" ]; then
    echo "   Keine Datumsangaben gefunden."
fi

echo "---"
