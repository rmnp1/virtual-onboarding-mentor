import { api, el, escapeHtml, showToast } from "../lib.js";

async function answer(id, value) {
  return api(`/api/scenarios/${encodeURIComponent(id)}/answer`, {
    method: "POST",
    body: { answer: value },
  });
}

function renderStepData(content, id, data) {
  if (data.completed) {
    content.innerHTML = `
      <div class="step">
        <div class="badge">completed</div>
        <div class="step-content">${escapeHtml(data.message || data.content || "Completed!")}</div>
        <div class="step-nav"><a class="primary" href="#/scenarios">Back to scenarios</a></div>
      </div>`;
    return;
  }

  const text = data.message ?? data.content ?? "";
  const body = el(`
    <div class="step">
      <div class="step-content">${escapeHtml(text)}</div>
    </div>`);

  const nav = el(`<div class="step-nav"></div>`);
  if (Array.isArray(data.options) && data.options.length) {
    const options = el(`<div class="options"></div>`);
    data.options.forEach((option, index) => {
      const button = el(`<button type="button" class="option">${escapeHtml(option)}</button>`);
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          const res = await answer(id, index);
          renderStepData(content, id, res);
        } catch (err) {
          button.disabled = false;
          showToast(err instanceof Error ? err.message : "Request failed", true);
        }
      });
      options.appendChild(button);
    });
    body.appendChild(options);
  } else {
    const next = el(`<button type="button" class="primary">Next</button>`);
    next.addEventListener("click", async () => {
      next.disabled = true;
      try {
        const res = await answer(id, null);
        renderStepData(content, id, res);
      } catch (err) {
        next.disabled = false;
        showToast(err instanceof Error ? err.message : "Request failed", true);
      }
    });
    nav.appendChild(next);
  }
  body.appendChild(nav);

  content.innerHTML = "";
  content.appendChild(body);
}

async function renderList(container) {
  try {
    const list = await api("/api/scenarios");
    const wrap = el(`
      <div>
        <h2>Scenarios</h2>
        <div class="scenario-grid"></div>
      </div>`);
    const grid = wrap.querySelector(".scenario-grid");
    if (!list.length) {
      grid.appendChild(el(`<p class="empty">No scenarios available for your role yet.</p>`));
    }
    for (const s of list) {
      grid.appendChild(el(`
        <a class="scenario-card" href="#/scenario/${encodeURIComponent(s.id)}">
          <div class="scenario-title">${escapeHtml(s.title)}</div>
          ${s.completed ? `<span class="badge">completed</span>` : ""}
        </a>`));
    }
    container.innerHTML = "";
    container.appendChild(wrap);
  } catch (err) {
    container.innerHTML = `<p class="empty">${escapeHtml(err instanceof Error ? err.message : "Failed to load")}</p>`;
  }
}

async function renderPlayer(container, id) {
  const wrap = el(`
    <div class="player">
      <a href="#/scenarios" class="back">← Scenarios</a>
      <div id="p-content"><p class="empty">Loading…</p></div>
    </div>`);
  container.innerHTML = "";
  container.appendChild(wrap);
  const content = wrap.querySelector("#p-content");

  try {
    const step = await api(`/api/scenarios/${encodeURIComponent(id)}`);
    const data = {
      content: step.content,
      message: step.content,
      options: step.options,
      completed: step.completed,
    };
    renderStepData(content, id, data);
  } catch (err) {
    content.innerHTML = `<p class="empty">${escapeHtml(err instanceof Error ? err.message : "Failed to load")}</p>`;
  }
}

export const ScenariosView = {
  render(container, params) {
    if (params && params.length > 1) renderPlayer(container, params[1]);
    else renderList(container);
  },
};