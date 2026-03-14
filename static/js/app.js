/* ============================================================
   France Elections 2026 — Main JS
   ============================================================ */

let candidateData = null;
let electionStatus = null;
let deptLayer = null;
let majorCityMarkers = [];
let newsItems = [];
let activeFilter = "all";
let highlightMayoral = true;

const PARTY_COLORS = {
  PS:          "#E8566C",
  NFP:         "#C0392B",
  EELV:        "#27AE60",
  LR:          "#2980B9",
  Renaissance: "#F39C12",
  RN:          "#2C3E7A",
  LFI:         "#CB4335",
  PCF:         "#E74C3C",
  UDR:         "#1A237E",
  Reconquête:  "#4A235A",
  Horizons:    "#E67E22",
  DVG:         "#F1948A",
  DVD:         "#85C1E9",
  Other:       "#95A5A6",
};

// Political spectrum position 0 (far left) → 100 (far right)
const PARTY_POSITION = {
  PCF: 5, LFI: 10, NFP: 18, PS: 25, EELV: 28,
  DVG: 35, Renaissance: 50, Horizons: 55,
  LR: 65, DVD: 62, LR: 65, UDR: 80, RN: 85, Reconquête: 92,
};

const DEPT_GEOJSON_URL =
  "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-version-simplifiee.geojson";

// ── Map init ──────────────────────────────────────────────────
const map = L.map("map", { center: [46.5, 2.3], zoom: 6 });
L.tileLayer("https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png", {
  attribution: "&copy; OpenStreetMap &copy; CARTO",
  subdomains: "abcd", maxZoom: 14,
}).addTo(map);

// ── Tooltip ───────────────────────────────────────────────────
const tooltip = document.getElementById("map-tooltip");
function showTooltip(e, html) {
  tooltip.innerHTML = html;
  tooltip.classList.remove("hidden");
  moveTooltip(e);
}
function moveTooltip(e) {
  const x = (e.originalEvent || e).clientX;
  const y = (e.originalEvent || e).clientY;
  tooltip.style.left = x + 14 + "px";
  tooltip.style.top  = y + 14 + "px";
}
function hideTooltip() { tooltip.classList.add("hidden"); }

// ── Race panel (map side panel) ───────────────────────────────
const racePanel = document.getElementById("race-panel");
const racePanelContent = document.getElementById("race-panel-content");
function openRacePanel(race) {
  racePanelContent.innerHTML = buildRacePanelHTML(race);
  racePanel.classList.remove("hidden");
}
function closeRacePanel() { racePanel.classList.add("hidden"); }
document.getElementById("panel-close").addEventListener("click", closeRacePanel);

// ── Party guide modal ─────────────────────────────────────────
document.getElementById("legend-party-btn").addEventListener("click", openPartyModal);
document.getElementById("party-modal-close").addEventListener("click", () => {
  document.getElementById("party-modal-overlay").classList.add("hidden");
});
document.getElementById("party-modal-overlay").addEventListener("click", (e) => {
  if (e.target === e.currentTarget) e.currentTarget.classList.add("hidden");
});

function openPartyModal() {
  const overlay = document.getElementById("party-modal-overlay");
  const track   = document.getElementById("party-matrix-track");
  const descs   = document.getElementById("party-descriptions");
  const parties = candidateData.parties;

  // Build matrix track
  track.innerHTML = "";
  const sorted = Object.entries(PARTY_POSITION).sort((a, b) => a[1] - b[1]);
  sorted.forEach(([key, pos]) => {
    const info = parties[key];
    if (!info) return;
    const dot = document.createElement("div");
    dot.className = "matrix-dot";
    dot.style.left = pos + "%";
    dot.style.background = info.color;
    dot.title = info.name;
    dot.innerHTML = `<span class="matrix-dot-label">${info.short}</span>`;
    track.appendChild(dot);
  });

  // Build description cards
  descs.innerHTML = "";
  const posOrder = {
    "Hard left": 0, "Left": 1, "Centre-left to left": 2, "Centre-left": 3,
    "Centre-left independent": 4, "Centre": 5, "Centre to centre-right": 6,
    "Centre-right independent": 7, "Centre-right": 8, "Hard right": 9,
    "Far right": 10,
  };
  const sortedParties = Object.entries(parties).sort(([, a], [, b]) => {
    return (posOrder[a.position] ?? 99) - (posOrder[b.position] ?? 99);
  });

  sortedParties.forEach(([key, info]) => {
    const card = document.createElement("div");
    card.className = "party-desc-card";
    card.innerHTML = `
      <div class="party-desc-header" style="border-left:4px solid ${info.color}">
        <span class="party-desc-short" style="color:${info.color}">${info.short}</span>
        <span class="party-desc-name">${info.name}</span>
        <span class="party-desc-pos">${info.position}</span>
      </div>
      <p class="party-desc-text">${info.description || ""}</p>`;
    descs.appendChild(card);
  });

  overlay.classList.remove("hidden");
}

// ── Race detail modal (from race cards) ──────────────────────
const raceModalOverlay = document.getElementById("race-modal-overlay");
const raceModalClose   = document.getElementById("race-modal-close");
raceModalClose.addEventListener("click", () => raceModalOverlay.classList.add("hidden"));
raceModalOverlay.addEventListener("click", (e) => {
  if (e.target === e.currentTarget) e.currentTarget.classList.add("hidden");
});

function openRaceModal(race) {
  document.getElementById("race-modal-title").textContent = `${race.name} — Mayoral Race`;
  const content = document.getElementById("race-modal-content");

  // Render static data immediately
  content.innerHTML = buildRaceModalHTML(race);

  // Then load city news async
  const newsContainer = document.getElementById("race-modal-news");
  if (newsContainer) {
    fetch(`/api/news/${race.id}`)
      .then(r => r.json())
      .then(items => {
        if (!items.length) {
          newsContainer.innerHTML = `<p class="no-city-news">No local news found right now — try refreshing.</p>`;
          return;
        }
        newsContainer.innerHTML = items.slice(0, 6).map(item => `
          <div class="city-news-card">
            <div class="city-news-source" style="background:${item.color}">${item.source}</div>
            <div class="city-news-body">
              <a href="${item.link}" target="_blank" rel="noopener noreferrer" class="city-news-title">${item.title}</a>
              ${item.summary ? `<p class="city-news-summary">${item.summary.slice(0, 200)}…</p>` : ""}
            </div>
            ${item.title_original !== item.title ? '<div class="translated-tag">Translated</div>' : ""}
          </div>`
        ).join("");
      })
      .catch(() => {
        newsContainer.innerHTML = `<p class="no-city-news">Could not load local news.</p>`;
      });
  }

  raceModalOverlay.classList.remove("hidden");
}

function buildRaceModalHTML(race) {
  const parties = candidateData.parties;
  const polls   = race.polls;
  const inc     = race.incumbent;
  const incColor = PARTY_COLORS[inc.party] || "#999";

  let html = `<div class="race-modal-grid">`;

  // Left column: context + candidates
  html += `<div class="race-modal-left">`;

  // Context
  if (race.context) {
    html += `<div class="modal-section">
      <h4 class="modal-section-title">Background</h4>
      <p class="race-context-text">${race.context}</p>
    </div>`;
  }

  // Macron endorsement
  if (race.macron_endorsement) {
    const me = race.macron_endorsement;
    const meColor = me.candidate ? (PARTY_COLORS[me.party] || "#F39C12") : "#888";
    html += `<div class="modal-section macron-box" style="border-left:3px solid ${meColor}">
      <h4 class="modal-section-title">🏛 Macron / Renaissance Position</h4>
      ${me.candidate
        ? `<p><strong style="color:${meColor}">${me.candidate}</strong> (${me.party})</p>`
        : `<p><em>No candidate / endorsement withheld</em></p>`}
      <p class="macron-note">${me.note}</p>
    </div>`;
  }

  // Incumbent
  html += `<div class="modal-section">
    <h4 class="modal-section-title">Outgoing Mayor</h4>
    <div class="panel-incumbent">
      <div class="party-dot" style="background:${incColor}"></div>
      <strong>${inc.name}</strong>
      <span class="candidate-party" style="background:${incColor}">${inc.party}</span>
      <span style="color:var(--text-muted);font-size:0.75rem;">since ${inc.since}</span>
    </div>
    ${inc.note ? `<p style="font-size:0.72rem;color:var(--text-muted);margin-top:4px;">${inc.note}</p>` : ""}
  </div>`;

  // Candidates
  html += `<div class="modal-section">
    <h4 class="modal-section-title">2026 Candidates</h4>`;
  race.candidates.forEach(c => {
    const col = PARTY_COLORS[c.party] || "#999";
    html += `<div class="candidate-row">
      <div class="party-dot" style="background:${col}"></div>
      <span class="candidate-name">${c.name}</span>
      <span class="candidate-party" style="background:${col}">${c.party}</span>
      ${c.list ? `<span class="candidate-list">"${c.list}"</span>` : ""}
    </div>
    ${c.note ? `<p class="candidate-note">${c.note}</p>` : ""}`;
  });
  html += `</div>`;

  html += `</div>`; // end left column

  // Right column: polls + news
  html += `<div class="race-modal-right">`;

  // Round 1 polls
  if (polls && polls.round1) {
    html += `<div class="modal-section">
      <h4 class="modal-section-title">Round 1 Projection</h4>
      <div class="poll-bar-wrap">`;
    const sorted = [...polls.round1].sort((a, b) => b.pct - a.pct);
    sorted.forEach(p => {
      const col   = PARTY_COLORS[p.party] || "#999";
      const short = (parties[p.party] || { short: p.party }).short;
      html += `<div class="poll-bar-row">
        <div class="poll-bar-label">
          <span style="color:${col};font-weight:700;">${short}</span>
          ${p.candidate && p.candidate !== "TBD" ? " " + p.candidate.split(" ").slice(-1)[0] : ""}
        </div>
        <div class="poll-bar-track">
          <div class="poll-bar-fill" style="width:${p.pct}%;background:${col}"></div>
        </div>
        <div class="poll-bar-pct">${p.pct}%</div>
      </div>`;
    });
    html += `</div>
      ${polls.margin_of_error ? `<p class="poll-source">±${polls.margin_of_error}% margin of error</p>` : ""}
    </div>`;
  }

  // Runoff projection
  if (polls && polls.round2_projection && polls.round2_projection.length) {
    const r2 = polls.round2_projection;
    html += `<div class="modal-section">
      <h4 class="modal-section-title">Runoff Projection</h4>
      <div class="runoff-bar">`;
    r2.forEach(p => {
      const col   = PARTY_COLORS[p.party] || "#999";
      const label = p.candidate && p.candidate !== "TBD"
        ? p.candidate.split(" ").slice(-1)[0] : p.party;
      html += `<div class="runoff-segment" style="width:${p.pct}%;background:${col}">
        <span>${label}</span><span>${p.pct}%</span>
      </div>`;
    });
    html += `</div>`;

    const lead = Math.abs(r2[0].pct - (r2[1] ? r2[1].pct : 0));
    let compClass = "comp-safe", compLabel = "Likely " + r2[0].party;
    if (lead <= 4)  { compClass = "comp-tossup"; compLabel = "Toss-up"; }
    else if (lead <= 10) { compClass = "comp-likely"; compLabel = "Leans " + r2[0].party; }
    html += `<p class="race-card-competitiveness ${compClass}" style="margin-top:6px">${compLabel}</p>`;

    if (polls.note) html += `<p class="panel-note">${polls.note}</p>`;
    if (polls.source) html += `<p class="poll-source">Source: ${polls.source}${polls.date ? ", " + polls.date : ""}</p>`;
    html += `</div>`;
  }

  // News section (async)
  html += `<div class="modal-section">
    <h4 class="modal-section-title">Latest News</h4>
    <div id="race-modal-news" class="race-modal-news">
      <div class="news-loading" style="padding:16px"><div class="spinner"></div><p>Loading local news…</p></div>
    </div>
  </div>`;

  html += `</div>`; // end right column
  html += `</div>`; // end grid

  return html;
}

// ── Map panel HTML (compact, for hover/click on map) ─────────
function buildRacePanelHTML(race) {
  const parties = candidateData.parties;
  const polls   = race.polls;
  const inc     = race.incumbent;
  const incColor = PARTY_COLORS[inc.party] || "#999";

  let html = `<div class="panel-city-name">${race.name}</div>
    <div class="panel-dept">Dept. ${race.departement} &mdash; ${Number(race.population).toLocaleString()} pop.</div>`;

  if (inc.note) html += `<p style="font-size:0.7rem;color:var(--accent);margin-bottom:6px;">${inc.note}</p>`;

  html += `<div class="panel-section-title">Outgoing Mayor</div>
    <div class="panel-incumbent">
      <div class="party-dot" style="background:${incColor}"></div>
      <strong>${inc.name}</strong>
      <span class="candidate-party" style="background:${incColor}">${inc.party}</span>
    </div>`;

  if (polls && polls.round1) {
    html += `<div class="panel-section-title">Round 1 Projection</div><div class="poll-bar-wrap">`;
    [...polls.round1].sort((a,b) => b.pct - a.pct).forEach(p => {
      const col   = PARTY_COLORS[p.party] || "#999";
      const short = (parties[p.party] || { short: p.party }).short;
      html += `<div class="poll-bar-row">
        <div class="poll-bar-label" style="color:${col};font-weight:700;">${short}</div>
        <div class="poll-bar-track"><div class="poll-bar-fill" style="width:${p.pct}%;background:${col}"></div></div>
        <div class="poll-bar-pct">${p.pct}%</div>
      </div>`;
    });
    html += `</div>`;
  }

  if (polls && polls.round2_projection) {
    html += `<div class="runoff-header">Runoff Projection</div><div class="runoff-bar">`;
    polls.round2_projection.forEach(p => {
      const col   = PARTY_COLORS[p.party] || "#999";
      const label = p.candidate && p.candidate !== "TBD" ? p.candidate.split(" ").slice(-1)[0] : p.party;
      html += `<div class="runoff-segment" style="width:${p.pct}%;background:${col}">
        <span>${label}</span><span>${p.pct}%</span>
      </div>`;
    });
    html += `</div>`;
    if (polls.note) html += `<p class="panel-note">${polls.note}</p>`;
  }

  html += `<button class="panel-more-btn" onclick="openRaceModalById('${race.id}')">Full analysis &amp; news →</button>`;
  return html;
}

function openRaceModalById(id) {
  const race = candidateData.major_races.find(r => r.id === id);
  if (race) openRaceModal(race);
}

// ── Département styling ───────────────────────────────────────
function getDeptColor(code) {
  const mapping = candidateData.departement_map.mapping;
  const party   = mapping[code] || "Other";
  return PARTY_COLORS[party] || PARTY_COLORS["Other"];
}

function styleDept(feature) {
  return {
    fillColor: getDeptColor(feature.properties.code),
    fillOpacity: 0.55,
    color: "#fff",
    weight: 1.2,
  };
}

function onDeptMouseover(e) {
  e.target.setStyle({ fillOpacity: 0.75, weight: 2.5, color: "#1a1a1a" });
  e.target.bringToFront();
  const props  = e.target.feature.properties;
  const code   = props.code;
  const party  = candidateData.departement_map.mapping[code] || "Other";
  const pInfo  = candidateData.parties[party] || { name: party };
  const major  = candidateData.major_races.find(r => r.departement === code);
  const hint   = major ? `<br><strong>★ ${major.name}</strong> — Mayor race` : "";
  showTooltip(e, `<strong>${props.nom}</strong> (${code})${hint}<br>
    <span style="color:${PARTY_COLORS[party] || '#aaa'}">●</span> ${pInfo.name}`);
}

function onDeptMousemove(e) { moveTooltip(e); }
function onDeptMouseout(e)  { deptLayer.resetStyle(e.target); hideTooltip(); }
function onDeptClick(e)     {
  const major = candidateData.major_races.find(r => r.departement === e.target.feature.properties.code);
  if (major) openRacePanel(major);
}

function loadDeptLayer() {
  fetch(DEPT_GEOJSON_URL)
    .then(r => r.json())
    .then(geojson => {
      deptLayer = L.geoJSON(geojson, {
        style: styleDept,
        onEachFeature: (feature, layer) => {
          layer.on({ mouseover: onDeptMouseover, mousemove: onDeptMousemove,
                     mouseout: onDeptMouseout,  click: onDeptClick });
        },
      }).addTo(map);
      buildLegend();
    })
    .catch(err => console.error("GeoJSON load failed:", err));
}

// ── Mayor star markers ────────────────────────────────────────
function buildMayoralMarkers() {
  majorCityMarkers.forEach(m => map.removeLayer(m));
  majorCityMarkers = [];
  if (!highlightMayoral) return;

  candidateData.major_races.forEach(race => {
    const [lng, lat] = race.coordinates;
    const incColor   = PARTY_COLORS[race.incumbent.party] || "#999";
    const icon = L.divIcon({
      html: `<div class="mayor-star-icon" style="color:${incColor}">★</div>`,
      className: "", iconSize: [24, 24], iconAnchor: [12, 12],
    });
    const marker = L.marker([lat, lng], { icon })
      .addTo(map)
      .on("mouseover", e => {
        const leader = race.polls?.round1?.reduce((a, b) => a.pct > b.pct ? a : b);
        showTooltip(e, `<strong>★ ${race.name} Mayoral Race</strong><br>
          Outgoing: ${race.incumbent.name} (${race.incumbent.party})<br>
          ${leader ? `Leading: <strong>${leader.candidate || leader.party}</strong> ${leader.pct}%` : ""}`);
      })
      .on("mousemove", moveTooltip)
      .on("mouseout",  hideTooltip)
      .on("click",     () => openRacePanel(race));
    majorCityMarkers.push(marker);
  });
}

// ── Legend ────────────────────────────────────────────────────
function buildLegend() {
  const container = document.getElementById("legend-items");
  const usedParties = new Set(Object.values(candidateData.departement_map.mapping));
  container.innerHTML = "";
  Object.entries(candidateData.parties).forEach(([key, info]) => {
    if (!usedParties.has(key)) return;
    const item = document.createElement("div");
    item.className = "legend-item";
    item.innerHTML = `<div class="legend-swatch" style="background:${info.color}"></div><span>${info.short}</span>`;
    container.appendChild(item);
  });
  const starItem = document.createElement("div");
  starItem.className = "legend-item";
  starItem.innerHTML = `<span style="font-size:1rem;line-height:1">★</span><span>Mayor race</span>`;
  container.appendChild(starItem);
}

// ── Race cards grid ───────────────────────────────────────────
function buildRacesGrid() {
  const grid = document.getElementById("races-grid");
  grid.innerHTML = "";
  candidateData.major_races.forEach(race => {
    const parties   = candidateData.parties;
    const polls     = race.polls;
    const incColor  = PARTY_COLORS[race.incumbent.party] || "#999";
    const incShort  = (parties[race.incumbent.party] || { short: race.incumbent.party }).short;

    let leader = { party: race.incumbent.party, pct: "—", candidate: race.incumbent.name };
    if (polls?.round1?.length) leader = polls.round1.reduce((a, b) => a.pct > b.pct ? a : b);
    const leaderColor = PARTY_COLORS[leader.party] || "#999";
    const leaderShort = (parties[leader.party] || { short: leader.party }).short;

    let compClass = "comp-safe", compLabel = "Safe";
    if (polls?.round2_projection?.length >= 2) {
      const lead = Math.abs(polls.round2_projection[0].pct - polls.round2_projection[1].pct);
      if (lead <= 4)  { compClass = "comp-tossup"; compLabel = "Toss-up"; }
      else if (lead <= 10) { compClass = "comp-likely"; compLabel = "Leans " + leaderShort; }
    }

    let runoffBar = "";
    if (polls?.round2_projection) {
      runoffBar = `<div class="race-card-runoff">`;
      polls.round2_projection.forEach(p => {
        runoffBar += `<div style="flex:${p.pct};background:${PARTY_COLORS[p.party] || '#999'}"></div>`;
      });
      runoffBar += `</div>`;
    }

    // Macron note
    const me = race.macron_endorsement;
    const macronTag = me?.candidate
      ? `<div class="macron-tag" title="Macron/Renaissance backs ${me.candidate}">🏛 ${me.candidate}</div>`
      : (me ? `<div class="macron-tag macron-none">🏛 No endorsement</div>` : "");

    const card = document.createElement("div");
    card.className = "race-card";
    card.innerHTML = `
      <div class="race-card-header" style="background:${incColor}20;border-bottom:2px solid ${incColor}">
        <span class="race-card-city">★ ${race.name}</span>
        <span class="race-card-incumbent" style="background:${incColor}">${incShort}</span>
      </div>
      <div class="race-card-body">
        <div class="race-card-leader">
          <span style="color:${leaderColor};font-weight:800;">${leaderShort}</span>
          ${leader.candidate && leader.candidate !== "TBD" ? " " + leader.candidate.split(" ").slice(-1)[0] : ""}
        </div>
        <div class="race-card-pct">Round 1 lead: ${leader.pct}%</div>
        ${runoffBar}
        <div class="race-card-competitiveness ${compClass}">${compLabel}</div>
        ${macronTag}
        <div class="race-card-cta">Click for full analysis →</div>
      </div>`;

    card.addEventListener("click", () => openRaceModal(race));
    grid.appendChild(card);
  });
}

// ── Status badge ──────────────────────────────────────────────
function updateStatusBadge(status) {
  const badge  = document.getElementById("election-status-badge");
  const noteEl = document.getElementById("legend-note");
  if (status.phase === "pre_election") {
    badge.textContent = "Pre-Election";
    badge.className   = "status-badge status-pre";
    noteEl.textContent = "Polling projections — not election results";
  } else if (status.phase === "round1") {
    badge.textContent = "Round 1 Live";
    badge.className   = "status-badge status-round1";
    noteEl.textContent = "Live results — Round 1 counting";
  } else {
    badge.textContent = "Round 2 Live";
    badge.className   = "status-badge status-round2";
    noteEl.textContent = "Live results — Round 2 counting";
  }
}

// ── News ──────────────────────────────────────────────────────
function renderNews(items) {
  const grid = document.getElementById("news-grid");
  const filtered = activeFilter === "all" ? items : items.filter(i => i.source === activeFilter);
  if (!filtered.length) {
    grid.innerHTML = `<div class="news-error">No election news found for this source. Try refreshing or select a different filter.</div>`;
    return;
  }
  grid.innerHTML = filtered.map(item => `
    <div class="news-card">
      <div class="news-card-source" style="background:${item.color}">
        <div class="source-logo">${item.logo}</div>${item.source}
      </div>
      <div class="news-card-body">
        <div class="news-card-title">
          <a href="${item.link}" target="_blank" rel="noopener noreferrer">${item.title}</a>
        </div>
        ${item.summary ? `<div class="news-card-summary">${item.summary}</div>` : ""}
      </div>
      <div class="news-card-footer">
        <span>${item.published || ""}</span>
        ${item.title_original !== item.title ? '<span class="translated-tag">Translated from French</span>' : ""}
      </div>
    </div>`
  ).join("");
}

function loadNews() {
  document.getElementById("news-grid").innerHTML =
    `<div class="news-loading"><div class="spinner"></div><p>Loading election news&hellip;</p></div>`;
  fetch("/api/news")
    .then(r => r.json())
    .then(data => {
      newsItems = data;
      if (!newsItems.length) {
        document.getElementById("news-grid").innerHTML =
          `<div class="news-error"><strong>No news loaded yet.</strong><br>The scraper is running — this may take a moment on first load.</div>`;
        return;
      }
      renderNews(newsItems);
    })
    .catch(() => {
      document.getElementById("news-grid").innerHTML =
        `<div class="news-error">Could not load news. Is the server running?</div>`;
    });
}

// ── Controls ──────────────────────────────────────────────────
document.getElementById("btn-overview").addEventListener("click", () => {
  map.flyTo([46.5, 2.3], 6, { duration: 1 });
  document.getElementById("btn-overview").classList.add("active");
  document.getElementById("btn-zoom-major").classList.remove("active");
});
document.getElementById("btn-zoom-major").addEventListener("click", () => {
  map.flyTo([46.5, 3.0], 6.2, { duration: 1 });
  document.getElementById("btn-zoom-major").classList.add("active");
  document.getElementById("btn-overview").classList.remove("active");
});
document.getElementById("toggle-mayoral").addEventListener("change", e => {
  highlightMayoral = e.target.checked;
  buildMayoralMarkers();
});
document.querySelectorAll(".news-filter-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".news-filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeFilter = btn.dataset.source;
    renderNews(newsItems);
  });
});
document.getElementById("refresh-news").addEventListener("click", () => loadNews());

// ── Results polling ───────────────────────────────────────────
function startResultsPolling() {
  function poll() {
    fetch("/api/status")
      .then(r => r.json())
      .then(status => { electionStatus = status; updateStatusBadge(status); })
      .catch(() => {});
  }
  poll();
  setInterval(poll, 300000);
}

// ── Boot ──────────────────────────────────────────────────────
async function init() {
  const resp = await fetch("/api/candidates");
  candidateData = await resp.json();
  loadDeptLayer();
  buildMayoralMarkers();
  buildRacesGrid();
  startResultsPolling();
  loadNews();
  setInterval(loadNews, 600000);
}

init();
