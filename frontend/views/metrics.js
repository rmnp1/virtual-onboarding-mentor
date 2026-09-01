import { api, el, escapeHtml } from "../lib.js";

function fmtPercent(value) {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}%`;
}

function fmtRating(value) {
  if (value === null || value === undefined) return "—";
  return value.toFixed(1);
}

export const MetricsView = {
  async render(container) {
    container.innerHTML = `<h2>My progress</h2><p class="empty">Loading…</p>`;

    let data;
    try {
      data = await api("/api/metrics/me");
    } catch (err) {
      container.innerHTML = `<p class="empty">${escapeHtml(err instanceof Error ? err.message : "Failed to load")}</p>`;
      return;
    }

    const cards = [
      { label: "Scenarios", value: `${data.scenarios_completed}/${data.scenarios_total}` },
      { label: "Progress", value: fmtPercent(data.progress_percent) },
      { label: "Avg score", value: fmtPercent(data.avg_score_percent) },
      { label: "Avg rating", value: fmtRating(data.avg_rating) },
    ];

    const wrap = el(`
      <div class="metrics">
        <h2>My progress</h2>
        <div class="metric-row">
          ${cards
            .map(
              (c) => `
                <div class="metric-card">
                  <div class="metric-value">${escapeHtml(c.value)}</div>
                  <div class="metric-label">${escapeHtml(c.label)}</div>
                </div>`,
            )
            .join("")}
        </div>
        <table class="metrics-table">
          <thead>
            <tr>
              <th>Scenario</th>
              <th>Status</th>
              <th>Score</th>
              <th>Quizzes</th>
            </tr>
          </thead>
          <tbody>
            ${data.scenarios
              .map(
                (s) => `
                  <tr>
                    <td>${escapeHtml(s.title)}</td>
                    <td>${escapeHtml(s.status)}</td>
                    <td>${escapeHtml(fmtPercent(s.score_percent))}</td>
                    <td>${s.total_quizzes}</td>
                  </tr>`,
              )
              .join("")}
          </tbody>
        </table>
      </div>`);

    container.innerHTML = "";
    container.appendChild(wrap);
  },
};