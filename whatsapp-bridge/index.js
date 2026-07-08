import { makeWASocket, useMultiFileAuthState, DisconnectReason } from "@whiskeysockets/baileys";
import { Redis } from "ioredis";
import pino from "pino";
import qrcode from "qrcode-terminal";

const logger = pino({ level: process.env.LOG_LEVEL || "info" });

const redis = new Redis({
  host: process.env.REDIS_HOST || "localhost",
  port: parseInt(process.env.REDIS_PORT || "6379"),
  password: process.env.REDIS_PASSWORD || undefined,
  retryStrategy: (times) => Math.min(times * 50, 2000),
});

function publish(channel, data) {
  redis.publish(channel, JSON.stringify(data)).catch((err) => {
    logger.error({ err }, "Redis publish failed");
  });
}

async function startBot() {
  const { state, saveCreds } = await useMultiFileAuthState("auth");

  const sock = makeWASocket({
    auth: state,
    logger,
    printQRInTerminal: false,
    syncFullHistory: false,
  });

  sock.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      qrcode.generate(qr, { small: true });
      publish("wa:auth", { event: "qr", data: qr });
      console.log("Scan the QR code above with your WhatsApp phone.");
    }

    if (connection === "open") {
      publish("wa:auth", { event: "connected" });
      console.log("WhatsApp connected!");
    }

    if (connection === "close") {
      const shouldReconnect =
        lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;

      publish("wa:auth", {
        event: "disconnected",
        data: { shouldReconnect },
      });

      if (shouldReconnect) {
        console.log("Reconnecting...");
        startBot();
      } else {
        console.log("Logged out. Delete auth/ and restart.");
      }
    }
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("messages.upsert", async ({ messages }) => {
    for (const msg of messages) {
      if (msg.key?.fromMe) continue;

      const text =
        msg.message?.conversation ||
        msg.message?.extendedTextMessage?.text ||
        "";

      if (!text.trim()) continue;

      const payload = {
        msg_id: msg.key.id || "",
        from: msg.key.remoteJid || "",
        body: text,
        type: "text",
        timestamp: msg.messageTimestamp || Date.now(),
        group_id: msg.key.remoteJid?.includes("@g.us") ? msg.key.remoteJid : null,
      };

      publish("wa:incoming", payload);
    }
  });

  const subscriber = new Redis({
    host: process.env.REDIS_HOST || "localhost",
    port: parseInt(process.env.REDIS_PORT || "6379"),
    password: process.env.REDIS_PASSWORD || undefined,
  });

  subscriber.subscribe("wa:outgoing", (err) => {
    if (err) logger.error({ err }, "Subscribe to wa:outgoing failed");
  });

  subscriber.on("message", async (_channel, message) => {
    try {
      const data = JSON.parse(message);
      const jid = data.to;
      const text = data.body;

      if (jid && text) {
        await sock.sendMessage(jid, { text });
      }
    } catch (err) {
      logger.error({ err }, "Failed to send message");
    }
  });
}

startBot().catch((err) => {
  logger.error({ err }, "Fatal error");
  process.exit(1);
});
