/**
 * Magnolia Hunter — Polymarket order placer (CLOB v2, POLY_1271 deposit wallet)
 * Gebruik: node place_order.js <condition_id> <no_price> <size_usdc>
 * Output: JSON { success, orderID, shares, price } of { success: false, error }
 */

const { ClobClient, Side, OrderType, SignatureTypeV2 } = require("@polymarket/clob-client-v2");
const { createWalletClient, http } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { polygon } = require("viem/chains");
const fs = require("fs");
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, ".env"), quiet: true });

const POLYMARKET_HOST = "https://clob.polymarket.com";
const CHAIN_ID = 137;
const ENV_PATH = path.join(__dirname, ".env");
// Deposit wallet voor EOA 0x7E79E542d9Bf590c6142F336d4Dc6Be10135823b
const DEPOSIT_WALLET = "0x393f39B28b1Ac8234B6B8Cf1739E54CE769e4B63";

async function main() {
  if (process.env.POLYMARKET_TRADING_ENABLED !== "true") {
    out({
      success: false,
      error: "Polymarket trading is disabled. Use read-only signals unless access and trading are legal for you.",
    });
    return;
  }

  const [, , conditionId, noPriceStr, sizeUsdcStr] = process.argv;

  if (!conditionId || !noPriceStr || !sizeUsdcStr) {
    out({ success: false, error: "Gebruik: node place_order.js <condition_id> <no_price> <size_usdc>" });
    return;
  }

  const noPrice = parseFloat(noPriceStr);
  const sizeUsdc = parseFloat(sizeUsdcStr);
  const shares = Math.round((sizeUsdc / noPrice) * 100) / 100;

  const rawKey = process.env.POLYGON_PRIVATE_KEY;
  if (!rawKey) {
    out({ success: false, error: "POLYGON_PRIVATE_KEY niet gevonden in .env" });
    return;
  }

  const privateKey = rawKey.startsWith("0x") ? rawKey : `0x${rawKey}`;

  try {
    const account = privateKeyToAccount(privateKey);
    const walletClient = createWalletClient({
      account,
      chain: polygon,
      transport: http("https://polygon-rpc.com"),
    });

    // Bestaande creds ophalen
    let creds = null;
    const apiKey = process.env.POLYMARKET_API_KEY;
    const apiSecret = process.env.POLYMARKET_API_SECRET;
    const apiPassphrase = process.env.POLYMARKET_API_PASSPHRASE;

    if (apiKey && apiSecret && apiPassphrase) {
      creds = { key: apiKey, secret: apiSecret, passphrase: apiPassphrase };
    }

    // Maak v2 client aan: EOA als signer, deposit wallet als funderAddress (maker)
    let client = new ClobClient({
      host: POLYMARKET_HOST,
      chain: CHAIN_ID,
      signer: walletClient,
      creds: creds || undefined,
      signatureType: SignatureTypeV2.EOA,
      funderAddress: DEPOSIT_WALLET,
    });

    // Creds aanmaken als ze er nog niet zijn
    if (!creds) {
      const newCreds = await client.createOrDeriveApiKey();
      fs.appendFileSync(ENV_PATH,
        `\nPOLYMARKET_API_KEY=${newCreds.key}\nPOLYMARKET_API_SECRET=${newCreds.secret}\nPOLYMARKET_API_PASSPHRASE=${newCreds.passphrase}\n`
      );
      client = new ClobClient({
        host: POLYMARKET_HOST,
        chain: CHAIN_ID,
        signer: walletClient,
        creds: newCreds,
        signatureType: SignatureTypeV2.EOA,
        funderAddress: DEPOSIT_WALLET,
      });
    }

    // Token ID ophalen voor No
    const market = await client.getMarket(conditionId);
    const tokens = market.tokens || [];
    const noToken = tokens.find(t => t.outcome === "No");

    if (!noToken) {
      out({ success: false, error: "Geen No token gevonden voor condition_id: " + conditionId });
      return;
    }

    // Order aanmaken en plaatsen
    const signedOrder = await client.createOrder({
      tokenID: noToken.token_id,
      price: noPrice,
      size: shares,
      side: Side.BUY,
    });

    const resp = await client.postOrder(signedOrder, OrderType.GTC);

    if (resp && resp.success) {
      out({ success: true, orderID: resp.orderID, shares, price: noPrice });
    } else {
      out({ success: false, error: JSON.stringify(resp) });
    }

  } catch (err) {
    out({ success: false, error: err.message });
  }
}

function out(obj) {
  process.stdout.write(JSON.stringify(obj) + "\n");
}

main().catch(err => out({ success: false, error: err.message }));
