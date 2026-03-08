import { Pool } from "pg";

const _pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.DATABASE_URL?.includes("localhost")
    ? false
    : { rejectUnauthorized: false },
});

export async function initDb(): Promise<void> {
  await _pool.query(`
    CREATE TABLE IF NOT EXISTS whatsapp_lid_map (
      lid   TEXT PRIMARY KEY,
      phone TEXT NOT NULL
    )
  `);
}

export async function loadCreds(): Promise<string | null> {
  try {
    const res = await _pool.query<{ value: string }>(
      "SELECT value FROM whatsapp_session WHERE key = 'creds'"
    );
    return res.rows[0]?.value ?? null;
  } catch {
    return null;
  }
}

export async function saveCreds(json: string): Promise<void> {
  await _pool.query(
    `INSERT INTO whatsapp_session (key, value) VALUES ('creds', $1)
     ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value`,
    [json]
  );
}

export async function deleteCreds(): Promise<void> {
  await _pool.query("DELETE FROM whatsapp_session WHERE key = 'creds'");
}

export async function loadLidMappings(): Promise<Map<string, string>> {
  try {
    const res = await _pool.query<{ lid: string; phone: string }>(
      "SELECT lid, phone FROM whatsapp_lid_map"
    );
    return new Map(res.rows.map((r) => [r.lid, r.phone]));
  } catch {
    return new Map();
  }
}

export async function saveLidMapping(lid: string, phone: string): Promise<void> {
  try {
    await _pool.query(
      `INSERT INTO whatsapp_lid_map (lid, phone) VALUES ($1, $2)
       ON CONFLICT (lid) DO UPDATE SET phone = EXCLUDED.phone`,
      [lid, phone]
    );
  } catch {
    // silently ignore — mapping still works in-memory
  }
}
