"""Baixa el GTFS dels autobusos interurbans de la Generalitat i en treu
les línies que passen pel Baix Empordà. Genera data/busos.json per al mapa.

Ús:  python scripts/gtfs_baix.py               (baixa el GTFS)
     python scripts/gtfs_baix.py fitxer.zip    (fa servir un zip local)
"""
import csv, io, json, math, os, re, sys, time, zipfile, urllib.request
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

# 05.11.2026: traçat per la carretera. Cada tram entre dues parades seguides es desa a
# data/trams.json («parada>parada»: [[lat, lon], …]). Surt del shapes.txt del GTFS si en porta;
# si no, d'OSRM (carreteres d'OpenStreetMap). Els trams ja calculats no es tornen a demanar.
TRAMS = os.path.join(os.path.dirname(__file__), "..", "data", "trams.json")
OSRM = os.environ.get("OSRM_URL", "https://router.project-osrm.org").rstrip("/")

# Municipis (el mateix fitxer que fa servir el mapa dels llamps del tauler)
MUNICIPIS_URL = os.environ.get("MUNICIPIS_URL",
                               "https://raw.githubusercontent.com/latdg/tauler/main/llamps/girona.json")


def dins(lat, lon, b):
    return b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]


# 13.11.2026: còpia de l'últim GTFS bo (el workflow la guarda a la memòria cau d'Actions).
# Si el portal de la Generalitat falla, es fa servir aquesta còpia i el mapa no queda buit.
COPIA = os.environ.get("GTFS_COPIA", os.path.join(os.path.dirname(__file__), "..", ".gtfs", "gtfs.zip"))


def baixa():
    for intent in range(3):
        if intent:
            print(f"Torno a provar d'aquí a 30 s (intent {intent + 1} de 3)")
            time.sleep(30)
        for url in URLS:
            try:
                print("Baixant", url)
                req = urllib.request.Request(url, headers={"User-Agent": "latdg-busos/1.0"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = r.read()
                if data[:2] == b"PK":
                    os.makedirs(os.path.dirname(COPIA), exist_ok=True)
                    with open(COPIA, "wb") as f:
                        f.write(data)
                    return data
                print("  no és un zip, la provo de saltar")
            except Exception as e:  # noqa: BLE001
                print("  error:", e)
    if os.path.isfile(COPIA) and os.path.getsize(COPIA) > 0:
        print("::warning::No s'ha pogut baixar el GTFS: faig servir l'última còpia bona.")
        with open(COPIA, "rb") as f:
            return f.read()
    sys.exit("No s'ha pogut baixar el GTFS de cap font i no hi ha cap còpia anterior.")


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


def article(nom):
    """«La Bisbal d'Empordà» -> «la Bisbal d'Empordà», «L'Escala» -> «l'Escala»."""
    return re.sub(r"^(La|El|Els|Les|L')(?=[ ']|\b)", lambda m: m.group(1).lower(), nom)


def carrega_municipis():
    """Polígons dels municipis de la demarcació de Girona (TopoJSON) per saber de quin poble és cada parada."""
    try:
        if os.path.exists(MUNICIPIS_URL):
            with open(MUNICIPIS_URL, encoding="utf-8") as f:
                topo = json.load(f)
        else:
            req = urllib.request.Request(MUNICIPIS_URL, headers={"User-Agent": "latdg-busos/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                topo = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print("Sense municipis:", e)
        return []
    tr = topo.get("transform")
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        punts = []
        for p in arc:
            if tr:
                x, y = x + p[0], y + p[1]
                punts.append((x * tr["scale"][0] + tr["translate"][0], y * tr["scale"][1] + tr["translate"][1]))
            else:
                punts.append((p[0], p[1]))
        arcs.append(punts)

    def anell(idx):
        pts = []
        for i in idx:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            pts.extend(a if not pts else a[1:])
        return pts

    sortida = []
    for g in topo["objects"]["municipis"]["geometries"]:
        polis = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]] if g["type"] == "Polygon" else []
        anells = [anell(r) for poli in polis for r in poli]
        if not anells:
            continue
        xs = [p[0] for a in anells for p in a]
        ys = [p[1] for a in anells for p in a]
        sortida.append({"n": article(g.get("properties", {}).get("n", "")), "caixa": (min(xs), min(ys), max(xs), max(ys)),
                        "anells": anells})
    return sortida


def municipi(muns, lat, lon):
    for m in muns:
        x0, y0, x1, y1 = m["caixa"]
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        dins_ = False
        for a in m["anells"]:            # parell-senar: els forats també compten bé
            j = len(a) - 1
            for i in range(len(a)):
                xi, yi = a[i]
                xj, yj = a[j]
                if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                    dins_ = not dins_
                j = i
        if dins_:
            return m["n"]
    return ""


def dist(a, b):
    """Metres entre dos punts [lat, lon]."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def simplifica(pts, tol=8.0):
    """Douglas-Peucker (tolerància en metres, aproximada); conserva el primer i l'últim punt."""
    if len(pts) < 3:
        return pts
    k = math.cos(math.radians(pts[0][0]))

    def xy(p):
        return (p[1] * 111320 * k, p[0] * 110540)

    P = [xy(p) for p in pts]
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    pila = [(0, len(pts) - 1)]
    while pila:
        i, j = pila.pop()
        (x1, y1), (x2, y2) = P[i], P[j]
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        best, bi = 0.0, -1
        for m in range(i + 1, j):
            x, y = P[m]
            if L2 == 0:
                d = math.hypot(x - x1, y - y1)
            else:
                t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / L2))
                d = math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))
            if d > best:
                best, bi = d, m
        if best > tol:
            keep[bi] = True
            pila += [(i, bi), (bi, j)]
    return [p for p, k_ in zip(pts, keep) if k_]


def arrodoneix(pts):
    return [[round(p[0], 5), round(p[1], 5)] for p in pts]


def raonable(tram, a, b):
    """Descarta trams estranys (voltes enormes): si és més de 3 vegades la recta + 1,5 km, recta."""
    llarg = sum(dist(tram[i], tram[i + 1]) for i in range(len(tram) - 1))
    return llarg <= 3 * dist(a, b) + 1500


def trams_shapes(z, viatges, bons, totes, falten):
    """Talla el shapes.txt del GTFS (si n'hi ha) en trams entre parades seguides."""
    shapes = {}
    for p in llegeix(z, "shapes.txt"):
        try:
            shapes.setdefault(p["shape_id"], []).append(
                (int(p["shape_pt_sequence"]), float(p["shape_pt_lat"]), float(p["shape_pt_lon"])))
        except (ValueError, KeyError):
            continue
    if not shapes:
        print("El GTFS no porta shapes.txt: els trams nous es demanen a OSRM")
        return {}
    for v in shapes.values():
        v.sort()
    print(f"shapes.txt: {len(shapes)} traçats")
    nous = {}
    for tid, ll in bons.items():
        sh = shapes.get((viatges.get(tid) or {}).get("shape_id", ""))
        sids = [sid for _, sid, _ in ll]
        claus = [f"{a}>{b}" for a, b in zip(sids, sids[1:])]
        if not sh or not any(k in falten and k not in nous for k in claus):
            continue
        pts = [[la, lo] for _, la, lo in sh]
        idx, cur = [], 0
        for sid in sids:            # cada parada, al punt més proper del traçat, sempre endavant
            p = totes[sid][1:]
            best, bi = None, cur
            for i in range(cur, len(pts)):
                d = dist(p, pts[i])
                if best is None or d < best:
                    best, bi = d, i
                elif d > best + 2000:   # ja ens n'allunyem: el mínim local és aquest
                    break
            idx.append(bi if best is not None and best < 300 else None)
            if best is not None and best < 300:
                cur = bi
        for k, (a, b) in enumerate(zip(sids, sids[1:])):
            i, j = idx[k], idx[k + 1]
            if i is None or j is None or j <= i:
                continue
            tram = [list(totes[a][1:])] + pts[i:j + 1] + [list(totes[b][1:])]
            if raonable(tram, totes[a][1:], totes[b][1:]):
                nous[f"{a}>{b}"] = arrodoneix(simplifica(tram))
    return nous


def trams_osrm(seqs, totes, falten):
    """Demana a OSRM el recorregut per carretera de cada seqüència de parades a la qual falti algun tram."""
    nous, demanades, errors = {}, 0, 0
    for sids in seqs:
        claus = [f"{a}>{b}" for a, b in zip(sids, sids[1:])]
        if not any(k in falten and k not in nous for k in claus):
            continue
        if errors >= 5:
            print("OSRM falla massa: la resta de trams queden en línia recta fins a la propera vegada")
            break
        coords = ";".join(f"{totes[s][2]:.6f},{totes[s][1]:.6f}" for s in sids)
        url = f"{OSRM}/route/v1/driving/{coords}?overview=false&steps=true&geometries=geojson"
        try:
            time.sleep(1.1)   # política del servidor públic: com a molt una petició per segon
            req = urllib.request.Request(url, headers={"User-Agent": "latdg-busos/1.0 (github.com/latdg/busos)"})
            with urllib.request.urlopen(req, timeout=60) as r:
                res = json.loads(r.read().decode("utf-8"))
            demanades += 1
            legs = res["routes"][0]["legs"] if res.get("code") == "Ok" else []
        except Exception as e:  # noqa: BLE001
            errors += 1
            print("  OSRM error:", e)
            continue
        for k, leg in enumerate(legs):
            a, b = sids[k], sids[k + 1]
            pts = []
            for st in leg.get("steps", []):
                for lo, la in st.get("geometry", {}).get("coordinates", []):
                    if not pts or pts[-1] != [la, lo]:
                        pts.append([la, lo])
            if len(pts) < 2:
                continue
            tram = [list(totes[a][1:])] + pts + [list(totes[b][1:])]
            if raonable(tram, totes[a][1:], totes[b][1:]):
                nous[f"{a}>{b}"] = arrodoneix(simplifica(tram))
            else:
                nous[f"{a}>{b}"] = arrodoneix([totes[a][1:], totes[b][1:]])
    print(f"OSRM: {demanades} peticions, {len(nous)} trams nous")
    return nous


def processa(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    muns = carrega_municipis()

    parades, totes = {}, {}
    for s in llegeix(z, "stops.txt"):
        try:
            lat, lon = float(s["stop_lat"]), float(s["stop_lon"])
        except (ValueError, KeyError):
            continue
        totes[s["stop_id"]] = (s.get("stop_name", "").strip(), lat, lon)
        if dins(lat, lon, BBOX):
            parades[s["stop_id"]] = {"n": s.get("stop_name", "").strip(), "ll": [round(lat, 5), round(lon, 5)],
                                     "c": dins(lat, lon, COMARCA)}

    rutes = {r["route_id"]: r for r in llegeix(z, "routes.txt")}
    agencies = {a.get("agency_id", ""): a.get("agency_name", "") for a in llegeix(z, "agency.txt")}
    viatges = {t["trip_id"]: t for t in llegeix(z, "trips.txt")}

    # stop_times agrupats per viatge, només parades del requadre
    horaris = {}
    extrems = {}   # trip -> [seq, parada, hora] de la primera i de l'última parada de TOT el viatge
    for st in llegeix(z, "stop_times.txt"):
        t = st.get("departure_time") or st.get("arrival_time")
        if not t:
            continue
        seq = int(st["stop_sequence"])
        e = extrems.get(st["trip_id"])
        if e is None:
            extrems[st["trip_id"]] = [[seq, st["stop_id"], t], [seq, st["stop_id"], t]]
        else:
            if seq < e[0][0]:
                e[0] = [seq, st["stop_id"], t]
            if seq > e[1][0]:
                e[1] = [seq, st["stop_id"], t]
        if st["stop_id"] not in parades:
            continue
        horaris.setdefault(st["trip_id"], []).append((int(st["stop_sequence"]), st["stop_id"], round(a_min(t), 2)))

    # viatges que toquen la comarca amb 2 o més parades
    bons = {}
    for tid, llista in horaris.items():
        llista.sort()
        if sum(1 for _, sid, _ in llista if parades[sid]["c"]) >= 2:
            bons[tid] = llista

    cache_lloc = {}

    def lloc(sid):
        """Nom del poble de la parada (o el nom de la parada si és fora de la demarcació)."""
        if sid not in cache_lloc:
            n, la, lo = totes.get(sid, ("", 0, 0))
            cache_lloc[sid] = municipi(muns, la, lo) or n
        return cache_lloc[sid]

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
            e = extrems.get(tid)
            llista_dia.append({"r": t["route_id"], "h": t.get("trip_headsign", "").strip(),
                               "o": lloc(e[0][1]) if e else "", "d": lloc(e[1][1]) if e else "",
                               "to": round(a_min(e[0][2]), 2) if e else None,
                               "td": round(a_min(e[1][2]), 2) if e else None,
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

    # 05.11.2026: trams per la carretera entre parades seguides (shapes.txt o OSRM, amb memòria)
    seqs = {}
    for vs in dies.values():
        for v in vs:
            sids = tuple(sid for sid, _ in v["s"])
            seqs.setdefault(sids, None)
    for rid, seq in tracats.items():
        seqs.setdefault(tuple(seq), None)
    usats = {f"{a}>{b}" for sids in seqs for a, b in zip(sids, sids[1:])}
    try:
        with open(TRAMS, encoding="utf-8") as f:
            memoria = json.load(f).get("trams", {})
    except Exception:  # noqa: BLE001
        memoria = {}
    trams = {k: v for k, v in memoria.items() if k in usats}
    falten = usats - set(trams)
    print(f"Trams: {len(usats)} en ús, {len(trams)} ja calculats, {len(falten)} per calcular")
    if falten:
        trams.update(trams_shapes(z, viatges, bons, totes, falten))
        falten = usats - set(trams)
    if falten:
        trams.update(trams_osrm(sorted(seqs, key=len, reverse=True), totes, falten))
    pendents = len(usats - set(trams))
    if pendents:
        print(f"{pendents} trams queden en línia recta")

    def recorregut(seq):
        pts = []
        for a, b in zip(seq, seq[1:]):
            t = trams.get(f"{a}>{b}") or [parades[a]["ll"], parades[b]["ll"]]
            pts.extend(t if not pts else t[1:])
        return pts or [parades[s]["ll"] for s in seq]

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
            "t": recorregut(tracats.get(rid, [])),   # per la carretera (abans, de parada a parada)
        }

    return {
        "generat": datetime.now(TZ).strftime("%d.%m.%Y %H.%M"),
        "font": "Generalitat de Catalunya · xarxa d'autobusos interurbans (GTFS)",
        "parades": {sid: {"n": parades[sid]["n"], "m": lloc(sid), "ll": parades[sid]["ll"]}
                    for sid in sorted(parades_usades)},
        "rutes": sortida_rutes,
        "dies": dies,
        "_trams": trams,
    }


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], "rb") as f:
            data = f.read()
    else:
        data = baixa()
    res = processa(data)
    trams = res.pop("_trams", {})
    os.makedirs(os.path.dirname(SORTIDA), exist_ok=True)
    with open(TRAMS, "w", encoding="utf-8") as f:
        json.dump({"font": "shapes.txt del GTFS o OSRM (© col·laboradors d'OpenStreetMap)",
                   "trams": dict(sorted(trams.items()))}, f, ensure_ascii=False, separators=(",", ":"))
    with open(SORTIDA, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, separators=(",", ":"))
    n = {k: len(v) for k, v in res["dies"].items()}
    print(f"Fet: {len(res['rutes'])} línies, {len(res['parades'])} parades, viatges per dia {n}")


if __name__ == "__main__":
    main()
