"use strict";

async function saveLevel(control, url, body) {
  const reset = control.querySelector(".level-reset");
  control.classList.remove("failed");
  control.classList.add("saving");
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    markLevel(control, data.level);
    reset.hidden = data.level === data.default_level;
    control.classList.add("saved");
    setTimeout(() => control.classList.remove("saved"), 900);
  } catch {
    markLevel(control, control.dataset.level);
    control.classList.add("failed");
  } finally {
    control.classList.remove("saving");
  }
}

function markLevel(control, level) {
  control.dataset.level = level;
  control.querySelectorAll(".level-option").forEach((option) => {
    option.setAttribute("aria-checked", String(option.dataset.level === level));
  });
}

async function toggleSeen(button) {
  const seen = button.getAttribute("aria-pressed") !== "true";
  button.classList.remove("failed");
  markSeen(button, seen);
  try {
    const response = await fetch(`/api/questions/${button.dataset.questionId}/seen`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seen }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    markSeen(button, (await response.json()).seen);
  } catch {
    markSeen(button, !seen);
    button.classList.add("failed");
  }
}

function markSeen(button, seen) {
  button.setAttribute("aria-pressed", String(seen));
  button.title = seen ? "Vista" : "Non vista";
}

document.addEventListener("click", (event) => {
  const option = event.target.closest(".level-option");
  if (option) {
    const control = option.closest(".level-control");
    if (option.dataset.level === control.dataset.level) return;
    const id = control.dataset.questionId;
    markLevel(control, option.dataset.level);
    saveLevel(control, `/api/questions/${id}/level`, { level: option.dataset.level });
    return;
  }
  const reset = event.target.closest(".level-reset");
  if (reset) {
    const control = reset.closest(".level-control");
    saveLevel(control, `/api/questions/${control.dataset.questionId}/level/reset`, null);
    return;
  }
  const seen = event.target.closest(".seen-toggle");
  if (seen) {
    toggleSeen(seen);
    return;
  }
  const badge = event.target.closest(".answer-badge");
  if (badge) badge.classList.toggle("peek");
});

function setupChapterPicker() {
  const options = [...document.querySelectorAll('input[name="chapter"]')];
  const count = document.querySelector("[data-chapters-count]");
  if (!count) return;
  const sync = () => {
    count.textContent = `${options.filter((option) => option.checked).length}/${options.length}`;
  };
  const setAll = (checked) => {
    options.forEach((option) => { option.checked = checked; });
    sync();
  };
  options.forEach((option) => option.addEventListener("change", sync));
  document.querySelector("[data-chapters-all]")?.addEventListener("click", () => setAll(true));
  document.querySelector("[data-chapters-none]")?.addEventListener("click", () => setAll(false));
  sync();
}

function setupCountPresets() {
  const input = document.querySelector("#practice-count");
  document.querySelectorAll("[data-count-preset]").forEach((button) => {
    button.addEventListener("click", () => { input.value = button.dataset.countPreset; });
  });
}

function setupExclusiveToggles() {
  document.querySelectorAll("[data-excludes]").forEach((toggle) => {
    const excluded = toggle.form.elements.namedItem(toggle.dataset.excludes);
    const sync = () => {
      excluded.disabled = toggle.checked;
      if (toggle.checked) excluded.checked = false;
    };
    toggle.addEventListener("change", sync);
    sync();
  });
}

function setupHideAnswers() {
  const toggle = document.querySelector("[data-hide-answers]");
  if (!toggle) return;
  try {
    toggle.checked = localStorage.getItem("hideAnswers") === "1";
  } catch {
    toggle.checked = false;
  }
  const apply = () => document.body.classList.toggle("answers-hidden", toggle.checked);
  toggle.addEventListener("change", () => {
    apply();
    try {
      localStorage.setItem("hideAnswers", toggle.checked ? "1" : "0");
    } catch {
      /* storage unavailable: the toggle still works for this page */
    }
  });
  apply();
}

const MAX_ZOOM = 8;
const ZOOM_STEP = 1.5;

function setupLightbox() {
  const dialog = document.querySelector("[data-lightbox]");
  if (!dialog) return;
  const stage = dialog.querySelector(".lightbox-stage");
  const image = dialog.querySelector(".lightbox-image");
  const view = { scale: 1, x: 0, y: 0 };
  const pointers = new Map();
  let pinch = null;
  let dragged = false;

  const render = () => {
    image.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.scale})`;
    stage.classList.toggle("is-zoomed", view.scale > 1);
  };
  const clampPan = () => {
    const limitX = (image.offsetWidth * view.scale) / 2;
    const limitY = (image.offsetHeight * view.scale) / 2;
    view.x = Math.min(limitX, Math.max(-limitX, view.x));
    view.y = Math.min(limitY, Math.max(-limitY, view.y));
  };
  const zoomAt = (scale, clientX, clientY) => {
    const next = Math.min(MAX_ZOOM, Math.max(1, scale));
    const rect = stage.getBoundingClientRect();
    const offsetX = clientX - rect.left - rect.width / 2;
    const offsetY = clientY - rect.top - rect.height / 2;
    view.x = offsetX - ((offsetX - view.x) * next) / view.scale;
    view.y = offsetY - ((offsetY - view.y) * next) / view.scale;
    view.scale = next;
    if (next === 1) Object.assign(view, { x: 0, y: 0 });
    clampPan();
    render();
  };
  const zoomAtCenter = (scale) => {
    const rect = stage.getBoundingClientRect();
    zoomAt(scale, rect.left + rect.width / 2, rect.top + rect.height / 2);
  };
  const open = (figure) => {
    Object.assign(view, { scale: 1, x: 0, y: 0 });
    render();
    image.src = figure.currentSrc || figure.src;
    image.alt = figure.alt;
    dialog.showModal();
  };

  document.addEventListener("click", (event) => {
    const figure = event.target.closest("[data-zoomable]");
    if (figure) open(figure);
  });
  document.addEventListener("keydown", (event) => {
    const figure = event.target.closest?.("[data-zoomable]");
    if (!figure || (event.key !== "Enter" && event.key !== " ")) return;
    event.preventDefault();
    open(figure);
  });

  dialog.querySelectorAll("[data-zoom-step]").forEach((button) => {
    button.addEventListener("click", () => {
      zoomAtCenter(view.scale * ZOOM_STEP ** Number(button.dataset.zoomStep));
    });
  });
  dialog.querySelector("[data-zoom-reset]").addEventListener("click", () => zoomAtCenter(1));
  dialog.querySelector("[data-lightbox-close]").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => image.removeAttribute("src"));

  stage.addEventListener("wheel", (event) => {
    event.preventDefault();
    zoomAt(view.scale * Math.exp(-event.deltaY * 0.0015), event.clientX, event.clientY);
  }, { passive: false });
  stage.addEventListener("dblclick", (event) => {
    zoomAt(view.scale > 1 ? 1 : ZOOM_STEP ** 2, event.clientX, event.clientY);
  });
  stage.addEventListener("click", (event) => {
    if (event.target === stage && !dragged) dialog.close();
  });

  stage.addEventListener("pointerdown", (event) => {
    stage.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    dragged = false;
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = { distance: Math.hypot(a.x - b.x, a.y - b.y), scale: view.scale };
    }
  });
  stage.addEventListener("pointermove", (event) => {
    const previous = pointers.get(event.pointerId);
    if (!previous) return;
    const current = { x: event.clientX, y: event.clientY };
    pointers.set(event.pointerId, current);
    if (pinch && pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      const distance = Math.hypot(a.x - b.x, a.y - b.y);
      zoomAt((pinch.scale * distance) / pinch.distance, (a.x + b.x) / 2, (a.y + b.y) / 2);
      dragged = true;
      return;
    }
    if (view.scale === 1) return;
    view.x += current.x - previous.x;
    view.y += current.y - previous.y;
    dragged = dragged || Math.hypot(current.x - previous.x, current.y - previous.y) > 2;
    clampPan();
    render();
  });
  const release = (event) => {
    pointers.delete(event.pointerId);
    if (pointers.size < 2) pinch = null;
  };
  stage.addEventListener("pointerup", release);
  stage.addEventListener("pointercancel", release);
}

document.addEventListener("DOMContentLoaded", () => {
  setupLightbox();
  setupChapterPicker();
  setupCountPresets();
  setupExclusiveToggles();
  setupHideAnswers();
  document.querySelectorAll("form[data-auto-submit]").forEach((form) => {
    form.addEventListener("change", () => form.submit());
  });
});
