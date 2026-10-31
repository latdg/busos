"""Busca el PDF d'horaris vigent de cada línia a la seva pàgina de Moventis
i genera data/horaris.json per al mapa.

Les pàgines de línia de Moventis no canvien, però el PDF canvia de nom cada
temporada. Si una pàgina no respon o no hi ha PDF, es manté el que hi havia.
"""
import json, os, re, urllib.parse, urllib.request

ARREL = os.path.join(os.path.dirname(__file__), "..")
FONTS = os.path.join(ARREL, "scripts", "horaris_fonts.json")
SORTIDA = os.path.join(ARREL, "data", "horaris.json")
RX_PDF = re.compile(r'href="([^"]+?/files/line/files/[^"]+?\.pdf)"', re.I)


def baixa(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (latdg-busos)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def main():
    with open(FONTS, encoding="utf-8") as f:
        fonts = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    try:
        with open(SORTIDA, encoding="utf-8") as f:
            abans = json.load(f)
    except (OSError, ValueError):
        abans = {}

    pagines = {}
    sortida = {}
    for codi, f in fonts.items():
        entrada = {"linia": f.get("linia", ""), "pagina": f.get("pagina", "")}
        if f.get("pdf"):
            entrada["pdf"] = f["pdf"]
        elif f.get("pagina"):
            url = f["pagina"]
            if url not in pagines:
                try:
                    m = RX_PDF.search(baixa(url))
                    pagines[url] = urllib.parse.urljoin(url, m.group(1)) if m else ""
                    print(("PDF " if m else "Sense PDF ") + url)
                except Exception as e:  # noqa: BLE001
                    pagines[url] = ""
                    print("Error", url, e)
            entrada["pdf"] = pagines[url] or abans.get(codi, {}).get("pdf", "")
        sortida[codi] = entrada

    os.makedirs(os.path.dirname(SORTIDA), exist_ok=True)
    with open(SORTIDA, "w", encoding="utf-8") as f:
        json.dump(sortida, f, ensure_ascii=False, indent=1)
    print(f"Horaris: {sum(1 for v in sortida.values() if v.get('pdf'))} de {len(sortida)} línies amb PDF")


if __name__ == "__main__":
    main()
