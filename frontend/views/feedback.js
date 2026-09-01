import { api, el, escapeHtml, showToast } from "../lib.js";

function formatDate(value) {
  if (!value) return "";
  const iso = /Z$|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`;
  const date = new Date(iso);
  return isNaN(date.getTime()) ? "" : date.toLocaleString();
}

export const FeedbackView = {
  async render(container) {
    container.innerHTML = `<h2>Feedback</h2><p class="empty">Loading…</p>`;

    let scenarios;
    try {
      scenarios = await api("/api/scenarios");
    } catch {
      scenarios = [];
    }

    const wrap = el(`
      <div class="fb">
        <h2>Share feedback</h2>
        <form class="card" id="fb-form">
          <label>Overall rating
            <div class="rating-row" id="stars"></div>
          </label>
          <label>Topic
            <select name="scenario_id">
              <option value="">General feedback about the mentor</option>
              ${scenarios
                .map((s) => `<option value="${escapeHtml(s.id)}">${escapeHtml(s.title)}</option>`)
                .join("")}
            </select>
          </label>
          <label>Comment (optional)
            <textarea name="comment"></textarea>
          </label>
          <button type="submit" class="primary">Submit</button>
        </form>
        <h2>Your entries</h2>
        <div id="fb-list" class="card"><p class="empty">Loading…</p></div>
      </div>`);

    container.innerHTML = "";
    container.appendChild(wrap);

    const form = wrap.querySelector("#fb-form");
    const starsRow = wrap.querySelector("#stars");
    let rating = 0;
    for (let i = 1; i <= 5; i += 1) {
      const star = el(`<button type="button" class="star" data-value="${i}" title="${i}">${i} star${i > 1 ? "s" : ""}</button>`);
      star.addEventListener("click", () => {
        rating = i;
        starsRow.querySelectorAll(".star").forEach((s) => s.classList.toggle("selected", Number(s.dataset.value) <= rating));
      });
      starsRow.appendChild(star);
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!rating) {
        showToast("Pick a rating first", true);
        return;
      }
      const fd = new FormData(form);
      const submit = form.querySelector("button[type=submit]");
      submit.disabled = true;
      try {
        await api("/api/feedback", {
          method: "POST",
          body: {
            rating,
            scenario_id: String(fd.get("scenario_id") || "") || null,
            comment: String(fd.get("comment") || "").trim() || null,
          },
        });
        showToast("Thank you for the feedback");
        form.reset();
        rating = 0;
        starsRow.querySelectorAll(".star").forEach((s) => s.classList.remove("selected"));
        await loadList();
      } catch (err) {
        showToast(err instanceof Error ? err.message : "Submit failed", true);
      } finally {
        submit.disabled = false;
      }
    });

    async function loadList() {
      const listEl = wrap.querySelector("#fb-list");
      try {
        const list = await api("/api/feedback");
        if (!list.length) {
          listEl.innerHTML = `<p class="empty">No feedback yet.</p>`;
          return;
        }
        listEl.innerHTML = list
          .map(
            (f) => `
              <div class="fb-item">
                <span class="fb-rating">${f.rating}/5</span>
                ${f.scenario_id ? `<span class="fb-scenario">${escapeHtml(f.scenario_id)}</span>` : ""}
                ${f.comment ? `<div class="fb-comment">${escapeHtml(f.comment)}</div>` : ""}
                <div class="fb-date">${escapeHtml(formatDate(f.created_at))}</div>
              </div>`,
          )
          .join("");
      } catch (err) {
        listEl.innerHTML = `<p class="empty">${escapeHtml(err instanceof Error ? err.message : "Failed to load")}</p>`;
      }
    }

    await loadList();
  },
};