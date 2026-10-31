"""Baixa el GTFS dels autobusos interurbans de la Generalitat i en treu
les línies que passen pel Baix Empordà. Genera data/busos.json per al mapa.

Ús:  python scripts/gtfs_baix.py               (baixa el GTFS)
     python scripts/gtfs_baix.py fitxer.zip    (fa servir un zip local)
"""
import csv, io, json, os, re, sys, zipfile, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")

# Fonts possibles del GTFS (es proven per ordre). Es pot forçar amb GTFS_URL.
URLS = [u for u in [os.environ.get("GTFS_URL")] if u] + [
    "https://analisi.transparenciacatalunya.cat/download/bca2-b4i3/application%2Fzip",
    "https://analisi.transparenciacatalunya.cat/api/views/bca2-b4i3/files/default?download=true",
]

# Requadre del Baix Empordà (amb una mica de marge cap a Girona per veure l'entrada dels busos)
BBOX = dict(lat_min=41.74, lat_max=42.13, lon_min=2.80, lon_max=3.26)
# Requadre estricte de la comarca: una línia hi ha de tenir com a mínim 2 parades
COMARCA = dict(lat_min=41.76, lat_max=42.12, lon_min=2.89, lon_max=3.25)

DIES = 2  # avui i demà

SORTIDA = os.path.join(os.path.dirname(__file__), "..", "data", "busos.json")


def dins(lat, lon, b):
    return b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]


def baixa():
    for url in URLS:
        try:
            print("Baixant", url)
            req = urllib.request.Request(url, headers={"User-Agent": "latdg-busos/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if data[:2] == b"PK":
                return data
            print("  no és un zip, la provo de saltar")
        except Exception as e:  # noqa: BLE001
            print("  error:", e)
    sys.exit("No s'ha pogut baixar el GTFS de cap font.")


def llegeix(z, nom):
    noms = {os.path.basename(n): n for n in z.namelist()}
    if nom not in noms:
        return []
    with z.open(noms[nom]) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))


def a_min(hhmmss):
    h, m, s = (int(x) for x in hhmmss.strip().split(":"))
    return h * 60 + m + s / 60


def serveis_actius(z, dia):
    """Serveis que funcionen el dia donat (calendar + calendar_dates)."""
    nom_dia = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][dia.weekday()]
    clau = dia.strftime("%Y%m%d")
    actius = set()
    for c in llegeix(z, "calendar.txt"):
        if c["start_date"] <= clau <= c["end_date"] and c.get(nom_dia) == "1":
            actius.add(c["service_id"])
    for c in llegeix(z, "calendar_dates.txt"):
        if c["date"] == clau:
            if c["exception_type"] == "1":
                actius.add(c["service_id"])
            elif c["exception_type"] == "2":
                actius.discard(c["service_id"])
    return actius


def processa(data):
    z = zipfile.ZipFile(io.BytesIO(data))

    parades = {}
    for s in llegeix(z, "stops.txt"):
        try:
            lat, lon = float(s["stop_lat"]), float(s["stop_lon"])
        except (ValueError, KeyError):
            continue
        if dins(lat, lon, BBOX):
            parades[s["stop_id"]] = {"n": s.get("stop_name", "").strip(), "ll": [round(lat, 5), round(lon, 5)],
                                     "c": dins(lat, lon, COMARCA)}

    rutes = {r["route_id"]: r for r in llegeix(z, "routes.txt")}
    agencies = {a.get("agency_id", ""): a.get("agency_name", "") for a in llegeix(z, "agency.txt")}
    viatges = {t["trip_id"]: t for t in llegeix(z, "trips.txt")}

    # stop_times agrupats per viatge, només parades del requadre
    horaris = {}
    for st in llegeix(z, "stop_times.txt"):
        if st["stop_id"] not in parades:
            continue
        t = st.get("departure_time") or st.get("arrival_time")
        if not t:
            continue
        horaris.setdefault(st["trip_id"], []).append((int(st["stop_sequence"]), st["stop_id"], round(a_min(t), 2)))

    # viatges que toquen la comarca amb 2 o més parades
    bons = {}
    for tid, llista in horaris.items():
        llista.sort()
        if sum(1 for _, sid, _ in llista if parades[sid]["c"]) >= 2:
            bons[tid] = llista

    avui = datetime.now(TZ).date()
    dies = {}
    rutes_usades, parades_usades = set(), set()
    for d in range(DIES):
        dia = avui + timedelta(days=d)
        actius = serveis_actius(z, dia)
        llista_dia = []
        for tid, ll in bons.items():
            t = viatges.get(tid)
            if not t or t["service_id"] not in actius:
                continue
            rutes_usades.add(t["route_id"])
            parades_usades.update(sid for _, sid, _ in ll)
            llista_dia.append({"r": t["route_id"], "h": t.get("trip_headsign", "").strip(),
                               "s": [[sid, m] for _, sid, m in ll]})
        llista_dia.sort(key=lambda v: v["s"][0][1])
        dies[dia.strftime("%d.%m.%Y")] = llista_dia

    # traçats: una seqüència de parades per ruta (la més llarga)
    tracats = {}
    for tid, ll in bons.items():
        t = viatges.get(tid)
        if not t or t["route_id"] not in rutes_usades:
            continue
        seq = [sid for _, sid, _ in ll]
        if len(seq) > len(tracats.get(t["route_id"], [])):
            tracats[t["route_id"]] = seq

    sortida_rutes = {}
    for rid in sorted(rutes_usades):
        r = rutes.get(rid, {})
        color = (r.get("route_color") or "").strip()
        llarg = (r.get("route_long_name") or "").strip()
        curt = (r.get("route_short_name") or "").strip() or rid
        # codis llegibles: R1-R3 del Clic, E2/E3 dels exprés; la resta, el número sense «L0»
        m = re.match(r"\s*\(?(R\d)\s+Clic", llarg, re.I) or re.search(r"Expres\.cat\s+(E\d+)", llarg, re.I)
        if m:
            codi = m.group(1).upper()
        else:
            codi = re.sub(r"^L0*", "", curt) or curt
        sortida_rutes[rid] = {
            "c": codi,
            "dem": bool(re.search(r"clic\.cat", llarg, re.I)),
            "n": (r.get("route_long_name") or "").strip(),
            "op": agencies.get(r.get("agency_id", ""), "") or next(iter(agencies.values()), ""),
            "col": "#" + color if len(color) == 6 else "",
            "t": [parades[s]["ll"] for s in tracats.get(rid, [])],
        }

    return {
        "generat": datetime.now(TZ).strftime("%d.%m.%Y %H.%M"),
        "font": "Generalitat de Catalunya · xarxa d'autobusos interurbans (GTFS)",
        "parades": {sid: {"n": parades[sid]["n"], "ll": parades[sid]["ll"]} for sid in sorted(parades_usades)},
        "rutes": sortida_rutes,
        "dies": dies,
    }


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], "rb") as f:
            data = f.read()
    else:
        data = baixa()
    res = processa(data)
    os.makedirs(os.path.dirname(SORTIDA), exist_ok=True)
    with open(SORTIDA, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, separators=(",", ":"))
    n = {k: len(v) for k, v in res["dies"].items()}
    print(f"Fet: {len(res['rutes'])} línies, {len(res['parades'])} parades, viatges per dia {n}")


if __name__ == "__main__":
    main()
