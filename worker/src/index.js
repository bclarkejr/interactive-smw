// Summer Movie Wager — players API (spec §3). Stores and returns submissions; nothing else.
export const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

async function listPlayers(env, year) {
  const { results } = await env.DB.prepare(
    "SELECT username, joined_at, picks FROM players WHERE year = ? ORDER BY joined_at, username")
    .bind(year).all();
  const players = results.map((r) => {
    const p = JSON.parse(r.picks);
    return { username: r.username, joined_at: r.joined_at,
             ranked: p.ranked, dark_horses: p.dark_horses };
  });
  return json(200, { year, players });
}

const USERNAME = /^[a-z0-9][a-z0-9-]{1,22}[a-z0-9]$/;
const MAX_BODY_BYTES = 4096;

function titlesOk(list, n) {
  return Array.isArray(list) && list.length === n &&
    list.every((t) => typeof t === "string" && t.length >= 1 && t.length <= 120);
}

/** §3.3 validation table. Returns an error message, or null when the body is acceptable. */
export function validate(body) {
  if (body === null || typeof body !== "object" || Array.isArray(body))
    return "body must be a JSON object";
  if (typeof body.username !== "string" || !USERNAME.test(body.username))
    return "username must be 3–24 characters: lowercase letters, digits, and interior hyphens";
  if (!titlesOk(body.ranked, 10)) return "ranked must be exactly 10 titles of 1–120 characters";
  if (!titlesOk(body.dark_horses, 3)) return "dark_horses must be exactly 3 titles of 1–120 characters";
  if (new Set([...body.ranked, ...body.dark_horses]).size !== 13)
    return "all 13 titles must be distinct";
  return null;
}

async function createPlayer(request, env, year) {
  const raw = await request.arrayBuffer();
  if (raw.byteLength > MAX_BODY_BYTES) return json(413, { error: "body exceeds 4 KB" });
  let body;
  try { body = JSON.parse(new TextDecoder().decode(raw)); }
  catch { return json(400, { error: "body must be JSON" }); }
  const err = validate(body);
  if (err) return json(400, { error: err });
  const joined_at = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");  // server-assigned (§2.2)
  const picks = JSON.stringify({ ranked: body.ranked, dark_horses: body.dark_horses });
  try {
    // INSERT and map the PK violation — never check-then-insert (§3.3).
    await env.DB.prepare(
      "INSERT INTO players (username, year, joined_at, picks) VALUES (?, ?, ?, ?)")
      .bind(body.username, year, joined_at, picks).run();
  } catch (e) {
    if (/UNIQUE constraint failed/i.test(String(e && e.message || e)))
      return json(409, { error: "that username is taken — pick another" });
    throw e;
  }
  return json(201, { username: body.username, joined_at });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/api/players") return json(404, { error: "not found" });
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    const year = Number(env.SEASON_YEAR);
    if (request.method === "GET") return listPlayers(env, year);
    if (request.method === "POST") return createPlayer(request, env, year);
    return json(405, { error: "method not allowed" });
  },
};
