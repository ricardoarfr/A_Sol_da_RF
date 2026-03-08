import express, { Request, Response } from "express";
import QRCode from "qrcode";
import { startSession, getStatus, getQr, sendMessage } from "./session";

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;

// Status da conexão
app.get("/status", (_req: Request, res: Response) => {
  res.json({ status: getStatus() });
});

// Retorna o QR atual como base64 PNG
app.get("/qr", async (_req: Request, res: Response) => {
  const qr = getQr();
  if (!qr) {
    res.status(404).json({ error: "QR não disponível. Status: " + getStatus() });
    return;
  }
  const dataUrl = await QRCode.toDataURL(qr, { scale: 6, margin: 4 });
  res.json({ qrDataUrl: dataUrl });
});

// Envia mensagem de texto
app.post("/send", async (req: Request, res: Response) => {
  const { phone, message } = req.body;
  if (!phone || !message) {
    res.status(400).json({ error: "Campos obrigatórios: phone, message" });
    return;
  }
  try {
    await sendMessage(phone, message);
    res.json({ status: "sent" });
  } catch (err: any) {
    res.status(503).json({ error: err.message });
  }
});

// Inicia o servidor e a sessão Baileys
app.listen(PORT, async () => {
  console.info(`[server] whatsapp-service rodando na porta ${PORT}`);
  await startSession();
});
