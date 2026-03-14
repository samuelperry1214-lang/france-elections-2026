/* ============================================================
   France Elections 2026 — Main JS
   Map (Leaflet) + News Monitor
   ============================================================ */

// ---- State ----
let candidateData = null;
let electionStatus = null;
let deptLayer = null;
let majorCityMarkers = [];
let newsItems = [];
let activeFilter = "all";
let highlightMayoral = true;

// ---- Party colours (mirrors CSS variables) ----
const PARTY_COLORS = {
  PS:          "#E8566C",
  NFP:         "#C0392B",
  EELV:        "#27AE60",
  LR:          "#2980B9",
  Renaissance: "#F39C12",
  RN:          "#2C3E7A",
  PCF:         "#E74C3C",
  DVG:         "#F1948A",
  DVD:         "#85C1E9",
  Other:       "#95A5A6",
};

// ---- GeoJSON sources ----
const DEPT_GEOJSON_URL =
  "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-version-simplifiee.geojson";

// ---- Leaflet map init ----
const map = L.map("map", {
  center: [46.5, 2.3],
  zoom: 6,
  zoomControl: true,
  scrollWheelZoom: true,
});

L.tileLayer(
  "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
  {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
    subdomains: "abcd",
    maxZoom: 14,
  }
).addTo(map);

// ---- Tooltip ----
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

function hideTooltip() {
  tooltip.classList.add("hidden");
}

// ---- Race panel ----
const racePanel = document.getElementById("race-panel");
const racePanelContent = document.getElementById("race-panel-content");

function openRacePanel(race) {
  racePanelContent.innerHTML = buildRacePanelHTML(race);
  racePanel.classList.remove("hidden");
}

function closeRacePanel() {
  racePanel.classList.add("hidden");
}

document.getElementById("panel-close").addEventListener("click", closeRacePanel);

// ---- Build race panel HTML ----
function buildRacePanelHTML(race) {
  const parties = candidateData.parties;
  const polls = race.polls;
  const inc = race.incumbent;
  const incColor = PARTY_COLORS[inc.party] || "#999";

  let html = `
    <div class="panel-city-name">${race.name}</div>
    <div class="panel-dept">Département ${race.departement} &mdash; Pop. ${Number(race.population).toLocaleString()}</div>`;

  if (race.note) {
    html += `<p style="font-size:0.72rem;color:var(--text-muted);margin-bottom:8px;font-style:italic;">${race.note}</p>`;
  }

  // Incumbent
  html += `
    <div class="panel-section-title">Incumbent</div>
    <div class="panel-incumbent">
      <div class="party-dot" style="background:${incColor}"></div>
      <span style="font-weight:700;font-size:0.88rem;">${inc.name}</span>
      <span class="candidate-party" style="background:${incColor}">${inc.party}</span>
      <span style="font-size:0.72rem;color:var(--text-muted);">since ${inc.since}</span>
    </div>`;

  // Candidates
  html += `<div class="panel-section-title">2026 Candidates</div>`;
  race.candidates.forEach((c) => {
    const col = PARTY_COLORS[c.party] || "#999";
    html += `
      <div class="candidate-row">
        <div class="party-dot" style="background:${col}"></div>
        <span class="candidate-name">${c.name}</span>
        <span class="candidate-party" style="background:${col}">${c.party}</span>
      </div>`;
  });

  // Round 1 polls
  if (polls && polls.round1 && polls.round1.length) {
    html += `<div class="panel-section-title">Round 1 Projection</div>`;
    html += `<div class="poll-bar-wrap">`;
    const sorted = [...polls.round1].sort((a, b) => b.pct - a.pct);
    sorted.forEach((p) => {
      const col = PARTY_COLORS[p.party] || "#999";
      const label = p.candidate && p.candidate !== "TBD"
        ? p.candidate.split(" ").pop()   // Last name only
        : (parties[p.party] ? parties[p.party].short : p.party);
      html += `
        <div class="poll-bar-row">
          <div class="poll-bar-label" title="${p.candidate || p.party}">
            <span style="color:${col};font-weight:700;">${parties[p.party] ? parties[p.party].short : p.party}</span>
            ${label !== (parties[p.party] ? parties[p.party].short : p.party) ? " " + label : ""}
          </div>
          <div class="poll-bar-track">
            <div class="poll-bar-fill" style="width:${p.pct}%;background:${col}"></div>
          </div>
          <div class="poll-bar-pct">${p.pct}%</div>
        </div>`;
    });
    html += `</div>`;
    if (polls.margin_of_error) {
      html += `<p class="poll-source">±${polls.margin_of_error}% margin of error</p>`;
    }
  }

  // Runoff projection
  if (polls && polls.round2_projection && polls.round2_projection.length) {
    const r2 = polls.round2_projection;
    html += `<div class="runoff-header">Runoff Projection</div>`;
    html += `<div class="runoff-bar">`;
    r2.forEach((p) => {
      const col = PARTY_COLORS[p.party] || "#999";
      const label = p.candidate && p.candidate !== "TBD" ? p.candidate.split(" ").pop() : p.party;
      html += `<div class="runoff-segment" style="width:${p.pct}%;background:${col}">
        <span>${label}</span><span>${p.pct}%</span>
      </div>`;
    });
    html += `</div>`;

    // Competitiveness label
    const lead = Math.abs(r2[0].pct - (r2[1] ? r2[1].pct : 0));
    let compClass = "comp-safe", compLabel = "Likely hold";
    if (lead <= 4) { compClass = "comp-tossup"; compLabel = "Toss-up"; }
    else if (lead <= 10) { compClass = "comp-likely"; compLabel = "Leans " + r2[0].party; }
    else { compClass = "comp-safe"; compLabel = "Likely " + r2[0].party; }

    html += `<p class="race-card-competitiveness ${compClass}">${compLabel}</p>`;
  }

  if (polls && polls.note) {
    html += `<p class="panel-note">${polls.note}</p>`;
  }

  if (polls && polls.source) {
    html += `<p class="poll-source">Source: ${polls.source}${polls.date ? ", " + polls.date : ""}</p>`;
  }

  return html;
}

// ---- Département styling ----
function getDeptColor(deptCode) {
  const mapping = candidateData.departement_map.mapping;
  const party = mapping[deptCode] || "Other";
  return PARTY_COLORS[party] || PARTY_COLORS["Other"];
}

function styleDept(feature) {
  const code = feature.properties.code;
  const color = getDeptColor(code);
  return {
    fillColor: color,
    fillOpacity: 0.55,
    color: "#fff",
    weight: 1.2,
  };
}

function deptHighlightStyle(feature) {
  return {
    fillOpacity: 0.75,
    weight: 2.5,
    color: "#1a1a1a",
  };
}

function onDeptMouseover(e) {
  const layer = e.target;
  layer.setStyle(deptHighlightStyle(layer.feature));
  layer.bringToFront();

  const props = layer.feature.properties;
  const code = props.code;
  const mapping = candidateData.departement_map.mapping;
  const party = mapping[code] || "Other";
  const partyInfo = candidateData.parties[party] || { name: party, short: party };

  // Check if a major race exists for this département
  const majorRace = candidateData.major_races.find((r) => r.departement === code);
  const raceHint = majorRace
    ? `<br><strong style="color:#fff;">★ ${majorRace.name}</strong> — Mayor race inside`
    : "";

  showTooltip(e,
    `<strong>${props.nom}</strong> (${code})${raceHint}<br>
     <span style="color:${PARTY_COLORS[party] || "#aaa"};">● </span>${partyInfo.name}`
  );
}

function onDeptMousemove(e) { moveTooltip(e); }

function onDeptMouseout(e) {
  deptLayer.resetStyle(e.target);
  hideTooltip();
}

function onDeptClick(e) {
  const code = e.target.feature.properties.code;
  const majorRace = candidateData.major_races.find((r) => r.departement === code);
  if (majorRace) {
    openRacePanel(majorRace);
  }
}

// ---- Load département GeoJSON ----
function loadDeptLayer() {
  fetch(DEPT_GEOJSON_URL)
    .then((r) => r.json())
    .then((geojson) => {
      deptLayer = L.geoJSON(geojson, {
        style: styleDept,
        onEachFeature: (feature, layer) => {
          layer.on({
            mouseover: onDeptMouseover,
            mousemove: onDeptMousemove,
            mouseout:  onDeptMouseout,
            click:     onDeptClick,
          });
        },
      }).addTo(map);

      buildLegend();
    })
    .catch((err) => console.error("GeoJSON load failed:", err));
}

// ---- Major city markers ----
function buildMayoralMarkers() {
  // Clear existing
  majorCityMarkers.forEach((m) => map.removeLayer(m));
  majorCityMarkers = [];

  if (!highlightMayoral) return;

  candidateData.major_races.forEach((race) => {
    const [lng, lat] = race.coordinates;
    const incColor = PARTY_COLORS[race.incumbent.party] || "#999";

    const icon = L.divIcon({
      html: `<div class="mayor-star-icon" style="color:${incColor};" title="${race.name} — Mayor Race">★</div>`,
      className: "",
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });

    const marker = L.marker([lat, lng], { icon })
      .addTo(map)
      .on("mouseover", (e) => {
        const polls = race.polls;
        const leader = polls && polls.round1 && polls.round1.length
          ? polls.round1.reduce((a, b) => (a.pct > b.pct ? a : b))
          : null;
        const leaderText = leader
          ? `Leading: <strong>${leader.candidate || leader.party}</strong> (${leader.pct}%)`
          : "Polling data pending";
        showTooltip(e,
          `<strong>★ ${race.name} Mayoral Race</strong><br>
           Incumbent: ${race.incumbent.name} (${race.incumbent.party})<br>
           ${leaderText}`
        );
      })
      .on("mousemove", moveTooltip)
      .on("mouseout", hideTooltip)
      .on("click", () => openRacePanel(race));

    majorCityMarkers.push(marker);
  });
}

// ---- Legend ----
function buildLegend() {
  const container = document.getElementById("legend-items");
  const parties = candidateData.parties;

  // Determine which parties are actually on the map
  const usedParties = new Set(Object.values(candidateData.departement_map.mapping));
  usedParties.add("major_mayoral"); // For reference

  container.innerHTML = "";
  Object.entries(parties).forEach(([key, info]) => {
    if (!usedParties.has(key) && key !== "Other") return;
    const item = document.createElement("div");
    item.className = "legend-item";
    item.innerHTML = `
      <div class="legend-swatch" style="background:${info.color}"></div>
      <span>${info.short}</span>`;
    container.appendChild(item);
  });

  // Mayoral star legend item
  const starItem = document.createElement("div");
  starItem.className = "legend-item";
  starItem.innerHTML = `<span style="font-size:1rem;">★</span><span>Mayoral race</span>`;
  container.appendChild(starItem);
}

// ---- Races summary grid ----
function buildRacesGrid() {
  const grid = document.getElementById("races-grid");
  grid.innerHTML = "";

  candidateData.major_races.forEach((race) => {
    const parties = candidateData.parties;
    const polls = race.polls;
    const incColor = PARTY_COLORS[race.incumbent.party] || "#999";
    const incShort = (parties[race.incumbent.party] || { short: race.incumbent.party }).short;

    let leaderInfo = { party: race.incumbent.party, pct: "—", candidate: race.incumbent.name };
    if (polls && polls.round1 && polls.round1.length) {
      leaderInfo = polls.round1.reduce((a, b) => (a.pct > b.pct ? a : b));
    }
    const leaderColor = PARTY_COLORS[leaderInfo.party] || "#999";
    const leaderShort = (parties[leaderInfo.party] || { short: leaderInfo.party }).short;

    // Competitiveness
    let compClass = "comp-safe", compLabel = "Safe";
    if (polls && polls.round2_projection && polls.round2_projection.length >= 2) {
      const lead = Math.abs(polls.round2_projection[0].pct - polls.round2_projection[1].pct);
      if (lead <= 4) { compClass = "comp-tossup"; compLabel = "Toss-up"; }
      else if (lead <= 10) { compClass = "comp-likely"; compLabel = "Leans " + leaderShort; }
    }

    // Runoff bar
    let runoffBar = "";
    if (polls && polls.round2_projection) {
      runoffBar = `<div class="race-card-runoff">`;
      polls.round2_projection.forEach((p) => {
        runoffBar += `<div style="width:${p.pct}%;background:${PARTY_COLORS[p.party] || "#999"}"></div>`;
      });
      runoffBar += `</div>`;
    }

    const card = document.createElement("div");
    card.className = "race-card";
    card.innerHTML = `
      <div class="race-card-header" style="background:${incColor}20;border-bottom:2px solid ${incColor}">
        <span class="race-card-city">${race.name}</span>
        <span class="race-card-incumbent" style="background:${incColor}">${incShort}</span>
      </div>
      <div class="race-card-body">
        <div class="race-card-leader">
          <span style="color:${leaderColor};font-weight:800;">${leaderShort}</span>
          ${leaderInfo.candidate && leaderInfo.candidate !== "TBD" ? leaderInfo.candidate.split(" ").pop() : ""}
        </div>
        <div class="race-card-pct">Round 1: ${leaderInfo.pct}%</div>
        ${runoffBar}
        <div class="race-card-competitiveness ${compClass}">${compLabel}</div>
      </div>`;

    card.addEventListener("click", () => openRacePanel(race));
    grid.appendChild(card);
  });
}

// ---- Election status badge ----
function updateStatusBadge(status) {
  const badge = document.getElementById("election-status-badge");
  const noteEl = document.getElementById("legend-note");

  if (status.phase === "pre_election") {
    badge.textContent = "Pre-Election";
    badge.className = "status-badge status-pre";
    noteEl.textContent = "Showing polling projections — not election results";
  } else if (status.phase === "round1") {
    badge.textContent = "Round 1 Live";
    badge.className = "status-badge status-round1";
    noteEl.textContent = "Live results — Round 1 counting";
  } else {
    badge.textContent = "Round 2 Live";
    badge.className = "status-badge status-round2";
    noteEl.textContent = "Live results — Round 2 counting";
  }
}

// ---- News rendering ----
function renderNews(items) {
  const grid = document.getElementById("news-grid");

  const filtered = activeFilter === "all"
    ? items
    : items.filter((i) => i.source === activeFilter);

  if (!filtered.length) {
    grid.innerHTML = `<div class="news-error">No election news found for this source right now.<br>
      <small>The scraper filters for election-related keywords — try checking back later or selecting a different source.</small></div>`;
    return;
  }

  grid.innerHTML = filtered.map((item) => `
    <div class="news-card" data-source="${item.source}">
      <div class="news-card-source" style="background:${item.color}">
        <div class="source-logo">${item.logo}</div>
        ${item.source}
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

function loadNews(force = false) {
  const grid = document.getElementById("news-grid");
  grid.innerHTML = `<div class="news-loading"><div class="spinner"></div><p>Loading election news&hellip;</p></div>`;

  fetch("/api/news")
    .then((r) => r.json())
    .then((data) => {
      newsItems = data;
      if (!newsItems.length) {
        grid.innerHTML = `<div class="news-error">
          <strong>No news loaded yet.</strong><br>
          The news scraper is running — this may take a moment on first load.<br>
          <small>If this persists, check that the Flask server is running and dependencies are installed.</small>
        </div>`;
        return;
      }
      renderNews(newsItems);
    })
    .catch((err) => {
      console.error("News load failed:", err);
      grid.innerHTML = `<div class="news-error">Could not load news. Is the server running?</div>`;
    });
}

// ---- Controls ----
document.getElementById("btn-overview").addEventListener("click", () => {
  map.flyTo([46.5, 2.3], 6, { duration: 1 });
  document.getElementById("btn-overview").classList.add("active");
  document.getElementById("btn-zoom-major").classList.remove("active");
});

document.getElementById("btn-zoom-major").addEventListener("click", () => {
  // Fit to a bounding box that shows all major cities well
  map.flyTo([46.5, 3.0], 6.2, { duration: 1 });
  document.getElementById("btn-zoom-major").classList.add("active");
  document.getElementById("btn-overview").classList.remove("active");
});

document.getElementById("toggle-mayoral").addEventListener("change", (e) => {
  highlightMayoral = e.target.checked;
  buildMayoralMarkers();
});

document.querySelectorAll(".news-filter-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".news-filter-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    activeFilter = btn.dataset.source;
    renderNews(newsItems);
  });
});

document.getElementById("refresh-news").addEventListener("click", () => loadNews(true));

// ---- Live results polling ----
// Poll every 5 minutes for status; on election day, poll every 60s
function startResultsPolling() {
  function poll() {
    fetch("/api/status")
      .then((r) => r.json())
      .then((status) => {
        electionStatus = status;
        updateStatusBadge(status);
        // If results are live, also refresh the map layer
        if (status.phase !== "pre_election") {
          fetch("/api/results")
            .then((r) => r.json())
            .then((results) => {
              // TODO: merge live results into the map layer colours
              // For now, just log
              console.log("Live results received:", Object.keys(results.results).length, "communes");
            });
        }
      })
      .catch((e) => console.warn("Status check failed:", e));
  }

  poll(); // immediate
  const interval = electionStatus && electionStatus.phase !== "pre_election" ? 60000 : 300000;
  setInterval(poll, interval);
}

// ---- Boot ----
async function init() {
  // 1. Load candidate data
  const resp = await fetch("/api/candidates");
  candidateData = await resp.json();

  // 2. Build map layers
  loadDeptLayer();
  buildMayoralMarkers();

  // 3. Build summary grid
  buildRacesGrid();

  // 4. Start status polling
  startResultsPolling();

  // 5. Load news
  loadNews();

  // 6. Auto-refresh news every 10 minutes
  setInterval(() => loadNews(), 600000);
}

init();
