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

export type SessionStatus = "disconnected" | "qr" | "connecting" | "connected";

let _status: SessionStatus = "disconnected";
let _qr: string | null = null;
let _sock: ReturnType<typeof makeWASocket> | null = null;

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
        console.warn("[session] Deslogado. Escaneie o QR novamente.");
      } else {
        // Reconecta automaticamente com backoff
        _status = "connecting";
        await reconnectWithBackoff();
      }
    }
  });

  _sock.ev.on("creds.update", saveCreds);
}

async function reconnectWithBackoff(attempt = 0): Promise<void> {
  const maxAttempts = 10;
  const baseDelay = 2000;
  const maxDelay = 30000;

  if (attempt >= maxAttempts) {
    console.error("[session] Máximo de tentativas atingido. Desistindo.");
    _status = "disconnected";
    return;
  }

  const delay = Math.min(baseDelay * Math.pow(1.8, attempt), maxDelay);
  console.info(`[session] Reconectando em ${Math.round(delay / 1000)}s (tentativa ${attempt + 1})`);

  await sleep(delay);

  try {
    await startSession();
  } catch (err) {
    console.error(`[session] Erro ao reconectar: ${err}`);
    await reconnectWithBackoff(attempt + 1);
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
