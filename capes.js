/* Capes de La TdG per al mapa dels busos.
   Només LLEGEIX fitxers que el tauler i els bots ja publiquen: no fa cap consulta
   a les fonts originals ni gasta quota de ningú. */
(function () {
  const TAULER = "https://latdg.github.io/tauler/";
  const FITXERS = {
    viu: TAULER + "dades/viu.json",
    dea: TAULER + "dades/dea.json",
    antenes: TAULER + "dades/antenes.json",
    // Registre del dia del vigilant d'aeronaus: tot el que ha passat a menys de 40 km
    aeronaus: (() => { const d = new Date(), p = n => String(n).padStart(2, "0");
      return `https://raw.githubusercontent.com/latdg/vigilant-aeronaus/dades/registre/${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}.json`; })(),
  };

  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const coma = n => String(n).replace(".", ",");
  const adreca = s => String(s || "").replace(/^C\/\s*/i, "C. ").replace(/^(Avgda\.?|Avda\.?|Av\/)\s*/i, "Av. ");
  const ok = (la, lo) => typeof la === "number" && typeof lo === "number";

  function icona(txt, color, sq) {
    return L.divIcon({ className: "", iconSize: null, iconAnchor: [12, 10],
      html: `<div class="ic${sq ? " sq" : ""}" style="background:${color}">${esc(txt)}</div>` });
  }
  function pop(titol, cos, peu) {
    return `<div class="pop"><h3>${esc(titol)}</h3>${cos}${peu ? `<div class="m">${peu}</div>` : ""}</div>`;
  }
  // Les mateixes emoticones que fa servir el vigilant d'aeronaus (CATEGORIES de vigilant.py)
  const EMOJI_AERO = {
    "AERONAU SANITÀRIA": "🚑", "MITJÀ AERI D'EXTINCIÓ": "🚒", "POLICIA, TRÀNSIT O SEGURETAT": "🚓",
    "SALVAMENT MARÍTIM": "🛟", "AERONAU MILITAR": "🎖️", "AERONAU MILITAR O D'ESTAT": "🏛️", "DRON": "🛸",
    "JET PRIVAT O AEROTAXI": "💼", "TREBALLS AERIS": "📷", "HELICÒPTER (SERVEI SENSE IDENTIFICAR)": "🚁",
    "PLANADOR, ULTRALLEUGER O GLOBUS": "🪂", "AVIONETA (AVIACIÓ GENERAL)": "🛩️",
    "AERONAU SENSE IDENTIFICAR": "❓", "VOL COMERCIAL": "✈️",
  };
  const avio = a => L.divIcon({ className: "", iconSize: [26, 26], iconAnchor: [13, 13],
    html: `<div class="emo">${EMOJI_AERO[String(a.categoria || "").toUpperCase()] || "✈️"}</div>` });

  async function carrega() {
    const out = {};
    await Promise.all(Object.entries(FITXERS).map(async ([k, u]) => {
      try {
        const r = await fetch(u + "?v=" + Date.now(), { cache: "no-store" });
        if (r.ok) out[k] = await r.json();
      } catch (e) { /* capa sense dades */ }
    }));
    return out;
  }

  /* Retorna la llista de capes per al tauler lateral */
  function pinta(map, D) {
    const v = (D.viu && D.viu.blocs) || {};
    const G = () => L.layerGroup();
    const C = {
      bombers: G(), v16: G(), aero: G(), terra: G(),
      llum: G(), aigua: G(), dea: G(), ante: G(),
    };
    const n = {};

    (v.bombers?.actuacions || []).forEach(a => { if (!ok(a.lat, a.lon)) return;
      L.marker([a.lat, a.lon], { icon: icona(a.incendi ? "FOC" : "BOMB", "#c62828", true) })
        .bindPopup(pop("Bombers", `${esc(a.descripcio)}<br>${esc(a.municipi)} · ${esc(a.inici)}${a.vehicles ? ` · ${a.vehicles} vehicles` : ""}`, a.fase ? "Fase: " + esc(a.fase) : "")).addTo(C.bombers); });
    n.bombers = (v.bombers?.actuacions || []).length;

    (v.v16?.balises || []).forEach(b => { if (!ok(b.lat, b.lon)) return;
      L.marker([b.lat, b.lon], { icon: icona("V16", "#e65100", true) })
        .bindPopup(pop("Balisa V16", `${esc(b.via)}${b.pk ? ", pk " + esc(b.pk) : ""}<br>${esc(b.municipi)} · ${esc(b.inici)}`, esc(b.orientacio))).addTo(C.v16); });
    n.v16 = (v.v16?.balises || []).length;

    const aeros = (Array.isArray(D.aeronaus) ? D.aeronaus : []).filter(a => a.clau !== "comercial" && ok(a.lat, a.lon));
    aeros.forEach(a => {
      L.marker([a.lat, a.lon], { icon: avio(a) })
        .bindPopup(pop(`${EMOJI_AERO[String(a.categoria || "").toUpperCase()] || "✈️"} ${a.categoria || "Aeronau"}`, `${esc(a.hora)} h${a.matricula ? " · " + esc(a.matricula) : ""}${a.model ? " · " + esc(a.model) : ""}<br>${esc(a.ubicacio)}<br>${a.altitud ? a.altitud + " m" : ""}${a.velocitat ? " · " + a.velocitat + " km/h" : ""}${a.distancia != null ? `<br>A ${coma(a.distancia)} km de la Bisbal` : ""}`, "Vigilant d'aeronaus · punt més proper a la Bisbal")).addTo(C.aero); });
    n.aero = aeros.length;


    (v.terratremols?.llista || []).forEach(t => { if (!ok(t.lat, t.lon)) return;
      L.circleMarker([t.lat, t.lon], { radius: 4 + t.magnitud * 2, color: "#5e35b1", weight: 1.5, fillColor: "#7e57c2", fillOpacity: .3 })
        .bindPopup(pop(`Terratrèmol de magnitud ${coma(t.magnitud)}`, `${esc(t.lloc)}<br>${esc(t.data)} · a ${t.km} km`, `<a href="${esc(t.enllac)}" target="_blank" rel="noopener">IGN</a>`)).addTo(C.terra); });
    n.terra = (v.terratremols?.llista || []).length;

    (v.tallsLlum?.talls || []).forEach(t => { if (!ok(t.lat, t.lon)) return;
      L.marker([t.lat, t.lon], { icon: icona("LLUM", "#6d4c41", true) })
        .bindPopup(pop(t.avaria ? "Avaria elèctrica" : "Tall de llum", `${esc(t.municipi)} · ${esc(t.causa)}<br>De ${esc(t.inici)} a ${esc(t.reposicio)}${t.abonats ? `<br>${t.abonats} abonats` : ""}`, "Endesa")).addTo(C.llum); });
    n.llum = (v.tallsLlum?.talls || []).length;

    (v.tallsAigua?.talls || []).forEach(t => { const g = t.geom; if (!g) return;
      const html = pop(t.avaria ? "Avaria d'aigua" : "Tall d'aigua", `Forallac · ${esc(t.adreca)}<br>${esc(t.carrers)}<br>${esc(t.quan)}`, "Veolia");
      const st = { color: "#0277bd", weight: 3 };
      if (g.tipus === "punt") L.marker(g.coords, { icon: icona("AIGUA", "#0277bd", true) }).bindPopup(html).addTo(C.aigua);
      else if (g.tipus === "linia") L.polyline(g.coords, st).bindPopup(html).addTo(C.aigua);
      else if (g.tipus === "poligon") L.polygon(g.coords, { ...st, fillOpacity: .2 }).bindPopup(html).addTo(C.aigua); });
    n.aigua = (v.tallsAigua?.talls || []).length;

    const munD = (D.dea && D.dea.municipis) || {};
    (D.dea?.fixos || []).forEach(d => { if (!ok(d.lat, d.lon)) return;
      L.marker([d.lat, d.lon], { icon: icona("DEA", "#2e7d32", true) })
        .bindPopup(pop("Desfibril·lador", `${esc(d.nom)}<br>${esc(adreca(d.adreca))}${d.espai ? " · " + esc(d.espai) : ""}<br>${esc(munD[d.mun] || "")}`, d.aprox ? "Ubicació aproximada" : "")).addTo(C.dea); });
    n.dea = (D.dea?.fixos || []).length;

    const munA = (D.antenes && D.antenes.municipis) || {};
    (D.antenes?.emplacaments || []).forEach(a => { if (!ok(a.lat, a.lon)) return;
      const ops = (a.operadors || []).map(o => o.op).join(", ");
      L.marker([a.lat, a.lon], { icon: icona("ANT", "#455a64", true) })
        .bindPopup(pop("Antena de telefonia", `${esc(ops)}<br>${esc(munA[a.mun] || "")}`, `<a href="${esc(a.enllac)}" target="_blank" rel="noopener">Celda</a>`)).addTo(C.ante); });
    n.ante = (D.antenes?.emplacaments || []).length;

    const D2 = c => `<span class="sw dot" style="background:${c}"></span>`;
    const q = k => n[k] ? `${n[k]} ara` : "Cap ara";
    return [
      { g: "Mobilitat" },
      { id: "ly-v16", label: "Balises V16", sub: q("v16"), layer: C.v16, sw: D2("#e65100"), on: true },
      { id: "ly-aero", label: "Aeronaus", sub: n.aero ? `${n.aero} avui, a menys de 40 km` : "Cap avui", layer: C.aero, sw: `<span style="justify-self:center;font-size:15px;line-height:1">✈️</span>`, on: true },
      { g: "Territori" },
      { id: "ly-terra", label: "Terratrèmols", sub: `${n.terra} en 30 dies`, layer: C.terra, sw: D2("#5e35b1"), on: false },
      { g: "Emergències i talls" },
      { id: "ly-bombers", label: "Bombers", sub: q("bombers"), layer: C.bombers, sw: D2("#c62828"), on: true },
      { id: "ly-llum", label: "Talls de llum", sub: q("llum"), layer: C.llum, sw: D2("#6d4c41"), on: true },
      { id: "ly-aigua", label: "Talls d'aigua a Forallac", sub: q("aigua"), layer: C.aigua, sw: D2("#0277bd"), on: true },
      { g: "Serveis" },
      { id: "ly-dea", label: "Desfibril·ladors", sub: `${n.dea} fixos`, layer: C.dea, sw: D2("#2e7d32"), on: false },
      { id: "ly-ante", label: "Antenes de telefonia", sub: `${n.ante} emplaçaments`, layer: C.ante, sw: D2("#455a64"), on: false },
    ];
  }

  window.CapesTdG = { carrega, pinta };
})();
