import { Pool } from "pg";

const _pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.DATABASE_URL?.includes("localhost")
    ? false
    : { rejectUnauthorized: false },
});

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
