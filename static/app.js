const TOKEN_KEY = "token";
const ROLE_KEY = "role";

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function saveSession(data) {
  localStorage.setItem(TOKEN_KEY, data.token);
  localStorage.setItem(ROLE_KEY, data.role);
}

function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
}

async function api(path, method = "GET", body) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;

  const res = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = {};
  try {
    data = await res.json();
  } catch (_) {}

  if (!res.ok) {
    const errorMsg = data.detail || "Something went wrong.";
    throw new Error(Array.isArray(errorMsg) ? errorMsg[0].msg : errorMsg);
  }
  return data;
}

function setMsg(element, text, kind = "") {
  element.textContent = text || "";
  element.className = "msg " + kind;
}

async function requireRole(role) {
  if (!getToken()) {
    location.replace("/login.html");
    return null;
  }
  try {
    const me = await api("/api/me");
    if (me.role !== role) {
      location.replace(me.role === "admin" ? "/admin.html" : "/feedback.html");
      return null;
    }
    return me;
  } catch (_) {
    clearSession();
    location.replace("/login.html");
    return null;
  }
}

async function logout() {
  try {
    await api("/api/logout", "POST");
  } catch (_) {}
  clearSession();
  location.replace("/login.html");
}

function fmtDate(iso) {
  return iso ? iso.slice(0, 10) : "";
}
