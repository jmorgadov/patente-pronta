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

document.addEventListener("DOMContentLoaded", () => {
  setupChapterPicker();
  setupCountPresets();
  setupHideAnswers();
  document.querySelectorAll("form[data-auto-submit]").forEach((form) => {
    form.addEventListener("change", () => form.submit());
  });
});
