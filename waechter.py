"""Prüft den JYSK-Bestand des Sessels REMMELS und schickt eine ntfy-Push, sobald er verfügbar ist.

Umgebungsvariablen:
  NTFY_TOPIC  ntfy-Thema (geheim halten, wer es kennt, kann mitlesen)
  STATE_FILE  Datei für den letzten Zustand (Standard: zustand.json)
  TEST_PUSH   wenn "1": schickt eine Testnachricht und beendet sich
"""

import json
import os
import sys
import urllib.request

ARTIKEL = "3650325"
SALES_ORG = "1023"
PRODUKT_URL = "https://jysk.de/wohnzimmer/sessel/sessel-remmels-zebra-stoff-chrom"
API = "https://jysk.de/websapapi/api/v2/atp"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


def hole(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def bestand():
    online = hole(f"{API}/onlineWithStoreStatus/{SALES_ORG}?articleIds={ARTIKEL}&atpType=BOTH")[ARTIKEL]
    online_menge = online["onlineAtp"]["dcAtp"]["quantity"]
    naechste = online["onlineAtp"].get("nextAtp") or []

    filialen = hole(f"{API}/stores/{SALES_ORG}/{ARTIKEL}?includeNegative=1")
    mit_bestand = {sid: f["storeAtp"]["quantity"] for sid, f in filialen.items() if f["storeAtp"]["quantity"] > 0}

    return {"online": online_menge, "nachschub": naechste, "filialen": mit_bestand}


def push(titel, text, prio="urgent"):
    topic = os.environ["NTFY_TOPIC"]
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=text.encode(),
        headers={"Title": titel, "Priority": prio, "Click": PRODUKT_URL, "Tags": "couch_and_lamp"},
    )
    urllib.request.urlopen(req, timeout=30)


def main():
    if os.environ.get("TEST_PUSH") == "1":
        push("Sessel-Wächter läuft", "Testnachricht: Benachrichtigungen kommen an.", prio="default")
        return

    state_file = os.environ.get("STATE_FILE", "zustand.json")
    try:
        with open(state_file) as f:
            vorher = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        vorher = {"online": 0, "filialen": {}, "nachschub": []}

    jetzt = bestand()
    print(json.dumps(jetzt, ensure_ascii=False))

    meldungen = []
    if jetzt["online"] > 0 and vorher["online"] <= 0:
        meldungen.append(f"ONLINE bestellbar: {jetzt['online']} Stück")
    neue_filialen = set(jetzt["filialen"]) - set(vorher["filialen"])
    if neue_filialen:
        meldungen.append(f"In {len(neue_filialen)} Filiale(n) neu vorrätig (Filial-Nr. {', '.join(sorted(neue_filialen))})")
    if jetzt["nachschub"] and not vorher.get("nachschub"):
        meldungen.append(f"Nachschub angekündigt: {json.dumps(jetzt['nachschub'], ensure_ascii=False)}")

    if meldungen:
        push("Sessel REMMELS verfügbar!", "\n".join(meldungen) + "\nTippen öffnet die Produktseite.")
        print("Push gesendet:", meldungen)

    with open(state_file, "w") as f:
        json.dump(jetzt, f)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Fehler:", e, file=sys.stderr)
        sys.exit(1)
