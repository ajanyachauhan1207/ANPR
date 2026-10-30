const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

// ---------- helpers ----------
function showLoader(text) { $("#loaderText").textContent = text; $("#loader").classList.remove("hidden"); }
function hideLoader() { $("#loader").classList.add("hidden"); }
function clearResult() { const r = $("#result"); r.innerHTML = ""; r.classList.add("hidden"); }

function field(label, value, bad) {
  const r = document.createElement("div");
  r.className = "field";
  const l = document.createElement("span");
  l.className = "label"; l.textContent = label;
  const v = document.createElement("span");
  v.className = "value" + (bad ? " bad" : ""); v.textContent = value || "-";
  r.append(l, v);
  return r;
}

function infoCard(info) {
  const d = document.createElement("div");
  d.className = "info " + (info.found ? "ok" : "unknown");
  const head = document.createElement("div");
  head.className = "info-head";
  if (!info.found) head.textContent = "Not found in registry";
  else if (info.match === "probable") head.textContent = "Probable match (1 character differs from the registry)";
  else head.textContent = "Registered vehicle";
  d.appendChild(head);

  const grid = document.createElement("div");
  grid.className = "grid";
  grid.appendChild(field("State (from plate)", info.state));
  if (info.found) {
    const expired = info.insurance_until && new Date(info.insurance_until) < new Date();
    const flagged = info.status && info.status !== "Active";
    grid.append(
      field("Owner", info.owner),
      field("Vehicle", info.vehicle),
      field("Colour", info.color),
      field("Registered", info.reg_year),
      field("Insurance valid till",
            info.insurance_until ? info.insurance_until + (expired ? " (EXPIRED)" : "") : "-", expired),
      field("Status", info.status, flagged),
      field("Registered plate", info.registered_plate)
    );
  }
  d.appendChild(grid);
  return d;
}

function addBlock(items, image, note) {
  const r = $("#result");
  r.classList.remove("hidden");
  const block = document.createElement("div");
  block.className = "block";

  if (items.length) {
    items.forEach((it) => {
      const chips = document.createElement("div");
      chips.className = "plates";
      const c = document.createElement("span");
      c.className = "plate";
      c.textContent = it.plate || "?";
      chips.appendChild(c);
      if (note) {
        const n = document.createElement("span");
        n.className = "muted"; n.textContent = note;
        chips.appendChild(n);
      }
      block.appendChild(chips);
      block.appendChild(infoCard(it.info));
    });
  } else {
    const m = document.createElement("p");
    m.className = "muted";
    m.textContent = note || "No plate found in this image.";
    block.appendChild(m);
  }
  if (image) {
    const im = document.createElement("img");
    im.src = image;
    block.appendChild(im);
  }
  r.appendChild(block);
}

function logQuery() {
  const p = new URLSearchParams();
  if ($("#fQuery").value.trim()) p.set("q", $("#fQuery").value.trim());
  if ($("#fFrom").value) p.set("from", $("#fFrom").value);
  if ($("#fTo").value) p.set("to", $("#fTo").value);
  if ($("#fStatus").value) p.set("status", $("#fStatus").value);
  return p.toString();
}

async function loadLog() {
  const rows = await (await fetch("/api/log?" + logQuery())).json();
  const body = $("#logBody");
  body.innerHTML = "";
  $("#logCount").textContent =
    rows.length + (rows.length === 1 ? " detection shown" : " detections shown");
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="5" class="muted">No detections match.</td></tr>';
    return;
  }
  rows.forEach((r) => {
    const tr = document.createElement("tr");
    const cell = (v) => {
      const td = document.createElement("td");
      td.textContent = v;
      return td;
    };
    tr.append(cell(r.time), cell(r.plate));

    const tds = document.createElement("td");
    const tag = document.createElement("span");
    tag.className = "status " + r.status.toLowerCase().replace(/\s+/g, "-");
    tag.textContent = r.status;
    tds.appendChild(tag);
    tr.appendChild(tds);

    tr.appendChild(cell(r.source));

    const tdp = document.createElement("td");
    if (r.photo) {
      const img = document.createElement("img");
      img.className = "thumb";
      img.src = "/evidence/" + encodeURIComponent(r.photo);
      img.alt = "Evidence for " + r.plate;
      img.addEventListener("click", () => {
        $("#lightImg").src = img.src;
        $("#lightbox").classList.remove("hidden");
      });
      tdp.appendChild(img);
    } else {
      tdp.textContent = "-";
    }
    tr.appendChild(tdp);
    body.appendChild(tr);
  });
}

["#fQuery", "#fFrom", "#fTo", "#fStatus"].forEach((id) =>
  $(id).addEventListener("input", loadLog)
);
$("#fReset").addEventListener("click", () => {
  ["#fQuery", "#fFrom", "#fTo", "#fStatus"].forEach((id) => ($(id).value = ""));
  loadLog();
});


$("#lightbox").addEventListener("click", () => $("#lightbox").classList.add("hidden"));


// ---------- tabs ----------
$$(".tab").forEach((t) =>
  t.addEventListener("click", () => {
    $$(".tab").forEach((x) => x.classList.remove("active"));
    $$(".panel").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    $("#panel-" + t.dataset.tab).classList.add("active");
    if (t.dataset.tab !== "camera") stopCamera();
        if (t.dataset.tab !== "live") stopLive();
    clearResult();
  })
);

// ---------- drag & drop ----------
function setupDrop(dropId, inputId, onFile) {
  const drop = $(dropId), input = $(inputId);
  input.addEventListener("change", () => input.files[0] && onFile(input.files[0]));
  ["dragenter", "dragover"].forEach((e) =>
    drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((e) =>
    drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", (ev) => ev.dataTransfer.files[0] && onFile(ev.dataTransfer.files[0]));
}

// ---------- image ----------
async function sendImage(file) {
  clearResult();
  showLoader("Reading plate...");
  try {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/image", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Server error");
    addBlock(data.plates, data.image);
    loadLog();
  } catch (e) {
    alert(e.message);
  } finally {
    hideLoader();
  }
}
setupDrop("#dropImage", "#fileImage", sendImage);

// ---------- camera ----------
let stream = null;
async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
    $("#cam").srcObject = stream;
    $("#camStart").classList.add("hidden");
    $("#camCapture").classList.remove("hidden");
  } catch (e) {
    alert("Could not open the camera. Please allow camera access in your browser.");
  }
}
function stopCamera() {
  if (stream) stream.getTracks().forEach((t) => t.stop());
  stream = null;
  $("#cam").srcObject = null;
  $("#camStart").classList.remove("hidden");
  $("#camCapture").classList.add("hidden");
}
$("#camStart").addEventListener("click", startCamera);
$("#camCapture").addEventListener("click", () => {
  const v = $("#cam");
  const c = document.createElement("canvas");
  c.width = v.videoWidth; c.height = v.videoHeight;
  c.getContext("2d").drawImage(v, 0, 0);
  c.toBlob((blob) => sendImage(new File([blob], "capture.jpg", { type: "image/jpeg" })), "image/jpeg", 0.92);
});

// ---------- video ----------
let videoFile = null;
setupDrop("#dropVideo", "#fileVideo", (f) => { videoFile = f; $("#videoName").textContent = f.name; });
$("#step").addEventListener("input", (e) => ($("#stepVal").textContent = e.target.value));
$("#hits").addEventListener("input", (e) => ($("#hitsVal").textContent = e.target.value));

$("#videoGo").addEventListener("click", async () => {
  if (!videoFile) return alert("Choose a video first.");
  clearResult();
  showLoader("Processing video... this can take a few minutes");
  try {
    const fd = new FormData();
    fd.append("file", videoFile);
    fd.append("step", $("#step").value);
    fd.append("min_hits", $("#hits").value);
    const res = await fetch("/api/video", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Server error");
    if (!data.results.length) {
      addBlock([], null, "No plate was read reliably. Try 'must appear in' = 1 or a clearer video.");
    } else {
      data.results.forEach((r) =>
        addBlock([{ plate: r.plate, info: r.info }], r.image, `seen in ${r.frames} frames`));
    }
    loadLog();
  } catch (e) {
    alert(e.message);
  } finally {
    hideLoader();
  }
});

// ---------- detection log ----------
$("#clearLog").addEventListener("click", async () => {
  if (!confirm("Delete the whole detection log?")) return;
  await fetch("/api/clear", { method: "POST" });
  loadLog();
});

// ---------- vehicle registry ----------
async function loadVehicles() {
  const rows = await (await fetch("/api/vehicles")).json();
  const body = $("#vehBody");
  body.innerHTML = "";
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="6" class="muted">No vehicles registered yet.</td></tr>';
    return;
  }
  rows.forEach((v) => {
    const tr = document.createElement("tr");
    [v.plate, v.owner, v.vehicle, v.insurance_until, v.status].forEach((val) => {
      const td = document.createElement("td");
      td.textContent = val || "-";
      tr.appendChild(td);
    });
    const td = document.createElement("td");
    const b = document.createElement("button");
    b.className = "btn ghost small";
    b.textContent = "Delete";
    b.addEventListener("click", async () => {
      if (!confirm("Delete " + v.plate + "?")) return;
      await fetch("/api/vehicles/" + encodeURIComponent(v.plate), { method: "DELETE" });
      loadVehicles();
    });
    td.appendChild(b);
    tr.appendChild(td);
    body.appendChild(tr);
  });
}

$("#vehForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target));
  const res = await fetch("/api/vehicles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const out = await res.json();
  if (!res.ok) return alert(out.error || "Could not save");
  e.target.reset();
  loadVehicles();
});

loadLog();
loadVehicles();

// ---------- live scan ----------
let liveStream = null;
let liveRunning = false;

function clearOverlay() {
  const cv = $("#liveOverlay");
  cv.getContext("2d").clearRect(0, 0, cv.width, cv.height);
}

function drawBoxes(boxes, w, h) {
  const cv = $("#liveOverlay");
  cv.width = w;
  cv.height = h;
  const g = cv.getContext("2d");
  g.clearRect(0, 0, w, h);
  g.lineWidth = 3;
  g.strokeStyle = "#22d3a6";
  g.fillStyle = "#22d3a6";
  g.font = "bold 20px Segoe UI, sans-serif";
  boxes.forEach((b) => {
    const [x1, y1, x2, y2] = b.box;
    g.strokeRect(x1, y1, x2 - x1, y2 - y1);
    g.fillText(b.text, x1, Math.max(y1 - 8, 20));
  });
}

function addLiveEvent(ev) {
  const row = document.createElement("div");
  row.className = "live-row";
  const chip = document.createElement("span");
  chip.className = "plate-mini";
  chip.textContent = ev.plate;
  const who = document.createElement("span");
  who.textContent = ev.info.found
    ? ev.info.owner + " · " + ev.info.vehicle
    : "Not in registry";
  const time = document.createElement("span");
  time.className = "count";
  time.textContent = new Date().toLocaleTimeString();
  row.append(chip, who, time);
  $("#liveList").prepend(row);
}

async function liveLoop() {
  const v = $("#liveVideo");
  const grab = document.createElement("canvas");
  while (liveRunning) {
    if (v.videoWidth) {
      const w = 640;
      const h = Math.round((v.videoHeight / v.videoWidth) * w);
      grab.width = w;
      grab.height = h;
      grab.getContext("2d").drawImage(v, 0, 0, w, h);
      const blob = await new Promise((res) => grab.toBlob(res, "image/jpeg", 0.85));
      try {
        $("#liveStatus").textContent = "Scanning... hold the plate steady in view";
        const fd = new FormData();
        fd.append("file", blob, "frame.jpg");
        const res = await fetch("/api/frame", { method: "POST", body: fd });
        const data = await res.json();
        if (!liveRunning) break;
        if (res.ok) {
          drawBoxes(data.boxes || [], w, h);
          $("#liveCount").textContent = data.count;
          (data.events || []).forEach(addLiveEvent);
          if ((data.events || []).length) loadLog();
        }
      } catch (e) {
        $("#liveStatus").textContent = "Connection problem, retrying...";
      }
    }
    await new Promise((r) => setTimeout(r, 300));
  }
}

async function startLive() {
  try {
    liveStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment", width: { ideal: 1280 } },
    });
  } catch (e) {
    alert("Could not open the camera. Please allow camera access in your browser.");
    return;
  }
  const v = $("#liveVideo");
  v.srcObject = liveStream;
  await v.play().catch(() => {});
  await fetch("/api/live/reset", { method: "POST" });
  $("#liveCount").textContent = "0";
  $("#liveList").innerHTML = "";
  $("#liveStart").classList.add("hidden");
  $("#liveStop").classList.remove("hidden");
  liveRunning = true;
  liveLoop();
}

function stopLive() {
  liveRunning = false;
  if (liveStream) liveStream.getTracks().forEach((t) => t.stop());
  liveStream = null;
  $("#liveVideo").srcObject = null;
  clearOverlay();
  $("#liveStart").classList.remove("hidden");
  $("#liveStop").classList.add("hidden");
  $("#liveStatus").textContent = "Camera is off";
}

$("#liveStart").addEventListener("click", startLive);
$("#liveStop").addEventListener("click", stopLive);