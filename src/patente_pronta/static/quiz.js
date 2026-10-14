"use strict";

const EXAM_ADVANCE_MS = 280;
const PRACTICE_ADVANCE_MS = { ok: 2000, ko: 3000, revealed: 3000 };

document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector(".quiz");
  if (!root) return;

  const isPractice = root.dataset.mode === "practice";
  const instant = isPractice && root.dataset.instantFeedback === "true";
  const cards = [...root.querySelectorAll(".question-card")];
  const cells = [...root.querySelectorAll(".strip-cell")];
  const submitForm = root.querySelector("[data-submit-form]");
  const prevButton = root.querySelector("[data-prev]");
  const nextButton = root.querySelector("[data-next]");
  const pending = new Set();
  let current = 0;
  let advanceTimer = null;
  let finishing = false;

  const isDone = (card) => card.dataset.given !== undefined || card.dataset.revealed === "true";
  const isCorrect = (card) => card.dataset.revealed !== "true" && card.dataset.given === card.dataset.answer;
  const label = (value) => (value === "true" ? "Vero" : "Falso");

  function show(index) {
    cancelAdvance();
    current = Math.max(0, Math.min(cards.length - 1, index));
    cards.forEach((card, i) => { card.hidden = i !== current; });
    cells.forEach((cell, i) => cell.classList.toggle("current", i === current));
    cells[current]?.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
    prevButton.disabled = current === 0;
    nextButton.disabled = current === cards.length - 1;
  }

  function render(card) {
    const given = card.dataset.given;
    const expected = card.dataset.answer;
    const done = instant && isDone(card);
    card.querySelectorAll(".answer-btn").forEach((button) => {
      const value = button.dataset.value;
      if (!instant) {
        button.classList.toggle("selected", value === given);
        return;
      }
      button.disabled = done;
      button.classList.toggle("correct", done && value === expected);
      button.classList.toggle("wrong", done && value === given && value !== expected);
      button.classList.toggle("dimmed", done && value !== expected && value !== given);
    });
    if (!instant) return;
    card.querySelector("[data-reveal-row]").hidden = done;
    const feedback = card.querySelector("[data-feedback]");
    feedback.hidden = !done;
    if (!done) return;
    const title = card.querySelector("[data-feedback-title]");
    const detail = card.querySelector("[data-feedback-detail]");
    if (card.dataset.revealed === "true") {
      feedback.className = "feedback ko";
      title.textContent = `La risposta è ${label(expected)}`;
      detail.textContent = "";
    } else if (isCorrect(card)) {
      feedback.className = "feedback ok";
      title.textContent = "Corretto!";
      detail.textContent = "";
    } else {
      feedback.className = "feedback ko";
      title.textContent = "Sbagliato";
      detail.textContent = `La risposta è ${label(expected)}`;
    }
  }

  function updateCounters() {
    const done = cards.filter(isDone);
    root.querySelector("[data-answered]").textContent = done.length;
    const progress = root.querySelector("[data-progress]");
    if (progress) progress.style.width = `${(100 * done.length) / cards.length}%`;
    cells.forEach((cell, i) => cell.classList.toggle("answered", isDone(cards[i])));
    if (!instant) return;
    const correct = done.filter(isCorrect).length;
    root.querySelector("[data-correct]").textContent = correct;
    root.querySelector("[data-wrong]").textContent = done.length - correct;
  }

  function post(url, body) {
    const request = fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((response) => {
      if (response.status === 409) submitForm.submit();
    });
    pending.add(request);
    request.finally(() => pending.delete(request));
  }

  function answer(value) {
    const card = cards[current];
    if (instant && isDone(card)) return;
    card.dataset.given = value;
    render(card);
    updateCounters();
    post(root.dataset.answerUrl, { position: Number(card.dataset.position), given: value === "true" });
    if (instant) {
      scheduleAdvance(isCorrect(card) ? PRACTICE_ADVANCE_MS.ok : PRACTICE_ADVANCE_MS.ko);
    } else {
      cancelAdvance();
      advanceTimer = setTimeout(nextExamQuestion, EXAM_ADVANCE_MS);
    }
  }

  function reveal() {
    const card = cards[current];
    if (!instant || isDone(card)) return;
    card.dataset.revealed = "true";
    render(card);
    updateCounters();
    post(root.dataset.revealUrl, { position: Number(card.dataset.position) });
    scheduleAdvance(PRACTICE_ADVANCE_MS.revealed);
  }

  function nextExamQuestion() {
    if (current < cards.length - 1) {
      show(current + 1);
      return;
    }
    const open = cards.findIndex((card) => !isDone(card));
    if (open !== -1) show(open);
  }

  function scheduleAdvance(ms) {
    cancelAdvance();
    const bar = cards[current].querySelector("[data-advance-bar]");
    bar.style.setProperty("--advance-ms", `${ms}ms`);
    bar.classList.remove("running");
    void bar.offsetWidth;
    bar.classList.add("running");
    advanceTimer = setTimeout(nextPracticeQuestion, ms);
  }

  function cancelAdvance() {
    clearTimeout(advanceTimer);
    advanceTimer = null;
    root.querySelectorAll("[data-advance-bar].running").forEach((bar) => bar.classList.remove("running"));
  }

  function nextPracticeQuestion() {
    const order = [...cards.keys()].map((offset) => (current + 1 + offset) % cards.length);
    const open = order.find((index) => !isDone(cards[index]));
    if (open === undefined) finish();
    else show(open);
  }

  function finish() {
    if (finishing) return;
    finishing = true;
    cancelAdvance();
    Promise.allSettled([...pending]).then(() => submitForm.submit());
  }

  root.addEventListener("click", (event) => {
    const button = event.target.closest(".answer-btn");
    if (button) answer(button.dataset.value);
    else if (event.target.closest("[data-reveal]")) reveal();
    else if (event.target.closest("[data-advance]")) nextPracticeQuestion();
    else if (event.target.closest("[data-goto]")) show(Number(event.target.closest("[data-goto]").dataset.goto));
  });
  root.addEventListener("pointerdown", (event) => {
    if (event.target.closest(".level-control")) cancelAdvance();
  });
  prevButton.addEventListener("click", () => show(current - 1));
  nextButton.addEventListener("click", () => show(current + 1));

  document.addEventListener("keydown", (event) => {
    if (event.target.closest("input, select, textarea") || event.ctrlKey || event.metaKey || event.altKey) return;
    const key = event.key.toLowerCase();
    if (key === "v") answer("true");
    else if (key === "f") answer("false");
    else if (key === "r") reveal();
    else if (key === "arrowleft") show(current - 1);
    else if (key === "arrowright") show(current + 1);
    else if (key === "enter" && instant && isDone(cards[current]) && !event.target.closest("button, a")) {
      nextPracticeQuestion();
    } else return;
    event.preventDefault();
  });

  submitForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const missing = cards.filter((card) => !isDone(card)).length;
    let question = `Hai ${missing} domande senza risposta, che conteranno come errori. Consegnare comunque?`;
    if (instant) {
      question = `Mancano ${missing} domande: se interrompi ora, l'esercitazione non verrà salvata nello storico. Interrompere?`;
    } else if (isPractice) {
      question = `Mancano ${missing} domande: se consegni ora, l'esercitazione non verrà salvata nello storico. Consegnare comunque?`;
    }
    if (missing > 0 && !window.confirm(question)) return;
    finish();
  });

  if (!isPractice) {
    const timer = root.querySelector("[data-timer]");
    const deadline = Date.now() + Number(root.dataset.remaining) * 1000;
    let handle = null;
    const tick = () => {
      const left = Math.max(0, Math.round((deadline - Date.now()) / 1000));
      const minutes = String(Math.floor(left / 60)).padStart(2, "0");
      const seconds = String(left % 60).padStart(2, "0");
      timer.textContent = `${minutes}:${seconds}`;
      timer.classList.toggle("warning", left <= 120);
      if (left === 0) {
        clearInterval(handle);
        finish();
      }
    };
    handle = setInterval(tick, 1000);
    tick();
  }

  cards.forEach(render);
  updateCounters();
  const firstOpen = cards.findIndex((card) => !isDone(card));
  show(firstOpen === -1 ? 0 : firstOpen);
  if (instant && firstOpen === -1) finish();
});
