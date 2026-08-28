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

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/api/players") return json(404, { error: "not found" });
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    const year = Number(env.SEASON_YEAR);
    if (request.method === "GET") return listPlayers(env, year);
    return json(405, { error: "method not allowed" });
  },
};
