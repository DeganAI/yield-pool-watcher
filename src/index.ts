import { createAgentApp } from "@lucid-dreams/agent-kit";
import { z } from "zod";

// Input schema
const YieldInputSchema = z.object({
  protocol_ids: z.array(z.string()).describe("Protocol slugs to track (e.g., ['aave-v3', 'compound-v3', 'uniswap-v3'])"),
  chain_ids: z.array(z.number()).describe("Chain IDs to monitor (1=Ethereum, 42161=Arbitrum, etc.)"),
  apy_threshold: z.number().optional().default(10).describe("APY change threshold for alerts (default: 10%)"),
  tvl_threshold: z.number().optional().default(0.2).describe("TVL change threshold for alerts (default: 20%)"),
});

// Output schema
const YieldOutputSchema = z.object({
  pools: z.array(z.object({
    protocol: z.string(),
    pool_id: z.string(),
    chain_id: z.number(),
    apy: z.number(),
    tvl: z.number(),
    apy_delta_24h: z.number(),
    tvl_delta_24h: z.number(),
    alert: z.string().nullable(),
  })),
  alerts_count: z.number(),
  timestamp: z.string(),
});

const { app, addEntrypoint, config } = createAgentApp(
  {
    name: "Yield Pool Watcher",
    version: "1.0.0",
    description: "Track APY and TVL across DeFi pools and alert on sharp changes",
  },
  {
    config: {
      payments: {
        facilitatorUrl: "https://facilitator.daydreams.systems",
        payTo: "0x01D11F7e1a46AbFC6092d7be484895D2d505095c",
        network: "base",
        asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        defaultPrice: "50000", // 0.05 USDC
      },
    },
    useConfigPayments: true,
    ap2: {
      required: true,
      params: { roles: ["merchant"] },
    },
  }
);

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

async function fetchDefillama(
  protocolIds: string[],
  chainIds: number[],
  apyThreshold: number,
  tvlThreshold: number
): Promise<PoolData[]> {
  try {
    const response = await fetch("https://yields.llama.fi/pools");
    if (!response.ok) {
      throw new Error(`DeFiLlama API error: ${response.status}`);
    }

    const data = await response.json();

    if (!data?.data || !Array.isArray(data.data)) {
      throw new Error("Invalid response from DeFiLlama API");
    }

    const filteredPools = data.data
      .filter((pool: any) => {
        const matchesProtocol = protocolIds.some(pid =>
          pool.project?.toLowerCase() === pid.toLowerCase()
        );
        const matchesChain = chainIds.includes(pool.chain ? getChainId(pool.chain) : 1);
        return matchesProtocol && matchesChain && pool.tvlUsd > 10000; // Minimum TVL filter
      })
      .slice(0, 20); // Return top 20 pools

    return filteredPools.map((pool: any) => {
      const apyDelta = pool.apyPct1D || 0;
      const tvlDelta = pool.tvlUsd1D || 0;
      const tvlPercent = pool.tvlUsd > 0 ? (tvlDelta / pool.tvlUsd) * 100 : 0;

      let alert = null;
      if (Math.abs(apyDelta) > apyThreshold) {
        alert = `⚠️ APY ${apyDelta > 0 ? 'increased' : 'decreased'} ${Math.abs(apyDelta).toFixed(1)}% in 24h`;
      } else if (Math.abs(tvlPercent) > tvlThreshold * 100) {
        alert = `⚠️ TVL ${tvlPercent > 0 ? 'increased' : 'decreased'} ${Math.abs(tvlPercent).toFixed(1)}% in 24h`;
      }

      return {
        protocol: pool.project || "unknown",
        pool_id: pool.pool || "unknown",
        chain_id: getChainId(pool.chain),
        apy: Number((pool.apy || 0).toFixed(2)),
        tvl: Number((pool.tvlUsd || 0).toFixed(2)),
        apy_delta_24h: Number(apyDelta.toFixed(2)),
        tvl_delta_24h: Number(tvlDelta.toFixed(2)),
        alert,
      };
    });
  } catch (error) {
    console.error("[DEFILLAMA] Error:", error);
    throw new Error(`Failed to fetch yield data: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

function getChainId(chainName: string): number {
  const chainMap: Record<string, number> = {
    ethereum: 1,
    arbitrum: 42161,
    optimism: 10,
    polygon: 137,
    base: 8453,
    avalanche: 43114,
    bsc: 56,
  };
  return chainMap[chainName?.toLowerCase()] || 1;
}

// Register entrypoint
addEntrypoint({
  key: "yield-pool-watcher",
  description: "Track APY and TVL across DeFi pools with configurable alert thresholds",
  input: YieldInputSchema,
  output: YieldOutputSchema,
  price: "50000", // 0.05 USDC
  async handler({ input }) {
    const pools = await fetchDefillama(
      input.protocol_ids,
      input.chain_ids,
      input.apy_threshold,
      input.tvl_threshold
    );

    const alertsCount = pools.filter((p) => p.alert !== null).length;

    return {
      output: {
        pools,
        alerts_count: alertsCount,
        timestamp: new Date().toISOString(),
      },
    };
  },
});

// Export for Bun
export default {
  port: parseInt(process.env.PORT || "3000"),
  fetch: app.fetch,
};

console.log(`🚀 Yield Pool Watcher running on port ${process.env.PORT || 3000}`);
console.log(`📝 Manifest: ${process.env.BASE_URL}/.well-known/agent.json`);
console.log(`💰 Payment address: ${config.payments?.payTo}`);
