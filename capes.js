/* Capes de La TdG per al mapa dels busos.
   Només LLEGEIX fitxers que el tauler i els bots ja publiquen: no fa cap consulta
   a les fonts originals ni gasta quota de ningú. */
(function () {
  const TAULER = "https://latdg.github.io/tauler/";
  const LLAMPS = "https://raw.githubusercontent.com/latdg/bots/llamps-dades/darrer.json";
  const FITXERS = {
    viu: TAULER + "dades/viu.json",
    dea: TAULER + "dades/dea.json",
    antenes: TAULER + "dades/antenes.json",
    serveis: TAULER + "dades/serveis.json",
    llamps: LLAMPS,
  };
  const BISBAL = [41.958, 3.038];
  // Estacions d'aforament (el tauler no en desa les coordenades)
  const RIUS = {
    "170221-002": [41.9600, 3.0360], "171910-001": [42.0280, 3.0720], "170792-002": [41.9860, 2.8230],
    "170558-002": [42.0830, 2.9870], "171997-002": [42.0430, 3.1180],
  };
  const GRAV = { groc: "#e6c229", taronja: "#f08a24", vermell: "#d62828" };

  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const coma = n => String(n).replace(".", ",");
  const pad = n => String(n).padStart(2, "0");
  const dia = d => `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
  const iso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const adreca = s => String(s || "").replace(/^C\/\s*/i, "C. ").replace(/^(Avgda\.?|Avda\.?|Av\/)\s*/i, "Av. ");
  const MIN = new Set(["de", "del", "la", "les", "el", "els", "i"]);
  const bonic = s => String(s || "").toLowerCase().replace(/[^\s-]+/g, (w, i) => {
    if (i > 0 && MIN.has(w)) return w;
    const m = w.match(/^(d'|l')(.*)$/);
    if (m) return (i > 0 ? m[1] : m[1].toUpperCase()) + m[2].charAt(0).toUpperCase() + m[2].slice(1);
    return w.charAt(0).toUpperCase() + w.slice(1);
  });
  const frase = s => String(s || "").toLowerCase().replace(/(^|\.\s+)(\p{L})/gu, (a, b, c) => b + c.toUpperCase());
  const ok = (la, lo) => typeof la === "number" && typeof lo === "number";

  function icona(txt, color, sq) {
    return L.divIcon({ className: "", iconSize: null, iconAnchor: [12, 10],
      html: `<div class="ic${sq ? " sq" : ""}" style="background:${color}">${esc(txt)}</div>` });
  }
  function pop(titol, cos, peu) {
    return `<div class="pop"><h3>${esc(titol)}</h3>${cos}${peu ? `<div class="m">${peu}</div>` : ""}</div>`;
  }
  const raig = c => L.divIcon({ className: "", iconSize: [16, 18], iconAnchor: [8, 9],
    html: `<svg width="16" height="18" viewBox="0 0 16 18"><path d="M9 0 1 10h6l-2 8 9-11H8z" fill="${c}" stroke="#fff" stroke-width="1"/></svg>` });
  const avio = L.divIcon({ className: "", iconSize: [20, 20], iconAnchor: [10, 10],
    html: `<svg width="20" height="20" viewBox="0 0 24 24"><path d="M12 2c.8 0 1.3.8 1.3 1.8V9l7.7 4.5v2l-7.7-2.3v4.6l2.2 1.7V21L12 20l-3.5 1v-1.5l2.2-1.7v-4.6L3 15.5v-2L10.7 9V3.8C10.7 2.8 11.2 2 12 2z" fill="#37474f" stroke="#fff" stroke-width="1"/></svg>` });

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

  /* Retorna la llista de capes per al tauler lateral i omple els blocs de text */
  function pinta(map, D, el) {
    const v = (D.viu && D.viu.blocs) || {};
    const G = () => L.layerGroup();
    const C = {
      bombers: G(), v16: G(), aero: G(), llamps: G(), rius: G(), terra: G(), piezo: G(),
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

    (v.aeronaus || []).forEach(a => { if (!ok(a.lat, a.lon)) return;
      L.marker([a.lat, a.lon], { icon: avio })
        .bindPopup(pop(`${a.categoria || "Aeronau"}`, `${esc(a.hora)} h · ${esc(a.matricula)} ${esc(a.model)}<br>${esc(a.ubicacio)}<br>${a.altitud ? a.altitud + " m" : ""}${a.velocitat ? " · " + a.velocitat + " km/h" : ""}`, "Vigilant d'aeronaus · avui")).addTo(C.aero); });
    n.aero = (v.aeronaus || []).length;

    [10, 30].forEach(r => L.circle(BISBAL, { radius: r * 1000, color: r === 10 ? "#d62828" : "#f08a24", weight: 1, dashArray: "4 4", fill: false, interactive: false }).addTo(C.llamps));
    const ll = D.llamps || {};
    (ll.llamps || []).forEach(l => { if (!ok(l.lat, l.lon)) return;
      L.marker([l.lat, l.lon], { icon: raig(l.km <= 10 ? "#d62828" : "#f08a24") })
        .bindPopup(pop("Llamp", `${esc(l.hora)} h · ${esc(l.lloc || "")}<br>a ${coma(l.km)} km de la Bisbal${l.kA != null ? ` · ${coma(l.kA)} kA` : ""}`, "XDDE · Meteocat")).addTo(C.llamps); });
    n.llamps = (ll.llamps || []).length;
    const llampsQuan = ll.generat ? dia(new Date(ll.generat)) : "";

    (v.rius?.estacions || []).forEach(e => { const p = RIUS[e.codi]; if (!p) return;
      const alerta = e.estat && e.estat !== "normalitat";
      L.marker(p, { icon: icona(`${e.riu} ${coma(e.cabal)}`, alerta ? "#d62828" : "#00838f", true) })
        .bindPopup(pop(`${e.riu} · ${e.lloc}`, `Cabal ${coma(e.cabal)} m³/s · nivell ${coma(e.nivell)} cm<br>${esc(e.hora)} · ${esc(e.estat)}`, "Agència Catalana de l'Aigua")).addTo(C.rius); });
    n.rius = (v.rius?.estacions || []).length;

    (v.terratremols?.llista || []).forEach(t => { if (!ok(t.lat, t.lon)) return;
      L.circleMarker([t.lat, t.lon], { radius: 4 + t.magnitud * 2, color: "#5e35b1", weight: 1.5, fillColor: "#7e57c2", fillOpacity: .3 })
        .bindPopup(pop(`Terratrèmol de magnitud ${coma(t.magnitud)}`, `${esc(t.lloc)}<br>${esc(t.data)} · a ${t.km} km`, `<a href="${esc(t.enllac)}" target="_blank" rel="noopener">IGN</a>`)).addTo(C.terra); });
    n.terra = (v.terratremols?.llista || []).length;

    (v.piezometres?.estacions || []).forEach(e => { if (!ok(e.lat, e.lon)) return;
      L.marker([e.lat, e.lon], { icon: icona(`${coma(e.fondaria)} m`, "#558b2f", true) })
        .bindPopup(pop(e.nom, `${esc(e.municipi)} · aigua a ${coma(e.fondaria)} m de fondària`, `Lectura del ${esc(e.data.split("-").reverse().join("."))}`)).addTo(C.piezo); });
    n.piezo = (v.piezometres?.estacions || []).length;

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

    /* blocs de text */
    if (el.avisos) {
      const av = [];
      (v.avisosMeteo?.aemet || []).forEach(a => av.push({ c: GRAV[a.gravetat] || "#e6c229", t: `AEMET · avís ${a.nivell} per ${a.fenomen}`, s: `${a.quan}. ${a.comentari || ""}` }));
      const mc = v.avisosMeteo?.meteocat;
      (Array.isArray(mc) ? mc : []).forEach(a => av.push({ c: GRAV[a.gravetat || a.nivell] || "#e6c229", t: `Meteocat · ${a.fenomen || a.titol || "avís"}`, s: a.quan || "" }));
      (v.proteccioCivil?.plans || []).forEach(p => av.push({ c: "#1d5fae", t: `Protecció Civil · ${p.pla}${p.fase ? " en " + p.fase : ""}`, s: p.quan || "" }));
      if (v.plaAlfa) av.push({ c: "#9aa1a9", t: "Pla Alfa", s: v.plaAlfa });
      el.avisos.innerHTML = av.length ? av.map(a => `<div class="alert"><i style="background:${a.c}"></i><span>${esc(a.t)}<small>${esc(a.s)}</small></span></div>`).join("")
        : `<div class="empty">Cap avís actiu.</div>`;
    }
    if (el.incid) {
      const inc = v.incidencies || [];
      const per = {};
      inc.forEach(i => (per[i.municipi] = per[i.municipi] || []).push(i));
      el.incid.innerHTML = inc.length ? Object.entries(per).map(([m, ll]) => `<div class="row1"><b>${esc(bonic(m))}</b>${ll.map(i => `<small>${esc(i.carretera)} (pk ${esc(i.km)}) · ${esc(frase(i.titol))}</small>`).join("")}</div>`).join("")
        : `<div class="empty">Cap incidència a les carreteres de la zona.</div>`;
    }
    if (el.farma) {
      const avui = iso(new Date());
      const d = (D.serveis?.farmacies?.dies || []).find(x => x.data === avui);
      el.farma.innerHTML = d && d.farmacies.length ? d.farmacies.map(f => `<div class="row1"><b>${esc(f.farmacia)}</b><small>${esc(adreca(f.adreca))} · la Bisbal d'Empordà</small><small>Telèfon ${esc(f.telefon)}</small></div>`).join("")
        : `<div class="empty">Sense dades de la guàrdia d'avui.</div>`;
    }

    const D2 = c => `<span class="sw dot" style="background:${c}"></span>`;
    const q = k => n[k] ? `${n[k]} ara` : "Cap ara";
    return [
      { g: "Mobilitat i trànsit" },
      { id: "ly-v16", label: "Balises V16", sub: q("v16"), layer: C.v16, sw: D2("#e65100"), on: true },
      { id: "ly-aero", label: "Aeronaus", sub: n.aero ? `${n.aero} avui` : "Cap avui", layer: C.aero, sw: D2("#37474f"), on: true },
      { g: "Meteorologia i territori" },
      { id: "ly-llamps", label: "Llamps", sub: `${n.llamps ? n.llamps : "Cap"} a l'última revisió${llampsQuan ? " (" + llampsQuan + ")" : ""}`, layer: C.llamps, sw: D2("#d62828"), on: true },
      { id: "ly-rius", label: "Rius", sub: "Daró i Ter", layer: C.rius, sw: D2("#00838f"), on: true },
      { id: "ly-terra", label: "Terratrèmols", sub: `${n.terra} en 30 dies`, layer: C.terra, sw: D2("#5e35b1"), on: false },
      { id: "ly-piezo", label: "Piezòmetres", sub: `${n.piezo} pous`, layer: C.piezo, sw: D2("#558b2f"), on: false },
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
