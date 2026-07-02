#!/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
OPENCLAW_DIR="$HOME/.openclaw"
AGENT_DIR="$OPENCLAW_DIR/agents/main/agent"

echo "=== Hans Setup ==="
echo "Repo:     $REPO_DIR"
echo "OpenClaw: $OPENCLAW_DIR"
echo ""

# 1. Prüfe ob openclaw installiert ist
if ! command -v openclaw &>/dev/null && [[ ! -x /opt/nodejs/bin/openclaw ]]; then
    echo "FEHLER: openclaw nicht gefunden. Bitte zuerst installieren:"
    echo "  npm install -g openclaw"
    exit 1
fi
echo "[✓] openclaw gefunden"

# 2. Prüfe ob secrets.env existiert
if [[ ! -f "$REPO_DIR/secrets.env" ]]; then
    echo "FEHLER: secrets.env nicht gefunden."
    echo "  Kopiere .env.example nach secrets.env und trage deine Keys ein:"
    echo "  cp $REPO_DIR/.env.example $REPO_DIR/secrets.env"
    exit 1
fi
echo "[✓] secrets.env vorhanden"

# 3. OpenClaw State-Verzeichnis anlegen
mkdir -p "$OPENCLAW_DIR"
mkdir -p "$AGENT_DIR"
echo "[✓] OpenClaw-Verzeichnisse angelegt"

# 4. openclaw.json kopieren (Gateway-Token einsetzen)
if [[ -f "$OPENCLAW_DIR/openclaw.json" ]]; then
    echo "    openclaw.json existiert bereits — überschreiben? (j/N)"
    read -r answer
    if [[ "$answer" != "j" && "$answer" != "J" ]]; then
        echo "    → übersprungen"
    else
        # Bestehenden Gateway-Token beibehalten falls vorhanden
        EXISTING_TOKEN=$(python3 -c "
import json
with open('$OPENCLAW_DIR/openclaw.json') as f:
    c = json.load(f)
print(c.get('gateway',{}).get('auth',{}).get('token',''))
" 2>/dev/null || true)
        cp "$REPO_DIR/openclaw.json" "$OPENCLAW_DIR/openclaw.json"
        if [[ -n "$EXISTING_TOKEN" && "$EXISTING_TOKEN" != "REPLACE_WITH_YOUR_GATEWAY_TOKEN" ]]; then
            python3 -c "
import json
with open('$OPENCLAW_DIR/openclaw.json', 'r+') as f:
    c = json.load(f)
    c['gateway']['auth']['token'] = '$EXISTING_TOKEN'
    f.seek(0); json.dump(c, f, indent=2); f.truncate()
"
            echo "    → openclaw.json kopiert (Gateway-Token beibehalten)"
        else
            echo "    → openclaw.json kopiert"
            echo "    HINWEIS: Gateway-Token muss noch gesetzt werden:"
            echo "      openclaw config set gateway.auth.token <dein-token>"
        fi
    fi
else
    cp "$REPO_DIR/openclaw.json" "$OPENCLAW_DIR/openclaw.json"
    echo "    → openclaw.json kopiert"
    echo "    HINWEIS: Gateway-Token muss noch gesetzt werden:"
    echo "      openclaw config set gateway.auth.token <dein-token>"
fi

# 5. Agent-Config kopieren (models.json + auth-profiles.json)
cp "$REPO_DIR/agent/models.json" "$AGENT_DIR/models.json"
cp "$REPO_DIR/agent/auth-profiles.json" "$AGENT_DIR/auth-profiles.json"
echo "[✓] Agent-Config kopiert"

# 6. secrets.env → ~/.openclaw/.env
cp "$REPO_DIR/secrets.env" "$OPENCLAW_DIR/.env"
echo "[✓] Secrets nach $OPENCLAW_DIR/.env kopiert"

# 7. Workspace verlinken
if [[ -L "$OPENCLAW_DIR/workspace" ]]; then
    CURRENT_TARGET=$(readlink "$OPENCLAW_DIR/workspace")
    if [[ "$CURRENT_TARGET" == "$REPO_DIR/workspace" ]]; then
        echo "[✓] Workspace-Symlink bereits korrekt"
    else
        rm "$OPENCLAW_DIR/workspace"
        ln -s "$REPO_DIR/workspace" "$OPENCLAW_DIR/workspace"
        echo "[✓] Workspace-Symlink aktualisiert (war: $CURRENT_TARGET)"
    fi
elif [[ -d "$OPENCLAW_DIR/workspace" ]]; then
    echo "    $OPENCLAW_DIR/workspace ist ein Verzeichnis — als Backup verschieben? (j/N)"
    read -r answer
    if [[ "$answer" == "j" || "$answer" == "J" ]]; then
        mv "$OPENCLAW_DIR/workspace" "$OPENCLAW_DIR/workspace.bak.$(date +%Y%m%d%H%M%S)"
        ln -s "$REPO_DIR/workspace" "$OPENCLAW_DIR/workspace"
        echo "[✓] Workspace-Symlink erstellt (altes Verzeichnis gesichert)"
    else
        echo "    → übersprungen (Workspace nicht verlinkt!)"
    fi
else
    ln -s "$REPO_DIR/workspace" "$OPENCLAW_DIR/workspace"
    echo "[✓] Workspace-Symlink erstellt"
fi

# 8. Ollama prüfen
echo ""
if curl -s http://127.0.0.1:11434/api/version &>/dev/null; then
    echo "[✓] Ollama läuft"
else
    echo "[!] Ollama nicht erreichbar (http://127.0.0.1:11434)"
    echo "    Starte Ollama: ollama serve"
fi

echo ""
echo "=== Setup abgeschlossen ==="
echo ""
echo "Hans starten:"
echo "  openclaw daemon start"
echo ""
echo "Hans testen:"
echo "  openclaw agent --local -m 'Hallo Hans!'"
