// SnapList frontend (vanilla JS). All dynamic text goes through textContent / value,
// never innerHTML, because it comes from an AI model.
const $ = (sel) => document.querySelector(sel);
const CONDITIONS = ["new", "new_boxed", "used_excellent", "used_good", "used_fair", "used_poor"];
const CHANNELS = ["ebay", "facebook", "craigslist"];

function h(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "class") e.className = v;
    else if (k === "value") e.value = v;
    else if (k in e && k !== "list") e[k] = v;
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false && kid !== true) e.append(kid.nodeType ? kid : document.createTextNode(kid));
  return e;
}

async function api(path, opts = {}) {
  if (opts.json !== undefined) {
    opts = { method: opts.method || "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(opts.json) };
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { const d = (await res.json()).detail; msg = typeof d === "string" ? d : JSON.stringify(d); } catch {}
    throw new Error(msg);
  }
  return res.json();
}

let toastTimer;
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 4000);
}
const guard = (fn) => async (...a) => { try { return await fn(...a); } catch (e) { toast(e.message); } };

let currentBatch = null;   // batch id
let batchData = null;      // last fetched batch detail
let pollTimer = null;
let dragPhoto = null;      // {id, itemId}

// ------------------------------------------------------------------ health
guard(async () => {
  const hh = await api("/health");
  $("#health").textContent = `llm=${hh.llm} · ${hh.bind}`;
})();

// ----------------------------------------------------------------- uploading
const drop = $("#drop"), filesInput = $("#files");
$("#pickBtn").onclick = () => filesInput.click();
filesInput.onchange = () => showPreview(Array.from(filesInput.files));
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("drag"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("drag"); }));
drop.addEventListener("drop", (e) => {
  const files = Array.from(e.dataTransfer?.files || []).filter((f) => f.type.startsWith("image/"));
  if (files.length) showPreview(files);
});

function showPreview(files) {
  const prev = $("#preview"); prev.replaceChildren();
  files.slice(0, 40).forEach((f) => prev.append(h("img", { src: URL.createObjectURL(f), alt: "" })));
  if (files.length) {
    const btn = h("button", { class: "primary" }, `Upload ${files.length} photo(s)`);
    btn.onclick = guard(async () => {
      btn.disabled = true; btn.textContent = "Uploading…";
      const fd = new FormData(); files.forEach((f) => fd.append("files", f));
      try {
        const r = await api("/batches", { method: "POST", body: fd });
        if (r.skipped.length) toast("Skipped: " + r.skipped.join("; "));
        prev.replaceChildren(); filesInput.value = "";
        await loadBatchList(); await selectBatch(r.batch_id);
      } finally { btn.disabled = false; }
    });
    prev.append(h("div", {}, btn));
  }
}

// -------------------------------------------------------------- batch sidebar
async function loadBatchList() {
  const { batches } = await api("/batches");
  const list = $("#batchList"); list.replaceChildren();
  if (!batches.length) list.append(h("p", { class: "hint" }, "No batches yet."));
  for (const b of batches) {
    const when = b.created_at ? new Date(b.created_at).toLocaleString() : "";
    list.append(h("div", { class: "brow" + (b.id === currentBatch ? " sel" : ""), onclick: guard(() => selectBatch(b.id)) },
      b.cover_photo ? h("img", { src: `/photos/${b.cover_photo}/thumb`, alt: "", loading: "lazy" }) : h("div", { class: "noimg" }),
      h("div", {},
        h("div", {}, `Batch ${b.id} `, h("span", { class: "badge " + b.status }, b.status)),
        h("div", { class: "meta" }, `${b.items} item(s) · ${b.approved} approved${b.processing ? ` · ${b.processing} processing…` : ""}${b.failed ? ` · ${b.failed} failed` : ""}`),
        h("div", { class: "meta" }, when))));
  }
}

async function selectBatch(id) {
  currentBatch = id;
  await refreshBatch(true);
  loadBatchList();
}

// ---------------------------------------------------------------- batch view
async function refreshBatch(full) {
  if (currentBatch == null) return;
  const data = await api(`/batches/${currentBatch}`);
  batchData = data;
  if (full) renderBatch(); else patchBatch();
  loadBatchList();
  clearTimeout(pollTimer);
  if (data.items.some((i) => i.status === "processing") || (data.status === "processing" && !data.items.length)) {
    pollTimer = setTimeout(guard(() => refreshBatch(false)), 2000);
  }
}

function renderBatch() {
  const main = $("#main"); main.replaceChildren();
  const b = batchData;
  const approvable = b.items.filter((i) => i.status === "ready" && !i.problems.length);
  main.append(h("div", { class: "bhead" },
    h("h3", {}, `Batch ${b.id}`), h("span", { class: "badge " + b.status }, b.status),
    h("span", { class: "meta" }, `${b.items.length} item(s), ${b.items.filter((i) => i.status === "approved").length} approved`),
    h("span", { class: "sp" }),
    h("button", { class: "good", disabled: !approvable.length, onclick: guard(async () => {
      for (const i of approvable) await api(`/items/${i.id}/approve`, { method: "POST" });
      toast(`Approved ${approvable.length} item(s)`); await refreshBatch(true);
    }) }, `Approve all clean (${approvable.length})`),
    h("button", { class: "danger", onclick: guard(async () => {
      if (!confirm(`Delete batch ${b.id}, all its items and photos?`)) return;
      await api(`/batches/${b.id}`, { method: "DELETE" });
      currentBatch = null; main.replaceChildren(h("p", { class: "hint empty" }, "Batch deleted.")); loadBatchList();
    }) }, "Delete batch")));
  const wrap = h("div", { class: "items", id: "items" });
  b.items.forEach((it) => wrap.append(renderItem(it)));
  main.append(wrap);
}

// Poll update: swap in only cards whose server state changed, never cards being edited.
function patchBatch() {
  const wrap = $("#items");
  if (!wrap) return renderBatch();
  const known = new Set();
  for (const it of batchData.items) {
    known.add(String(it.id));
    const old = wrap.querySelector(`.item[data-id="${it.id}"]`);
    if (!old) { wrap.append(renderItem(it)); continue; }
    if (old.dataset.status !== it.status && !old.classList.contains("dirty")) old.replaceWith(renderItem(it));
    else if (old.dataset.status !== it.status) old.dataset.status = it.status;
  }
  wrap.querySelectorAll(".item").forEach((n) => { if (!known.has(n.dataset.id)) n.remove(); });
}

function replaceItem(card, item) {
  const idx = batchData.items.findIndex((i) => i.id === item.id);
  if (idx >= 0) batchData.items[idx] = item;
  const fresh = renderItem(item);
  card.replaceWith(fresh);
  if (item.status === "processing") { loadBatchList(); clearTimeout(pollTimer); pollTimer = setTimeout(guard(() => refreshBatch(false)), 1500); }
}

// ------------------------------------------------------------------ item card
function renderItem(item) {
  const busy = item.status === "processing";
  const card = h("div", { class: "item " + item.status, "data-id": item.id, "data-status": item.status });
  const markDirty = () => card.classList.add("dirty");
  const f = item.facts || {};

  const title = f.item_type ? [f.brand && f.brand !== "unknown" ? f.brand : "", f.item_type].filter(Boolean).join(" ") : "Unidentified item";
  card.append(h("div", { class: "ihead" },
    h("h3", {}, title), h("span", { class: "badge " + item.status }, item.status),
    busy && h("span", { class: "spin" }),
    h("span", { class: "sp" }),
    item.status === "approved"
      ? h("button", { onclick: guard(async () => replaceItem(card, await api(`/items/${item.id}/unapprove`, { method: "POST" }))) }, "Un-approve")
      : h("button", { class: "good", disabled: busy, onclick: guard(async () => {
          if (card.classList.contains("dirty")) await save();
          replaceItem(card, await api(`/items/${item.id}/approve`, { method: "POST" }));
        }) }, "Approve")));

  if (item.error) card.append(h("div", { class: "err" }, "⚠ " + item.error));

  // photos ---------------------------------------------------------------
  const strip = h("div", { class: "strip" });
  const others = () => batchData.items.filter((i) => i.id !== item.id);
  item.photos.forEach((p) => {
    const move = h("select", { title: "Move to another item", disabled: busy, onchange: guard(async (e) => {
      const v = e.target.value; if (!v) return;
      await movePhoto(p.id, v === "new" ? null : Number(v));
    }), style: "width:auto;max-width:60px;padding:0;font-size:12px" },
      h("option", { value: "" }, "⇄"), h("option", { value: "new" }, "→ new item"),
      others().map((o) => h("option", { value: o.id }, `→ item ${o.id}`)));
    strip.append(h("div", { class: "ph" + (p.is_cover ? " cover" : ""), draggable: !busy, "data-photo": p.id,
      ondragstart: () => { dragPhoto = { id: p.id, itemId: item.id }; } ,
      ondragend: () => { dragPhoto = null; document.querySelectorAll(".drop-target").forEach((n) => n.classList.remove("drop-target")); } },
      h("img", { src: `/photos/${p.id}/thumb`, alt: "", loading: "lazy", onclick: () => openLightbox(p.id) }),
      p.is_cover && h("span", { class: "star", title: "Cover photo" }, "★"),
      h("div", { class: "tools" },
        h("button", { title: "Make cover", disabled: busy, onclick: guard(async () => replaceItem(card, await api(`/photos/${p.id}/cover`, { method: "POST" }))) }, "★"),
        move,
        h("button", { title: "Delete photo", disabled: busy, onclick: guard(async () => {
          if (!confirm("Delete this photo?")) return;
          replaceItem(card, await api(`/photos/${p.id}`, { method: "DELETE" }));
        }) }, "✕"))));
  });
  const addInput = h("input", { type: "file", accept: "image/*", multiple: true, hidden: true, onchange: guard(async () => {
    const fd = new FormData(); Array.from(addInput.files).forEach((x) => fd.append("files", x));
    const out = await api(`/items/${item.id}/photos`, { method: "POST", body: fd });
    if (out.skipped?.length) toast("Skipped: " + out.skipped.join("; "));
    else toast("Photos added. Click “Re-analyze photos” so the AI uses them.");
    replaceItem(card, out);
  }) });
  strip.append(h("button", { class: "addph", disabled: busy, title: "Add photos to this item", onclick: () => addInput.click() }, "+ photos"), addInput);
  card.append(strip);

  // drop target: move a dragged photo here
  card.addEventListener("dragover", (e) => { if (dragPhoto && dragPhoto.itemId !== item.id) { e.preventDefault(); card.classList.add("drop-target"); } });
  card.addEventListener("dragleave", (e) => { if (e.target === card) card.classList.remove("drop-target"); });
  card.addEventListener("drop", guard(async (e) => {
    e.preventDefault(); card.classList.remove("drop-target");
    if (dragPhoto && dragPhoto.itemId !== item.id) await movePhoto(dragPhoto.id, item.id);
  }));

  // details + listings ---------------------------------------------------
  const inp = {};
  const field = (key, label, el) => { inp[key] = el; el.addEventListener("input", markDirty); return [h("label", {}, label), el]; };
  const txt = (v) => h("input", { type: "text", value: v ?? "", disabled: busy });
  const lines = (v) => h("textarea", { value: (v || []).join("\n"), disabled: busy, style: "min-height:52px" });
  const cond = h("select", { disabled: busy }, CONDITIONS.map((c) => h("option", { value: c, selected: c === f.condition }, c.replace("_", " "))));
  const sites = h("div", { class: "sites" }, CHANNELS.map((c) => {
    const cb = h("input", { type: "checkbox", checked: item.sites.includes(c), disabled: busy, "data-site": c, onchange: markDirty });
    return h("label", {}, cb, c);
  }));
  const details = h("div", { class: "grid2" },
    field("item_type", "Item", txt(f.item_type)), field("brand", "Brand", txt(f.brand === "unknown" ? "" : f.brand)),
    field("model", "Model", txt(f.model === "unknown" ? "" : f.model)), field("color", "Color", txt(f.color)),
    field("size", "Size", txt(f.size)), field("condition", "Condition", cond),
    field("flaws", "Flaws (one per line)", lines(f.flaws)), field("included", "Included (one per line)", lines(f.included)),
    field("price", "Price (USD)", h("input", { type: "number", min: "0", step: "0.01", value: item.price ?? "", disabled: busy, placeholder: "required" })),
    h("label", { class: "top" }, "Post to"), sites,
    field("notes", "Tell the AI", h("textarea", { value: item.notes, disabled: busy, placeholder: "Anything the photos can't show: model number, works perfectly, dimensions, why selling…" })));
  details.querySelectorAll("label").forEach((l) => { if (l.textContent.includes("(one per line)") || l.textContent === "Tell the AI") l.classList.add("top"); });

  const qbox = h("div", {});
  item.questions.forEach((q) => {
    const a = h("input", { type: "text", value: q.answer ?? "", disabled: busy, placeholder: "answer (optional)" });
    a.onchange = guard(async () => { replaceItem(card, await api(`/items/${item.id}/answer`, { json: { question_id: q.id, answer: a.value } })); });
    qbox.append(h("div", { class: "q" }, h("label", {}, q.question), a));
  });

  const lbox = h("div", {});
  const origListing = {};
  item.listings.forEach((l) => {
    origListing[l.id] = { title: l.title, body: l.body };
    const t = h("input", { type: "text", value: l.title, disabled: busy });
    const b = h("textarea", { value: l.body, disabled: busy });
    const count = h("span", { class: "count" });
    const upd = () => { count.textContent = `${t.value.length}${l.title_max ? "/" + l.title_max : ""}`; count.classList.toggle("over", !!l.title_max && t.value.length > l.title_max); };
    t.addEventListener("input", () => { upd(); markDirty(); }); b.addEventListener("input", markDirty); upd();
    t.dataset.listing = l.id; b.dataset.listing = l.id;
    lbox.append(h("div", { class: "listing" },
      h("h4", {}, l.channel, l.status === "failed" && h("span", { class: "badge failed" }, "failed"), count),
      l.errors.length > 0 && h("div", { class: "err" }, l.errors.join("; ")),
      t, h("div", { style: "height:6px" }), b,
      h("div", { class: "actions" }, h("button", { onclick: guard(async () => {
        const txt = await (await fetch(`/channels/${item.id}/${l.channel}/packet`)).text();
        await navigator.clipboard.writeText(txt); toast(`${l.channel} packet copied`);
      }) }, "Copy packet"))));
  });
  if (!item.listings.length) lbox.append(h("p", { class: "hint" }, busy ? "Writing listings…" : "No listings yet."));

  card.append(h("div", { class: "cols" }, h("div", {}, details, item.questions.length > 0 && h("h2", { style: "margin-top:12px" }, "Open questions"), qbox), lbox));

  if (item.problems.length && item.status !== "approved") {
    card.append(h("ul", { class: "problems" }, item.problems.map((p) => h("li", {}, p))));
  }

  // actions --------------------------------------------------------------
  async function save() {
    const sel = [...card.querySelectorAll("[data-site]")].filter((c) => c.checked).map((c) => c.dataset.site);
    const price = inp.price.value.trim();
    const body = {
      facts: {
        item_type: inp.item_type.value.trim(), brand: inp.brand.value.trim() || "unknown", model: inp.model.value.trim() || "unknown",
        color: inp.color.value.trim(), size: inp.size.value.trim() || null, condition: inp.condition.value,
        flaws: inp.flaws.value.split("\n"), included: inp.included.value.split("\n"),
      },
      notes: inp.notes.value, sites: sel, clear_price: price === "",
    };
    if (price !== "") body.price = Number(price);
    await api(`/items/${item.id}`, { method: "PATCH", json: body });
    for (const l of item.listings) {
      const t = card.querySelector(`input[data-listing="${l.id}"]`), b = card.querySelector(`textarea[data-listing="${l.id}"]`);
      if (t.value !== origListing[l.id].title || b.value !== origListing[l.id].body)
        await api(`/listings/${l.id}`, { method: "PATCH", json: { title: t.value, body: b.value } });
    }
    return api(`/items/${item.id}`);
  }
  const listingEdited = () => item.listings.some((l) => {
    const t = card.querySelector(`input[data-listing="${l.id}"]`), b = card.querySelector(`textarea[data-listing="${l.id}"]`);
    return t.value !== origListing[l.id].title || b.value !== origListing[l.id].body;
  });
  const rewriteWarn = () => !listingEdited() || confirm("This overwrites your manual listing edits. Continue?");

  card.append(h("div", { class: "actions" },
    h("button", { class: "primary", disabled: busy, onclick: guard(async () => { replaceItem(card, await save()); toast("Saved"); }) }, "Save changes"),
    h("button", { disabled: busy, title: "Look at all current photos again (and your notes), then rewrite the listings", onclick: guard(async () => {
      if (!rewriteWarn()) return;
      await api(`/items/${item.id}`, { method: "PATCH", json: { notes: inp.notes.value } });
      replaceItem(card, await api(`/items/${item.id}/reanalyze`, { method: "POST" }).then(() => api(`/items/${item.id}`)));
    }) }, "Re-analyze photos"),
    h("button", { disabled: busy, title: "Rewrite listing text from the details above, without looking at photos", onclick: guard(async () => {
      if (!rewriteWarn()) return;
      await save();
      replaceItem(card, await api(`/items/${item.id}/regenerate`, { method: "POST" }).then(() => api(`/items/${item.id}`)));
    }) }, "Rewrite text"),
    others().length > 0 && h("select", { style: "width:auto", disabled: busy, onchange: guard(async (e) => {
      const to = Number(e.target.value); e.target.value = ""; if (!to) return;
      if (!confirm(`Merge all photos of this item into item ${to}? Re-analyze it afterwards.`)) return;
      await api(`/items/${item.id}/merge`, { json: { into: to } }); await refreshBatch(true);
    }) }, h("option", { value: "" }, "Merge into…"), others().map((o) => h("option", { value: o.id }, `item ${o.id}`))),
    h("span", { class: "sp", style: "flex:1" }),
    h("button", { class: "danger", disabled: busy, onclick: guard(async () => {
      if (!confirm("Delete this item and its photos?")) return;
      await api(`/items/${item.id}`, { method: "DELETE" }); await refreshBatch(true);
    }) }, "Delete item")));
  return card;
}

async function movePhoto(photoId, toItem) {
  const r = await api(`/photos/${photoId}/move`, { json: { item_id: toItem } });
  toast(toItem === null ? "Split into a new item (analyzing…)" : "Photo moved. Re-analyze the item(s) to refresh descriptions.");
  await refreshBatch(true);
  return r;
}

function openLightbox(id) {
  const lb = $("#lightbox"); lb.querySelector("img").src = `/photos/${id}/file`; lb.hidden = false;
}
$("#lightbox").onclick = () => { $("#lightbox").hidden = true; };
document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("#lightbox").hidden = true; });

guard(async () => {
  await loadBatchList();
  const first = document.querySelector(".brow");
  if (first) first.click();
})();
