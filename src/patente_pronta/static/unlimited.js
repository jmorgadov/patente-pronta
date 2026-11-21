"use strict";

const ADVANCE_MS = { ok: 1500, ko: 3000 };

document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-unlimited]");
  if (!root) return;

  const slot = root.querySelector("[data-card-slot]");
  const submitForm = root.querySelector("[data-submit-form]");
  let card = slot.querySelector(".question-card");
  let upcoming = null;
  let advanceTimer = null;
  let advanceWanted = false;
  let finishing = false;

  const label = (value) => (value === "true" ? "Vero" : "Falso");
  const isDone = () => card.dataset.given !== undefined || card.dataset.revealed === "true";
  const isCorrect = () => card.dataset.revealed !== "true" && card.dataset.given === card.dataset.answer;

  function render() {
    const given = card.dataset.given;
    const expected = card.dataset.answer;
    card.querySelectorAll(".answer-btn").forEach((button) => {
      const value = button.dataset.value;
      button.disabled = true;
      button.classList.toggle("correct", value === expected);
      button.classList.toggle("wrong", value === given && value !== expected);
      button.classList.toggle("dimmed", value !== expected && value !== given);
    });
    card.querySelector("[data-reveal-row]").hidden = true;
    const feedback = card.querySelector("[data-feedback]");
    const title = card.querySelector("[data-feedback-title]");
    const detail = card.querySelector("[data-feedback-detail]");
    feedback.hidden = false;
    if (card.dataset.revealed === "true") {
      feedback.className = "feedback ko";
      title.textContent = `La risposta è ${label(expected)}`;
      detail.textContent = "";
    } else if (isCorrect()) {
      feedback.className = "feedback ok";
      title.textContent = "Corretto!";
      detail.textContent = "";
    } else {
      feedback.className = "feedback ko";
      title.textContent = "Sbagliato";
      detail.textContent = `La risposta è ${label(expected)}`;
    }
  }

  function updateStats(html) {
    root.querySelector("[data-run-stats]").outerHTML = html;
  }

  function send(url, body) {
    upcoming = fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    }).then((next) => {
      updateStats(next.stats_html);
      return next;
    }).catch(() => {
      window.location.reload();
      return null;
    });
  }

  function answer(value) {
    if (isDone() || finishing) return;
    card.dataset.given = value;
    render();
    send(root.dataset.answerUrl, { position: Number(card.dataset.position), given: value === "true" });
    scheduleAdvance(isCorrect() ? ADVANCE_MS.ok : ADVANCE_MS.ko);
  }

  function reveal() {
    if (isDone() || finishing) return;
    card.dataset.revealed = "true";
    render();
    send(root.dataset.revealUrl, { position: Number(card.dataset.position) });
    scheduleAdvance(ADVANCE_MS.ko);
  }

  function scheduleAdvance(ms) {
    cancelAdvance();
    const bar = card.querySelector("[data-advance-bar]");
    bar.style.setProperty("--advance-ms", `${ms}ms`);
    bar.classList.remove("running");
    void bar.offsetWidth;
    bar.classList.add("running");
    advanceTimer = setTimeout(advance, ms);
  }

  function cancelAdvance() {
    clearTimeout(advanceTimer);
    advanceTimer = null;
    card.querySelector("[data-advance-bar]")?.classList.remove("running");
  }

  function advance() {
    if (!isDone() || advanceWanted || finishing) return;
    cancelAdvance();
    advanceWanted = true;
    upcoming.then((next) => {
      advanceWanted = false;
      if (!next || finishing) return;
      slot.innerHTML = next.card;
      card = slot.querySelector(".question-card");
      upcoming = null;
    });
  }

  function finish() {
    if (finishing) return;
    finishing = true;
    cancelAdvance();
    Promise.allSettled([upcoming]).then(() => submitForm.submit());
  }

  root.addEventListener("click", (event) => {
    const button = event.target.closest(".answer-btn");
    if (button) answer(button.dataset.value);
    else if (event.target.closest("[data-reveal]")) reveal();
    else if (event.target.closest("[data-advance]")) advance();
  });
  root.addEventListener("pointerdown", (event) => {
    if (event.target.closest(".level-control")) cancelAdvance();
  });

  document.addEventListener("keydown", (event) => {
    if (event.target.closest("input, select, textarea") || event.ctrlKey || event.metaKey || event.altKey) return;
    const key = event.key.toLowerCase();
    if (key === "v") answer("true");
    else if (key === "f") answer("false");
    else if (key === "r") reveal();
    else if (key === "enter" && isDone() && !event.target.closest("button, a")) advance();
    else return;
    event.preventDefault();
  });

  submitForm.addEventListener("submit", (event) => {
    event.preventDefault();
    finish();
  });
});
