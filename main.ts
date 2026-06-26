// ── DAO Proposal Risk Scorer — main.ts ───────────────────────────────────────
// Static server: serves frontend/index.html.
// All business logic lives on the GenLayer chain via the intelligent contract.
// The browser talks directly to the GenLayer Studio node via genlayer-js.

import { join } from "https://deno.land/std@0.224.0/path/mod.ts";

const PORT       = Number(Deno.env.get("PORT") ?? 8000);
const STATIC_DIR = join(Deno.cwd(), "frontend");

function cors(extra: HeadersInit = {}): Headers {
  const h = new Headers(extra);
  h.set("Access-Control-Allow-Origin", "*");
  return h;
}

Deno.serve({ port: PORT }, async (req) => {
  const url = new URL(req.url);

  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: cors() });
  }

  if (url.pathname === "/health") {
    return new Response(JSON.stringify({ ok: true }), {
      headers: cors({ "Content-Type": "application/json" }),
    });
  }

  try {
    const content = await Deno.readFile(join(STATIC_DIR, "index.html"));
    return new Response(content, {
      headers: cors({ "Content-Type": "text/html; charset=utf-8" }),
    });
  } catch {
    return new Response("Not found", { status: 404, headers: cors() });
  }
});

console.log(`DAO Risk Scorer frontend → http://localhost:${PORT}`);
console.log("Contract methods:");
console.log("  Write: submit_proposal(title, description)");
console.log("  Read:  get_proposal, list_proposals, get_stats, get_dao_name");
