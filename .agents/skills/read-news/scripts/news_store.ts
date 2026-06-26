#!/usr/bin/env bun
/**
 * crypto-news-store — TypeScript/Bun port of news_store.py
 * Local hybrid news store: SQLite + FTS5 + SimHash near-dup clustering.
 * Stdlib-only (bun:sqlite, node:crypto, node:path, node:fs). Zero npm deps.
 */

import { Database } from "bun:sqlite";
import { createHash } from "node:crypto";
import { resolve, dirname } from "node:path";
import { mkdirSync, readFileSync } from "node:fs";

// ── Constants ────────────────────────────────────────────────────────────────

const DEFAULT_DB = ".db/news.db";
const SIMHASH_BITS = 64;
const DEFAULT_JACCARD = 0.15;
const SHINGLE = 3;    // token window for SimHash features
const JAC_NGRAM = 2;  // word + bigram shingles for Jaccard

// ── Types ────────────────────────────────────────────────────────────────────

export interface Article {
  source: string;
  url: string;
  title: string;
  summary: string;
  body: string | null;
  published_at: string;
  lang: string;
  tags: string[];
}

export interface EventRecord {
  event_cluster_id: number;
  title: string;
  first_seen: string;
  last_updated: string;
  sources: string[];
  source_count: number;
  materiality: string | null;
  priced_in: string | null;
  surfaced_to_panel_on: string | null;
}

export interface IngestResult {
  new: number;
  duplicate: number;
  events_touched: number;
}

// ── Text normalization ───────────────────────────────────────────────────────

export function normalizeText(s: string): string {
  if (!s) return "";
  s = String(s).normalize("NFKC").toLowerCase();
  s = s.replace(/https?:\/\/\S+/g, " ");
  s = s.replace(/[^a-z0-9$ ]+/g, " ");
  s = s.replace(/\s+/g, " ").trim();
  return s;
}

export function canonicalUrl(url: string): string {
  if (!url) return "";
  let u = url.trim().split("#")[0];
  u = u.replace(/[?&](utm_[^=&]+|ref|fbclid|gclid)=[^&]*/g, "");
  return u.replace(/[?&/]+$/, "").toLowerCase();
}

export function contentHash(title: string, summary: string): string {
  const norm = normalizeText(`${title} ${summary}`);
  return createHash("sha256").update(norm).digest("hex");
}

// ── Date parsing ─────────────────────────────────────────────────────────────

export function parseDt(s: string | null | undefined): Date | null {
  if (!s) return null;
  const str = String(s).trim();
  // Handles: ISO 8601, RFC-822, %Y-%m-%dT%H:%M:%SZ
  let d = new Date(str);
  if (!isNaN(d.getTime())) return d;
  // "%Y-%m-%d %H:%M:%S" — no T separator, treat as UTC
  const withT = str.replace(/^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})$/, "$1T$2Z");
  if (withT !== str) {
    d = new Date(withT);
    if (!isNaN(d.getTime())) return d;
  }
  return null;
}

export function nowUtc(): string {
  return new Date().toISOString();
}

// ── SimHash ──────────────────────────────────────────────────────────────────

function _tokens(norm: string): string[] {
  const words = norm.split(/\s+/).filter(Boolean);
  const feats: string[] = [...words];
  for (let i = 0; i <= words.length - SHINGLE; i++) {
    feats.push(words.slice(i, i + SHINGLE).join(" "));
  }
  return feats.length > 0 ? feats : [norm];
}

export function simhash(norm: string): string {
  const v = new Array<number>(SIMHASH_BITS).fill(0);
  for (const tok of _tokens(norm)) {
    const hex = createHash("md5").update(tok).digest("hex");
    const h = BigInt("0x" + hex); // 128-bit integer
    for (let b = 0; b < SIMHASH_BITS; b++) {
      if ((h >> BigInt(b)) & BigInt(1)) {
        v[b]++;
      } else {
        v[b]--;
      }
    }
  }
  let out = BigInt(0);
  for (let b = 0; b < SIMHASH_BITS; b++) {
    if (v[b] > 0) out |= BigInt(1) << BigInt(b);
  }
  return out.toString(10);
}

// ── Shingles / Jaccard ───────────────────────────────────────────────────────

export function shingles(norm: string, n = JAC_NGRAM): Set<string> {
  const w = norm.split(/\s+/).filter(Boolean);
  const s = new Set<string>(w);
  for (let i = 0; i <= w.length - n; i++) {
    s.add(w.slice(i, i + n).join(" "));
  }
  return s.size > 0 ? s : new Set([norm]);
}

export function jaccard(a: Set<string>, b: Set<string>): number {
  if (!a.size || !b.size) return 0;
  let inter = 0;
  for (const x of a) if (b.has(x)) inter++;
  const union = a.size + b.size - inter;
  return union > 0 ? inter / union : 0;
}

// ── Optional embeddings ──────────────────────────────────────────────────────

export function embed(text: string): number[] | null {
  const cmd = process.env.CRYPTO_NEWS_EMBED_CMD;
  if (!cmd) return null;
  try {
    const result = Bun.spawnSync(["sh", "-c", cmd], {
      stdin: new TextEncoder().encode(text),
    });
    if (result.exitCode !== 0) return null;
    const vec = JSON.parse(new TextDecoder().decode(result.stdout)) as unknown;
    if (!Array.isArray(vec) || !vec.length) return null;
    return (vec as unknown[]).map((x) => parseFloat(String(x)));
  } catch {
    return null;
  }
}

export function cosine(a: number[], b: number[]): number {
  if (!a || !b || a.length !== b.length) return 0;
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  return na && nb ? dot / (Math.sqrt(na) * Math.sqrt(nb)) : 0;
}

// ── Schema ───────────────────────────────────────────────────────────────────

const SCHEMA = `
CREATE TABLE IF NOT EXISTS events (
    event_cluster_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    rep_simhash        TEXT NOT NULL,
    rep_norm           TEXT NOT NULL DEFAULT '',
    rep_embedding      TEXT,
    title              TEXT NOT NULL,
    first_seen         TEXT NOT NULL,
    last_updated       TEXT NOT NULL,
    sources            TEXT NOT NULL DEFAULT '[]',
    source_count       INTEGER NOT NULL DEFAULT 0,
    materiality        TEXT,
    priced_in          TEXT,
    surfaced_to_panel_on TEXT
);
CREATE TABLE IF NOT EXISTS articles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id      INTEGER NOT NULL REFERENCES events(event_cluster_id),
    source        TEXT, url TEXT, title TEXT, summary TEXT,
    published_at  TEXT, lang TEXT, tags TEXT,
    canonical_url TEXT, content_hash TEXT, simhash TEXT,
    ingested_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_art_canon ON articles(canonical_url);
CREATE INDEX IF NOT EXISTS idx_art_hash  ON articles(content_hash);
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts
    USING fts5(title, summary, content='articles', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS art_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
END;
`;

export function connect(dbPath: string): Database {
  if (dbPath !== ":memory:") {
    mkdirSync(dirname(resolve(dbPath)), { recursive: true });
  }
  const db = new Database(dbPath, { create: true });
  db.exec("PRAGMA journal_mode=WAL;");
  db.exec(SCHEMA);
  return db;
}

/** Alias matching news_db.ts semantics. */
export const openStore = connect;

// ── Event dict helper ────────────────────────────────────────────────────────

type Row = Record<string, unknown>;

function eventDict(r: Row): EventRecord {
  return {
    event_cluster_id: r.event_cluster_id as number,
    title: r.title as string,
    first_seen: r.first_seen as string,
    last_updated: r.last_updated as string,
    sources: JSON.parse(r.sources as string) as string[],
    source_count: r.source_count as number,
    materiality: (r.materiality as string | null) ?? null,
    priced_in: (r.priced_in as string | null) ?? null,
    surfaced_to_panel_on: (r.surfaced_to_panel_on as string | null) ?? null,
  };
}

// ── Find event (near-dup) ────────────────────────────────────────────────────

export function findEvent(db: Database, norm: string, emb: number[] | null): Row | null {
  const rows = db.prepare("SELECT * FROM events").all() as Row[];
  const cosThr = parseFloat(process.env.CRYPTO_NEWS_EMBED_COS ?? "0.85");
  const jacThr = parseFloat(process.env.CRYPTO_NEWS_JACCARD ?? String(DEFAULT_JACCARD));
  const qsh = shingles(norm);
  let best: [Row, number] | null = null;
  for (const r of rows) {
    if (emb !== null && r.rep_embedding) {
      try {
        const repEmb = JSON.parse(r.rep_embedding as string) as number[];
        if (cosine(emb, repEmb) >= cosThr) return r;
      } catch { /* skip */ }
    }
    const j = jaccard(qsh, shingles(r.rep_norm as string));
    if (j >= jacThr && (best === null || j > best[1])) {
      best = [r, j];
    }
  }
  return best ? best[0] : null;
}

// ── Ingest ───────────────────────────────────────────────────────────────────

export function ingest(db: Database, records: Row[]): IngestResult {
  let newCount = 0, dup = 0, touched = 0;
  const ts = nowUtc();
  for (const rec of records) {
    const title = ((rec.title as string) || "").trim();
    const summary = ((rec.summary as string) || (rec.body as string) || "").trim();
    if (!title) continue;

    const curl = canonicalUrl((rec.url as string) || "");
    const chash = contentHash(title, summary);

    // Layer 1: exact dedup
    const exists = db.prepare(
      "SELECT 1 FROM articles WHERE content_hash=? OR (canonical_url<>'' AND canonical_url=?) LIMIT 1",
    ).get(chash, curl);
    if (exists) { dup++; continue; }

    const norm = normalizeText(`${title} ${summary}`);
    const sh = simhash(norm);
    const emb = embed(`${title}. ${summary}`);
    const src = ((rec.source as string) || "").trim() || "unknown";
    const pub = (rec.published_at as string) || ts;

    // Layer 2: near-dup clustering
    const ev = findEvent(db, norm, emb);
    let eventId: number;
    if (ev === null) {
      const result = db.prepare(
        "INSERT INTO events(rep_simhash, rep_norm, rep_embedding, title, first_seen, last_updated,"
        + " sources, source_count, materiality, priced_in) VALUES (?,?,?,?,?,?,?,?,?,?)",
      ).run(
        sh, norm,
        emb !== null ? JSON.stringify(emb) : null,
        title, pub, ts,
        JSON.stringify([src]), 1,
        (rec.materiality as string) ?? null,
        (rec.priced_in as string) ?? null,
      );
      eventId = result.lastInsertRowid as number;
    } else {
      eventId = ev.event_cluster_id as number;
      const srcs = JSON.parse(ev.sources as string) as string[];
      if (!srcs.includes(src)) srcs.push(src);
      db.prepare(
        "UPDATE events SET last_updated=?, sources=?, source_count=? WHERE event_cluster_id=?",
      ).run(ts, JSON.stringify(srcs), srcs.length, eventId);
      touched++;
    }

    db.prepare(
      "INSERT INTO articles(event_id, source, url, title, summary, published_at, lang, tags,"
      + " canonical_url, content_hash, simhash, ingested_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
    ).run(
      eventId, src, (rec.url as string) ?? null, title, summary, pub,
      (rec.lang as string) ?? null,
      JSON.stringify((rec.tags as string[]) || []),
      curl, chash, sh, ts,
    );
    newCount++;
  }
  return { new: newCount, duplicate: dup, events_touched: touched };
}

// ── Query ────────────────────────────────────────────────────────────────────

export function query(
  db: Database,
  q: string,
  opts: { days?: number; k?: number } = {},
): (EventRecord & { score: number })[] {
  const k = opts.k ?? 10;
  const norm = normalizeText(q);

  // Rank A: BM25 over articles → map to events (first occurrence per event)
  const bm25Events: number[] = [];
  const seen = new Set<number>();
  try {
    const rows = db.prepare(
      "SELECT a.event_id AS eid FROM articles_fts f JOIN articles a ON a.id=f.rowid"
      + " WHERE articles_fts MATCH ? ORDER BY bm25(articles_fts) LIMIT 200",
    ).all(norm || q) as { eid: number }[];
    for (const r of rows) {
      if (!seen.has(r.eid)) { seen.add(r.eid); bm25Events.push(r.eid); }
    }
  } catch { /* FTS error → empty list */ }

  // Rank B: shingle-Jaccard similarity to each event's rep_norm
  const qsh = shingles(norm);
  const evRows = db.prepare("SELECT * FROM events").all() as Row[];
  const simRank = [...evRows]
    .sort((a, b) =>
      jaccard(qsh, shingles(b.rep_norm as string)) -
      jaccard(qsh, shingles(a.rep_norm as string)),
    )
    .map((r) => r.event_cluster_id as number);

  // RRF fusion
  const KK = 60;
  const score: Record<number, number> = {};
  for (let rank = 0; rank < bm25Events.length; rank++) {
    const eid = bm25Events[rank];
    score[eid] = (score[eid] ?? 0) + 1 / (KK + rank + 1);
  }
  for (let rank = 0; rank < simRank.length; rank++) {
    const eid = simRank[rank];
    score[eid] = (score[eid] ?? 0) + 1 / (KK + rank + 1);
  }

  const byId: Record<number, Row> = {};
  for (const r of evRows) byId[r.event_cluster_id as number] = r;

  const cutoff = opts.days ? new Date(Date.now() - opts.days * 86_400_000) : null;
  const out: (EventRecord & { score: number })[] = [];
  const sorted = Object.entries(score).sort((a, b) => b[1] - a[1]);
  for (const [eidStr, sc] of sorted) {
    const eid = parseInt(eidStr);
    const r = byId[eid];
    if (!r) continue;
    if (cutoff) {
      const lu = parseDt(r.last_updated as string) ?? new Date();
      if (lu < cutoff) continue;
    }
    const d = { ...eventDict(r), score: parseFloat(sc.toFixed(5)) };
    out.push(d);
    if (out.length >= k) break;
  }
  return out;
}

// ── New since ────────────────────────────────────────────────────────────────

export function newSince(db: Database, days: number): EventRecord[] {
  const cutoff = new Date(Date.now() - days * 86_400_000);
  const rows = db.prepare(
    "SELECT * FROM events WHERE surfaced_to_panel_on IS NULL",
  ).all() as Row[];
  const out: EventRecord[] = [];
  for (const r of rows) {
    const fs = parseDt(r.first_seen as string) ?? new Date();
    const lu = parseDt(r.last_updated as string) ?? new Date();
    if (fs >= cutoff || lu >= cutoff) out.push(eventDict(r));
  }
  out.sort((a, b) => b.last_updated.localeCompare(a.last_updated));
  return out;
}

// ── Mark surfaced ────────────────────────────────────────────────────────────

export function markSurfaced(
  db: Database,
  ids: (string | number)[],
  on?: string,
): { marked: number; on: string } {
  const onDate = on ?? new Date().toISOString().split("T")[0];
  let n = 0;
  for (const id of ids) {
    const result = db.prepare(
      "UPDATE events SET surfaced_to_panel_on=? WHERE event_cluster_id=? AND surfaced_to_panel_on IS NULL",
    ).run(onDate, parseInt(String(id)));
    n += result.changes;
  }
  return { marked: n, on: onDate };
}

// ── Flat-store superset helpers (replacing news_db.ts) ───────────────────────

export function recentArticles(db: Database, source: string, days = 7): Article[] {
  const cutoff = new Date(Date.now() - days * 86_400_000).toISOString();
  const rows = db.prepare(
    "SELECT source, url, title, summary, published_at, lang, tags"
    + " FROM articles WHERE source = ? AND published_at >= ? ORDER BY published_at DESC",
  ).all(source, cutoff) as Array<{
    source: string; url: string; title: string; summary: string;
    published_at: string; lang: string; tags: string;
  }>;
  return rows.map((r) => ({
    source: r.source,
    url: r.url,
    title: r.title,
    summary: r.summary,
    body: null,
    published_at: r.published_at,
    lang: r.lang ?? "en",
    tags: JSON.parse(r.tags ?? "[]") as string[],
  }));
}

export function articleCount(db: Database, source?: string): number {
  if (source) {
    const row = db
      .prepare("SELECT COUNT(*) as cnt FROM articles WHERE source = ?")
      .get(source) as { cnt: number } | null;
    return row?.cnt ?? 0;
  }
  const row = db.prepare("SELECT COUNT(*) as cnt FROM articles").get() as { cnt: number } | null;
  return row?.cnt ?? 0;
}

// ── CLI ──────────────────────────────────────────────────────────────────────

if (import.meta.main) {
  const args = process.argv.slice(2);

  function getArg(flag: string): string | null {
    const i = args.indexOf(flag);
    return i >= 0 && i + 1 < args.length ? args[i + 1] : null;
  }

  const CMDS = ["ingest", "query", "new-since", "mark-surfaced"] as const;
  const cmd = args.find((a) => (CMDS as readonly string[]).includes(a));

  if (!cmd) {
    console.error("Usage: news_store.ts <ingest|query|new-since|mark-surfaced> [options]");
    process.exit(1);
  }

  const dbPath = getArg("--db") ?? process.env.CRYPTO_NEWS_DB ?? DEFAULT_DB;
  const db = connect(dbPath);

  if (cmd === "ingest") {
    const jsonPath = getArg("--json");
    if (!jsonPath) { console.error("--json required"); process.exit(1); }
    let recs = JSON.parse(readFileSync(jsonPath, "utf8")) as unknown;
    if (typeof recs === "object" && !Array.isArray(recs) && recs !== null) {
      const obj = recs as Record<string, unknown>;
      recs = obj.records ?? obj.articles ?? [obj];
    }
    console.log(JSON.stringify(ingest(db, recs as Row[]), null, 2));

  } else if (cmd === "query") {
    const q = getArg("--q");
    if (!q) { console.error("--q required"); process.exit(1); }
    const daysArg = getArg("--days");
    const kArg = getArg("--k");
    console.log(JSON.stringify(query(db, q, {
      days: daysArg ? parseInt(daysArg) : undefined,
      k: kArg ? parseInt(kArg) : 10,
    }), null, 2));

  } else if (cmd === "new-since") {
    const daysArg = getArg("--days");
    console.log(JSON.stringify(newSince(db, daysArg ? parseInt(daysArg) : 2), null, 2));

  } else if (cmd === "mark-surfaced") {
    const onDate = getArg("--on") ?? undefined;
    const idsIdx = args.indexOf("--ids");
    if (idsIdx < 0) { console.error("--ids required"); process.exit(1); }
    const ids: string[] = [];
    for (let i = idsIdx + 1; i < args.length; i++) {
      if (args[i].startsWith("--")) break;
      ids.push(args[i]);
    }
    console.log(JSON.stringify(markSurfaced(db, ids, onDate), null, 2));

  } else {
    console.error(`Unknown command: ${cmd}`);
    process.exit(1);
  }
}
