import makeWASocket, {
  DisconnectReason,
  useMultiFileAuthState,
  ConnectionState,
  fetchLatestBaileysVersion,
} from "@whiskeysockets/baileys";
import { Boom } from "@hapi/boom";
import path from "path";
import { chmod, mkdir, rm, writeFile, readFile } from "fs/promises";
import { existsSync } from "fs";
import { loadCreds, saveCreds as saveCredsToDb } from "./db";

const AUTH_DIR = path.resolve(process.env.AUTH_DIR || "./whatsapp-auth");
const PYTHON_WEBHOOK_URL =
  process.env.PYTHON_WEBHOOK_URL || "http://localhost:8000/api/v1/webhook/baileys";

export type SessionStatus = "disconnected" | "qr" | "connecting" | "connected";

let _status: SessionStatus = "disconnected";
let _qr: string | null = null;
let _sock: ReturnType<typeof makeWASocket> | null = null;
let _reconnectAttempt = 0;
let _reconnecting = false;
let _reconnectTimer: NodeJS.Timeout | null = null;

/** Mapeia LID (sem sufixo) → número de telefone (sem sufixo) para resolver @lid JIDs */
const _lidToPhone = new Map<string, string>();

/** Fila de mensagens aguardando resolução de @lid */
const _pendingLid = new Map<
  string,
  Array<{ message: string; messageId?: string; senderName: string }>
>();

/** Registra mapeamento lid→phone e processa mensagens pendentes desse lid */
function _addLidMapping(lid: string, phone: string): void {
  if (!lid || !phone) return;
  _lidToPhone.set(lid, phone);
  const pending = _pendingLid.get(lid);
  if (pending?.length) {
    _pendingLid.delete(lid);
    console.info(
      `[session] Processando ${pending.length} mensagem(ns) pendente(s) do lid ${lid} → ${phone}`
    );
    for (const item of pending) {
      forwardToPython({ phone, ...item });
    }
  }
}

export function getStatus(): SessionStatus {
  return _status;
}

export function getQr(): string | null {
  return _qr;
}

export async function sendMessage(phone: string, text: string): Promise<void> {
  if (!_sock || _status !== "connected") {
    throw new Error("WhatsApp não está conectado.");
  }
  const jid = phone.replace(/\D/g, "") + "@s.whatsapp.net";
  await _sock.sendMessage(jid, { text });
}

/** Fecha o socket ativo e remove listeners para evitar eventos duplicados. */
function closeSocket(): void {
  if (!_sock) return;
  try {
    _sock.ev.removeAllListeners("connection.update");
    _sock.ev.removeAllListeners("messages.upsert");
    _sock.ev.removeAllListeners("creds.update");
    _sock.ev.removeAllListeners("contacts.upsert");
    _sock.ws.close();
  } catch {
    // ignora erros ao fechar socket já encerrado
  }
  _sock = null;
}

/** Cancela reconexão agendada, se houver. */
function cancelReconnect(): void {
  if (_reconnectTimer) {
    clearTimeout(_reconnectTimer);
    _reconnectTimer = null;
  }
}

/** Limpa o diretório de autenticação para forçar novo QR. */
async function clearAuthDir(): Promise<void> {
  console.warn("[session] Limpando diretório de autenticação (sessão inválida)");
  await rm(AUTH_DIR, { recursive: true, force: true });
  await mkdir(AUTH_DIR, { recursive: true });
}

/**
 * Valida se o creds.json existente contém os campos mínimos esperados pelo Baileys.
 * Retorna true se válido ou ausente (sem sessão = QR será gerado).
 */
async function validateCredsJson(): Promise<boolean> {
  const credsPath = path.join(AUTH_DIR, "creds.json");
  if (!existsSync(credsPath)) return true;
  try {
    const raw = await readFile(credsPath, "utf8");
    const parsed = JSON.parse(raw);
    if (!parsed.noiseKey || !parsed.signedIdentityKey) {
      console.warn("[session] creds.json sem campos obrigatórios — sessão inválida");
      return false;
    }
    return true;
  } catch {
    console.warn("[session] creds.json corrompido (JSON inválido)");
    return false;
  }
}

async function restoreCredsFromDb(): Promise<void> {
  const credsPath = path.join(AUTH_DIR, "creds.json");
  if (existsSync(credsPath)) return; // já existe no disco — não sobrescreve
  try {
    const json = await loadCreds();
    if (!json) return;
    JSON.parse(json); // valida antes de escrever
    await mkdir(AUTH_DIR, { recursive: true });
    await writeFile(credsPath, json, { mode: 0o600 });
    console.info("[session] Credenciais restauradas do banco de dados");
  } catch (err) {
    console.error("[session] Erro ao restaurar credenciais do banco:", err);
  }
}

export async function startSession(): Promise<void> {
  closeSocket();
  cancelReconnect();

  await restoreCredsFromDb();

  const credsValid = await validateCredsJson();
  if (!credsValid) {
    await clearAuthDir();
    console.info("[session] Sessão limpa — aguardando scan do QR");
  }

  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

  const { version } = await fetchLatestBaileysVersion();
  console.info("[session] usando versão WA:", version);

  _sock = makeWASocket({
    version,
    auth: state,
    printQRInTerminal: false,
    browser: ["A Sol da RF", "Chrome", "120.0.0"],
    syncFullHistory: false,
    markOnlineOnConnect: false,
  });

  _sock.ev.on("connection.update", async (update: Partial<ConnectionState>) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      _status = "qr";
      _qr = qr;
      console.info("[session] QR gerado — aguardando scan");
    }

    if (connection === "connecting") {
      _status = "connecting";
      console.info("[session] Conectando...");
    }

    if (connection === "open") {
      _status = "connected";
      _qr = null;
      _reconnectAttempt = 0;
      _reconnecting = false;
      console.info("[session] Conectado ao WhatsApp");

      const credsPath = path.join(AUTH_DIR, "creds.json");
      if (existsSync(credsPath)) {
        await chmod(credsPath, 0o600).catch(() => {});
      }
    }

    if (connection === "close") {
      const err = lastDisconnect?.error as Boom | undefined;
      const statusCode = err?.output?.statusCode;

      console.warn(`[session] Conexão fechada — código: ${statusCode}`);
      _status = "disconnected";

      // Logout explícito — não reconectar, aguardar novo QR via API
      if (statusCode === DisconnectReason.loggedOut) {
        _qr = null;
        _reconnectAttempt = 0;
        _reconnecting = false;
        console.warn("[session] Deslogado. Escaneie o QR novamente via /api/qr.");
        return;
      }

      // Sessão inválida: device pairing rejeitado pelo WhatsApp
      if (statusCode === 405) {
        console.warn("[session] Sessão inválida (405) — limpando auth e reiniciando");
        _reconnectAttempt = 0;
        _reconnecting = false;
        await clearAuthDir();
        await startSession();
        return;
      }

      // Outros erros — reconectar com backoff exponencial
      if (!_reconnecting) {
        _reconnecting = true;
        scheduleReconnect();
      }
    }
  });

  // contacts.upsert: popula mapeamento lid→phone e processa fila de mensagens pendentes
  _sock.ev.on("contacts.upsert", (contacts) => {
    for (const contact of contacts) {
      if (contact.lid && contact.id) {
        const phone = contact.id.replace(/@s\.whatsapp\.net$/, "").replace(/@\w+$/, "");
        const lid = contact.lid.replace(/@lid$/, "").replace(/@\w+$/, "");
        if (phone && lid) {
          _addLidMapping(lid, phone);
        }
      }
    }
  });

  _sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;

    for (const msg of messages) {
      if (msg.key.remoteJid === "status@broadcast") continue;
      if (msg.key.fromMe) continue;

      const remoteJid = msg.key.remoteJid ?? "";
      let phone = "";
      let lidKey = "";

      if (remoteJid.endsWith("@s.whatsapp.net")) {
        phone = remoteJid.replace("@s.whatsapp.net", "");
      } else if (remoteJid.endsWith("@lid")) {
        lidKey = remoteJid.replace(/@lid$/, "");
        phone = _lidToPhone.get(lidKey) ?? "";
        if (!phone) {
          console.warn(`[session] @lid sem mapeamento: ${remoteJid} — enfileirando mensagem`);
        }
      } else {
        continue; // grupo ou JID desconhecido
      }

      const text =
        msg.message?.conversation ||
        msg.message?.extendedTextMessage?.text ||
        "";

      if (!text) continue;

      // @lid ainda não mapeado → enfileira para processar quando contatos chegarem
      if (lidKey && !phone) {
        const queue = _pendingLid.get(lidKey) ?? [];
        queue.push({
          message: text,
          messageId: msg.key.id ?? undefined,
          senderName: msg.pushName ?? "",
        });
        _pendingLid.set(lidKey, queue);
        console.info(
          `[session] Mensagem de @lid ${lidKey} enfileirada (total: ${queue.length})`
        );
        continue;
      }

      console.info(`[session] Mensagem de ${phone}: ${text.slice(0, 60)}`);

      await forwardToPython({
        phone,
        message: text,
        messageId: msg.key.id ?? undefined,
        senderName: msg.pushName ?? "",
      });
    }
  });

  _sock.ev.on("creds.update", async () => {
    await saveCreds(); // salva no disco (Baileys)
    try {
      const credsPath = path.join(AUTH_DIR, "creds.json");
      const json = await readFile(credsPath, "utf8");
      await saveCredsToDb(json); // persiste no banco PostgreSQL
    } catch (err) {
      console.error("[session] Erro ao persistir creds no banco:", err);
    }
  });
}

async function forwardToPython(data: {
  phone: string;
  message: string;
  messageId?: string;
  senderName?: string;
}): Promise<void> {
  try {
    await fetch(PYTHON_WEBHOOK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
  } catch (err) {
    console.error(`[session] Erro ao encaminhar mensagem ao Python: ${err}`);
  }
}

function scheduleReconnect(): void {
  const maxAttempts = 15;
  const baseDelay = 5000;
  const maxDelay = 300000; // 5 minutos

  if (_reconnectAttempt >= maxAttempts) {
    console.error("[session] Máximo de tentativas atingido. Desistindo.");
    _status = "disconnected";
    _reconnecting = false;
    _reconnectAttempt = 0;
    return;
  }

  const delay = Math.min(baseDelay * Math.pow(2, _reconnectAttempt), maxDelay);
  _reconnectAttempt++;
  console.info(
    `[session] Reconectando em ${Math.round(delay / 1000)}s (tentativa ${_reconnectAttempt}/${maxAttempts})`
  );

  cancelReconnect();
  _reconnectTimer = setTimeout(async () => {
    _reconnectTimer = null;
    try {
      await startSession();
    } catch (err) {
      console.error(`[session] Erro ao reconectar: ${err}`);
      scheduleReconnect();
    }
  }, delay);
}
