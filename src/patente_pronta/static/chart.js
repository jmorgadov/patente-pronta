"use strict";

const SVG_NS = "http://www.w3.org/2000/svg";
const SERIES = [
  { mode: "exam", label: "Esame" },
  { mode: "practice", label: "Esercitazione" },
];
const MARGIN = { top: 16, right: 52, bottom: 34, left: 46 };
const Y_TICKS = [0, 25, 50, 75, 100];
const MAX_DOTS = 60;

function svgElement(name, attributes, parent) {
  const node = document.createElementNS(SVG_NS, name);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
  parent.appendChild(node);
  return node;
}

function textElement(content, attributes, parent) {
  const node = svgElement("text", attributes, parent);
  node.textContent = content;
  return node;
}

function setupChart(root) {
  const points = JSON.parse(root.querySelector("[data-chart-points]").textContent);
  const threshold = Number(root.dataset.threshold);
  const tooltip = document.createElement("div");
  tooltip.className = "chart-tooltip";
  tooltip.hidden = true;
  root.appendChild(tooltip);
  let scene = null;
  let active = null;

  function draw() {
    root.querySelector("svg")?.remove();
    const width = root.clientWidth;
    if (width < MARGIN.left + MARGIN.right + 40) return;
    const svg = svgElement("svg", {}, root);
    const height = svg.getBoundingClientRect().height;
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("aria-hidden", "true");
    const plotWidth = width - MARGIN.left - MARGIN.right;
    const plotHeight = height - MARGIN.top - MARGIN.bottom;
    const count = points.length;
    const x = (index) => MARGIN.left + (count === 1 ? plotWidth / 2 : (index * plotWidth) / (count - 1));
    const y = (percent) => MARGIN.top + (1 - percent / 100) * plotHeight;

    Y_TICKS.forEach((tick) => {
      svgElement("line", {
        x1: MARGIN.left, x2: MARGIN.left + plotWidth, y1: y(tick), y2: y(tick),
        class: tick === 0 ? "base-line" : "grid-line",
      }, svg);
      textElement(`${tick}%`, {
        x: MARGIN.left - 8, y: y(tick), class: "tick", "text-anchor": "end", "dominant-baseline": "middle",
      }, svg);
    });

    const maxTicks = Math.max(2, Math.floor(plotWidth / 80));
    const step = Math.max(1, Math.ceil(count / maxTicks));
    let previous = null;
    for (let index = 0; index < count; index += step) {
      const day = points[index].date.slice(0, 5);
      if (day === previous) continue;
      previous = day;
      textElement(day, { x: x(index), y: MARGIN.top + plotHeight + 22, class: "tick", "text-anchor": "middle" }, svg);
    }

    svgElement("line", {
      x1: MARGIN.left, x2: MARGIN.left + plotWidth, y1: y(threshold), y2: y(threshold), class: "threshold",
    }, svg);
    textElement(`Soglia ${Math.round(threshold)}%`, {
      x: MARGIN.left + 6, y: y(threshold) - 6, class: "threshold-label",
    }, svg);

    const crosshair = svgElement("line", {
      y1: MARGIN.top, y2: MARGIN.top + plotHeight, class: "crosshair", visibility: "hidden",
    }, svg);

    const dots = new Map();
    const endLabels = [];
    SERIES.forEach(({ mode }) => {
      const series = points.map((point, index) => ({ point, index })).filter(({ point }) => point.mode === mode);
      if (!series.length) return;
      if (series.length > 1) {
        const path = series.map(({ point, index }, i) => `${i ? "L" : "M"}${x(index)},${y(point.percent)}`).join(" ");
        svgElement("path", { d: path, class: `series series-${mode}` }, svg);
      }
      series.forEach(({ point, index }, i) => {
        const isLast = i === series.length - 1;
        if (!isLast && count > MAX_DOTS) return;
        dots.set(index, svgElement("circle", {
          cx: x(index), cy: y(point.percent), r: 4, class: `dot dot-${mode}`,
        }, svg));
      });
      const last = series[series.length - 1];
      endLabels.push({ x: x(last.index), y: y(last.point.percent), text: `${Math.round(last.point.percent)}%` });
    });

    if (endLabels.length === 2 && Math.abs(endLabels[0].y - endLabels[1].y) < 16
        && Math.abs(endLabels[0].x - endLabels[1].x) < 48) {
      const upper = endLabels[0].y <= endLabels[1].y ? endLabels[0] : endLabels[1];
      upper.y -= 16 - Math.abs(endLabels[0].y - endLabels[1].y);
    }
    endLabels.forEach((label) => {
      const fits = label.x + 44 <= width;
      textElement(label.text, {
        x: fits ? label.x + 9 : label.x - 9,
        y: fits ? label.y : label.y - 12,
        class: "end-label",
        "text-anchor": fits ? "start" : "end",
        "dominant-baseline": "middle",
      }, svg);
    });

    const hit = svgElement("rect", {
      x: MARGIN.left - 12, y: MARGIN.top, width: plotWidth + 24, height: plotHeight, class: "hit",
    }, svg);
    hit.addEventListener("pointermove", (event) => {
      const box = svg.getBoundingClientRect();
      const px = event.clientX - box.left;
      const index = count === 1 ? 0 : Math.round(((px - MARGIN.left) * (count - 1)) / plotWidth);
      highlight(Math.max(0, Math.min(count - 1, index)));
    });
    hit.addEventListener("pointerleave", () => { if (document.activeElement !== root) highlight(null); });
    hit.addEventListener("click", () => { if (active !== null) window.location.href = points[active].url; });

    scene = { x, y, width, crosshair, dots };
    if (active !== null) highlight(active);
  }

  function highlight(index) {
    if (scene === null) return;
    scene.dots.forEach((dot) => dot.setAttribute("r", 4));
    active = index;
    if (index === null) {
      scene.crosshair.setAttribute("visibility", "hidden");
      tooltip.hidden = true;
      return;
    }
    const point = points[index];
    const px = scene.x(index);
    scene.crosshair.setAttribute("x1", px);
    scene.crosshair.setAttribute("x2", px);
    scene.crosshair.setAttribute("visibility", "visible");
    scene.dots.get(index)?.setAttribute("r", 6);

    tooltip.replaceChildren();
    const value = document.createElement("strong");
    value.textContent = `${point.correct}/${point.total} · ${Math.round(point.percent)}%`;
    const series = document.createElement("span");
    series.className = "tooltip-series";
    const key = document.createElement("span");
    key.className = `line-key key-${point.mode}`;
    series.append(key, SERIES.find(({ mode }) => mode === point.mode).label);
    const date = document.createElement("span");
    date.className = "tooltip-date";
    date.textContent = point.date;
    tooltip.append(value, series, date);
    tooltip.hidden = false;
    const tooltipWidth = tooltip.offsetWidth;
    const left = px + 14 + tooltipWidth > scene.width ? px - 14 - tooltipWidth : px + 14;
    tooltip.style.left = `${Math.max(0, left)}px`;
    tooltip.style.top = `${Math.max(0, scene.y(point.percent) - tooltip.offsetHeight / 2)}px`;
  }

  root.addEventListener("focus", () => highlight(active ?? points.length - 1));
  root.addEventListener("blur", () => highlight(null));
  root.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") highlight(Math.max(0, (active ?? 0) - 1));
    else if (event.key === "ArrowRight") highlight(Math.min(points.length - 1, (active ?? -1) + 1));
    else if (event.key === "Enter" && active !== null) window.location.href = points[active].url;
    else return;
    event.preventDefault();
  });

  new ResizeObserver(() => draw()).observe(root);
  draw();
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-chart]").forEach(setupChart);
});
