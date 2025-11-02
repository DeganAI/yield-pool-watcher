import { createAgentApp } from '@lucid-dreams/agent-kit';
import { Hono } from 'hono';

const PORT = parseInt(process.env.PORT || '3000', 10);
const FACILITATOR_URL = process.env.FACILITATOR_URL || 'https://facilitator.cdp.coinbase.com';
const WALLET_ADDRESS = process.env.ADDRESS || '0x01D11F7e1a46AbFC6092d7be484895D2d505095c';

interface PoolData {
  protocol: string;
  pool_id: string;
  chain_id: number;
  apy: number;
  tvl: number;
  apy_delta_24h: number;
  tvl_delta_24h: number;
  alert: string | null;
}

async function fetchDefillama(protocolIds: string[], chainIds: number[]): Promise<PoolData[]> {
  try {
    const response = await fetch('https://yields.llama.fi/pools');
    if (!response.ok) return [];
    const data = await response.json();

    return data.data
      .filter((pool: any) =>
        protocolIds.includes(pool.project.toLowerCase()) &&
        chainIds.includes(pool.chainId || 1)
      )
      .slice(0, 10)
      .map((pool: any) => {
        const apyDelta = pool.apyPct1D || 0;
        const tvlDelta = pool.tvlUsd1D || 0;
        let alert = null;
        if (Math.abs(apyDelta) > 10) alert = `⚠️ APY changed ${apyDelta.toFixed(1)}% in 24h`;
        if (Math.abs(tvlDelta / pool.tvlUsd) > 0.2) alert = `⚠️ TVL changed ${(tvlDelta / pool.tvlUsd * 100).toFixed(1)}% in 24h`;

        return {
          protocol: pool.project,
          pool_id: pool.pool,
          chain_id: pool.chainId || 1,
          apy: pool.apy || 0,
          tvl: pool.tvlUsd || 0,
          apy_delta_24h: apyDelta,
          tvl_delta_24h: tvlDelta,
          alert,
        };
      });
  } catch (error) {
    console.error('[DEFILLAMA] Error:', error);
    return [];
  }
}

const app = createAgentApp({
  name: 'Yield Pool Watcher',
  description: 'Track APY and TVL across DeFi pools',
  version: '1.0.0',
  paymentsConfig: {
    facilitatorUrl: FACILITATOR_URL,
    address: WALLET_ADDRESS as `0x${string}`,
    network: 'base',
    defaultPrice: '$0.05',
  },
});

const honoApp = app.app;
honoApp.get('/health', (c) => c.json({ status: 'ok' }));
honoApp.get('/og-image.png', (c) => {
  const svg = `<svg width="1200" height="630" xmlns="http://www.w3.org/2000/svg"><rect width="1200" height="630" fill="#16213e"/><text x="600" y="315" font-family="Arial" font-size="60" fill="#ffbf00" text-anchor="middle" font-weight="bold">Yield Pool Watcher</text></svg>`;
  c.header('Content-Type', 'image/svg+xml');
  return c.body(svg);
});

app.addEntrypoint({
  key: 'yield-pool-watcher',
  name: 'Yield Pool Watcher',
  description: 'Track APY and TVL across DeFi pools',
  price: '$0.05',
  outputSchema: {
    input: { type: 'http', method: 'POST', discoverable: true, bodyType: 'json', bodyFields: { protocol_ids: { type: 'array', required: true }, chain_ids: { type: 'array', required: true } } },
    output: { type: 'object', required: ['pools', 'timestamp'], properties: { pools: { type: 'array' }, alerts_count: { type: 'integer' }, timestamp: { type: 'string' } } },
  } as any,
  handler: async (ctx) => {
    const { protocol_ids, chain_ids } = ctx.input as any;
    const pools = await fetchDefillama(protocol_ids, chain_ids);
    const alertsCount = pools.filter(p => p.alert).length;
    return { pools, alerts_count: alertsCount, timestamp: new Date().toISOString() };
  },
});

const wrapperApp = new Hono();
wrapperApp.get('/favicon.ico', (c) => { c.header('Content-Type', 'image/svg+xml'); return c.body(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" fill="#ffbf00"/><text y=".9em" x="50%" text-anchor="middle" font-size="90">📈</text></svg>`); });
wrapperApp.get('/', (c) => c.html(`<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Yield Pool Watcher - x402 Agent</title><link rel="icon" type="image/svg+xml" href="/favicon.ico"><meta property="og:title" content="Yield Pool Watcher"><meta property="og:description" content="Track APY and TVL across DeFi pools"><meta property="og:image" content="https://yield-pool-watcher-production.up.railway.app/og-image.png"><style>body{background:#16213e;color:#fff;font-family:system-ui;padding:40px;max-width:1200px;margin:0 auto}h1{color:#ffbf00}</style></head><body><h1>Yield Pool Watcher</h1><p>$0.05 USDC per request</p></body></html>`));
wrapperApp.all('*', async (c) => honoApp.fetch(c.req.raw));

if (typeof Bun !== 'undefined') { Bun.serve({ port: PORT, hostname: '0.0.0.0', fetch: wrapperApp.fetch }); } else { const { serve } = await import('@hono/node-server'); serve({ fetch: wrapperApp.fetch, port: PORT, hostname: '0.0.0.0' }); }
