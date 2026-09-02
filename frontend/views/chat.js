import { el, getToken } from "../lib.js";

const STORAGE_KEY = "mentor-chat-history";
const PING_INTERVAL = 20000;
const MAX_HISTORY = 20;

let socket = null;
let pingTimer = null;

function loadHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveHistory(entries) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(-MAX_HISTORY)));
  } catch {
    // storage unavailable; ignore
  }
}

function renderMessages(messages, append) {
  for (const item of messages) {
    if (item.type === "user") {
      append(item.text, "user");
    } else if (item.type === "mentor") {
      append(item.text, "mentor");
    }
  }
}

export const ChatView = {
  render(container) {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
      socket.close();
    }
    if (pingTimer) {
      clearInterval(pingTimer);
      pingTimer = null;
    }

    const chat = el(`
      <div class="chat">
        <div class="chat-head">
          <h2>Mentor chat</h2>
          <div class="chat-status" id="chat-status">connecting…</div>
          <button type="button" id="chat-new">New chat</button>
        </div>
        <div class="chat-messages" id="chat-messages"></div>
        <form class="chat-input" id="chat-form">
          <input id="chat-text" placeholder="Ask your mentor something…" autocomplete="off" />
          <button type="submit" class="primary">Send</button>
        </form>
      </div>`);

    container.appendChild(chat);

    const messages = chat.querySelector("#chat-messages");
    const status = chat.querySelector("#chat-status");
    const form = chat.querySelector("#chat-form");
    const text = chat.querySelector("#chat-text");
    let currentBubble = null;
    let typingBubble = null;
    let history = loadHistory();

    function append(msg, cls) {
      const bubble = el(`<div class="bubble ${cls}"></div>`);
      bubble.textContent = msg;
      messages.appendChild(bubble);
      messages.scrollTop = messages.scrollHeight;
      return bubble;
    }

    function showTyping() {
      if (typingBubble) return;
      typingBubble = el(`<div class="bubble mentor typing"><span></span><span></span><span></span></div>`);
      messages.appendChild(typingBubble);
      messages.scrollTop = messages.scrollHeight;
    }

    function hideTyping() {
      if (!typingBubble) return;
      typingBubble.remove();
      typingBubble = null;
    }

    renderMessages(history, append);

    function connect() {
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${proto}//${window.location.host}/api/chat/ws`);
      socket = ws;

      ws.addEventListener("open", () => {
        ws.send(JSON.stringify({ type: "auth", content: getToken() }));
        status.textContent = "connected";
        status.classList.add("ok");
        status.classList.remove("err");
      });
      ws.addEventListener("close", () => {
        status.textContent = "reconnecting…";
        status.classList.remove("ok");
        status.classList.add("err");
        hideTyping();
        if (pingTimer) {
          clearInterval(pingTimer);
          pingTimer = null;
        }
        setTimeout(connect, 2000);
      });
      ws.addEventListener("error", () => {
        status.textContent = "connection error";
        status.classList.remove("ok");
        status.classList.add("err");
      });
      ws.addEventListener("message", (event) => {
        let msg;
        try {
          msg = JSON.parse(event.data);
        } catch {
          return;
        }
        if (msg.type === "token") {
          if (!currentBubble) {
            hideTyping();
            currentBubble = append("", "mentor");
          }
          currentBubble.textContent += msg.content || "";
          messages.scrollTop = messages.scrollHeight;
        } else if (msg.type === "done") {
          if (currentBubble) {
            history.push({ type: "mentor", text: currentBubble.textContent });
            saveHistory(history);
            currentBubble = null;
          }
          hideTyping();
        } else if (msg.type === "error") {
          currentBubble = null;
          hideTyping();
          append(msg.content || "Service error", "mentor error");
        }
      });
    }

    function startPing() {
      if (pingTimer) clearInterval(pingTimer);
      pingTimer = setInterval(() => {
        if (socket && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: "ping" }));
        }
      }, PING_INTERVAL);
    }

    connect();
    startPing();

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const value = text.value.trim();
      if (!value) return;
      append(value, "user");
      history.push({ type: "user", text: value });
      saveHistory(history);
      text.value = "";
      if (socket && socket.readyState === WebSocket.OPEN) {
        showTyping();
        socket.send(JSON.stringify({ message: value }));
      } else {
        append("Connection lost. Please reload the page.", "mentor error");
      }
    });

    chat.querySelector("#chat-new").addEventListener("click", () => {
      messages.innerHTML = "";
      history = [];
      saveHistory(history);
    });
  },
};
