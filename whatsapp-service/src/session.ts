import makeWASocket, {
  DisconnectReason,
  useMultiFileAuthState,
  ConnectionState,
} from "@whiskeysockets/baileys";
import { Boom } from "@hapi/boom";
import path from "path";
import { chmod } from "fs/promises";
import { existsSync } from "fs";

const AUTH_DIR = path.resolve(process.env.AUTH_DIR || "./whatsapp-auth");
const PYTHON_WEBHOOK_URL =
  process.env.PYTHON_WEBHOOK_URL || "http://localhost:8000/api/v1/webhook/baileys";

export type SessionStatus = "disconnected" | "qr" | "connecting" | "connected";

let _status: SessionStatus = "disconnected";
let _qr: string | null = null;
let _sock: ReturnType<typeof makeWASocket> | null = null;
let _reconnectAttempt = 0;
let _reconnecting = false;

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
  // Normaliza número: apenas dígitos + @s.whatsapp.net
  const jid = phone.replace(/\D/g, "") + "@s.whatsapp.net";
  await _sock.sendMessage(jid, { text });
}

export async function startSession(): Promise<void> {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

  _sock = makeWASocket({
    auth: state,
    printQRInTerminal: false,
    browser: ["A Sol da RF", "Chrome", "120.0.0"],
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

      // Protege o arquivo de credenciais
      const credsPath = path.join(AUTH_DIR, "creds.json");
      if (existsSync(credsPath)) {
        await chmod(credsPath, 0o600).catch(() => {});
      }
    }

    if (connection === "close") {
      const statusCode = (lastDisconnect?.error as Boom)?.output?.statusCode;
      const loggedOut = statusCode === DisconnectReason.loggedOut;

      console.warn(`[session] Conexão fechada — código: ${statusCode}`);

      if (loggedOut) {
        _status = "disconnected";
        _qr = null;
        _reconnectAttempt = 0;
        _reconnecting = false;
        console.warn("[session] Deslogado. Escaneie o QR novamente.");
      } else if (!_reconnecting) {
        // Reconecta automaticamente com backoff global
        _status = "connecting";
        _reconnecting = true;
        scheduleReconnect();
      }
    }
  });

  // Recebe mensagens e encaminha ao Python
  _sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;

    for (const msg of messages) {
      if (msg.key.remoteJid === "status@broadcast") continue;
      if (msg.key.fromMe) continue;

      const phone = msg.key.remoteJid?.replace("@s.whatsapp.net", "") ?? "";
      const text =
        msg.message?.conversation ||
        msg.message?.extendedTextMessage?.text ||
        "";

      if (!phone || !text) continue;

      console.info(`[session] Mensagem de ${phone}: ${text.slice(0, 60)}`);

      await forwardToPython({
        phone,
        message: text,
        messageId: msg.key.id ?? undefined,
        senderName: msg.pushName ?? "",
      });
    }
  });

  _sock.ev.on("creds.update", saveCreds);
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
  console.info(`[session] Reconectando em ${Math.round(delay / 1000)}s (tentativa ${_reconnectAttempt}/${maxAttempts})`);

  setTimeout(async () => {
    try {
      await startSession();
    } catch (err) {
      console.error(`[session] Erro ao reconectar: ${err}`);
      scheduleReconnect();
    }
  }, delay);
}

