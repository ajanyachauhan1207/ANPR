const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

function statCard(label, value, cls) {
  const d = el("div", "stat " + (cls || ""));
  d.append(el("span", "stat-num", String(value)), el("span", "stat-label", label));
  return d;
}

function drawBars(daily) {
  const box = $("#bars");
  box.innerHTML = "";
  const max = Math.max(1, ...daily.map((d) => d.count));
  daily.forEach((d) => {
    const col = el("div", "bar-col");
    const track = el("div", "bar-track");
    const bar = el("div", "bar");
    bar.style.height = (d.count / max) * 100 + "%";
    track.append(bar);
    col.append(el("span", "bar-val", String(d.count)), track, el("span", "bar-label", d.day));
    box.append(col);
  });
}

function drawDonut(reg, unk) {
  const svg = $("#donut");
  svg.innerHTML = "";
  const ns = "http://www.w3.org/2000/svg";
  const ring = (cls, dash) => {
    const c = document.createElementNS(ns, "circle");
    c.setAttribute("cx", "21"); c.setAttribute("cy", "21"); c.setAttribute("r", "15.915");
    c.setAttribute("fill", "none"); c.setAttribute("stroke-width", "6");
    c.setAttribute("class", cls);
    if (dash) { c.setAttribute("stroke-dasharray", dash); c.setAttribute("stroke-dashoffset", "25"); }
    return c;
  };
  const total = reg + unk;
  svg.append(ring(total ? "ring-unk" : "ring-bg"));
  if (total) {
    const p = (reg / total) * 100;
    svg.append(ring("ring-reg", `${p} ${100 - p}`));
  }
  const t = document.createElementNS(ns, "text");
  t.setAttribute("x", "21"); t.setAttribute("y", "23.5");
  t.setAttribute("text-anchor", "middle"); t.setAttribute("class", "donut-num");
  t.textContent = String(total);
  svg.append(t);

  const lg = $("#legend");
  lg.innerHTML = "";
  [["Registered", reg, "#22d3a6"], ["Unknown", unk, "#f0b429"]].forEach(([name, n, col]) => {
    const row = el("div");
    const dot = el("span", "dot");
    dot.style.background = col;
    const pct = total ? Math.round((n / total) * 100) : 0;
    row.append(dot, document.createTextNode(`${name}: ${n} (${pct}%)`));
    lg.append(row);
  });
}

function drawTop(top) {
  const box = $("#top");
  box.innerHTML = "";
  if (!top.length) { box.append(el("p", "muted", "No detections yet.")); return; }
  top.forEach((t) => {
    const r = el("div", "toprow");
    r.append(el("span", "plate-mini", t.plate), el("span", "", t.owner), el("span", "count", t.count + "x"));
    box.append(r);
  });
}

function drawAlerts(alerts) {
  const box = $("#alerts");
  box.innerHTML = "";
  if (!alerts.length) {
    box.append(el("p", "muted", "No alerts. Every vehicle seen is in good standing."));
    return;
  }
  alerts.forEach((a) => {
    const r = el("div", "alert-row");
    r.append(el("span", "plate-mini", a.plate), el("span", "", a.owner), el("span", "tag", a.reason));
    box.append(r);
  });
}

async function load() {
  try {
    const d = await (await fetch("/api/stats")).json();
    const s = $("#stats");
    s.innerHTML = "";
    s.append(
      statCard("Total detections", d.total),
      statCard("Unique vehicles", d.unique),
      statCard("Registered", d.registered, "good"),
      statCard("Unknown", d.unknown, d.unknown ? "warn" : "")
    );
    drawBars(d.daily);
    drawDonut(d.registered, d.unknown);
    drawTop(d.top);
    drawAlerts(d.alerts);
  } catch (e) {
    console.error(e);
  }
}

load();
setInterval(load, 10000);