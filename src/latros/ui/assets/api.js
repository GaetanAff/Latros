async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  }); } catch { throw new Error(t("service_unavailable")); }
  let payload;
  try { payload = await response.json(); }
  catch { throw new Error(t("unreadable")); }
  if (!response.ok) throw new Error(t("http_error", {status: response.status, message: payload.message || payload.error || ""}));
  return payload;
}

function notice(message) {
  byId("app-message").textContent = message;
  byId("app-message").hidden = !message;
}

function setBusy(busy, message = t("loading")) {
  state.busy = busy;
  window.clearTimeout(state.busyTimer);
  byId("loading-text").textContent = message;
  byId("loading-layer").hidden = !busy;
  byId("app-shell").setAttribute("aria-busy", String(busy));
  if (busy) {
    state.busyTimer = window.setTimeout(() => {
      byId("loading-text").textContent = t("slow");
    }, 15000);
  }
}

async function guarded(action, message = t("loading")) {
  if (state.busy) return;
  notice("");
  setBusy(true, message);
  try { await action(); }
  catch (error) { notice(error.message || t("local_error")); }
  finally { setBusy(false); }
}
