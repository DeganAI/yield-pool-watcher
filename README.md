# Yield Pool Watcher

Track APY and TVL across DeFi pools and alert on sharp changes.

## Overview

Yield Pool Watcher monitors APY (Annual Percentage Yield) and TVL (Total Value Locked) across major DeFi protocols. Get alerted when metrics change beyond configured thresholds - perfect for yield farmers, liquidity providers, and DeFi analysts.

## Features

- **Real-Time Monitoring**: Detect TVL or APY changes beyond thresholds within 1 block
- **Multi-Protocol Support**: Uniswap V2/V3, SushiSwap, Aave, Curve, PancakeSwap, TraderJoe
- **Smart Alerts**: Configure custom thresholds for TVL drains, spikes, and APY changes
- **7 Chains**: Ethereum, Polygon, Arbitrum, Optimism, Base, BSC, Avalanche

## Supported Protocols

### DEX Protocols
- **Uniswap V2**: All chains
- **Uniswap V3**: Ethereum, Polygon, Arbitrum, Optimism, Base
- **SushiSwap**: All chains
- **PancakeSwap**: BSC only
- **TraderJoe**: Avalanche only
- **Curve Finance**: Ethereum, Polygon, Arbitrum, Optimism

### Lending Protocols
- **Aave V3**: All chains except BSC

## API Endpoints

### POST /pools/watch

Monitor pools and receive alerts on threshold breaches.

**Request:**
```json
{
  "protocol_ids": ["uniswap-v3", "aave"],
  "pools": ["0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"],
  "chain": 1,
  "threshold_rules": [
    {
      "metric": "tvl_drop",
      "threshold_percent": 20.0,
      "timeframe_minutes": 60
    },
    {
      "metric": "apy_spike",
      "threshold_percent": 100.0,
      "timeframe_minutes": 60
    }
  ]
}
```

**Response:**
```json
{
  "pool_metrics": [{
    "pool_address": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
    "protocol": "uniswap-v3",
    "apy": 12.5,
    "tvl_usd": 5000000.0,
    "fees_24h": 50000.0,
    "volume_24h": 10000000.0,
    "timestamp": "2025-10-31T18:30:00Z"
  }],
  "deltas": [{
    "metric": "tvl",
    "previous_value": 5500000.0,
    "current_value": 5000000.0,
    "change_percent": -9.09,
    "timeframe_minutes": 60
  }],
  "alerts": [{
    "pool_address": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
    "protocol": "uniswap-v3",
    "alert_type": "tvl_drop",
    "metric": "tvl",
    "threshold_percent": 20.0,
    "actual_change_percent": -25.0,
    "previous_value": 6000000.0,
    "current_value": 4500000.0,
    "triggered_at": "2025-10-31T18:30:00Z",
    "severity": "high"
  }],
  "timestamp": "2025-10-31T18:30:00Z"
}
```

### GET /protocols

List all supported DeFi protocols.

### GET /health

Health check endpoint.

## Alert Types

- **tvl_drop**: Alert when TVL drops beyond threshold (e.g., 20% in 1 hour)
- **tvl_spike**: Alert when TVL increases sharply (e.g., 50% in 1 hour)
- **apy_spike**: Alert when APY increases significantly (e.g., 100% change)
- **apy_drop**: Alert when APY decreases (e.g., 50% drop)

## Development

### Local Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create `.env` file from `.env.example`:
   ```bash
   cp .env.example .env
   ```

4. Run the server:
   ```bash
   uvicorn src.main:app --reload
   ```

### Environment Variables

- `PORT`: Server port (default: 8000)
- `FREE_MODE`: Set to `true` for free mode, `false` for payment verification
- `PAYMENT_ADDRESS`: Payment wallet address
- `BASE_URL`: Service base URL
- RPC URLs for each chain (ETHEREUM_RPC_URL, POLYGON_RPC_URL, etc.)

## Deployment

### Railway

1. Push to GitHub
2. Connect repository to Railway
3. Set environment variables
4. Deploy

Railway will automatically:
- Build the Docker image
- Start the service
- Handle health checks
- Manage restarts

See [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md) for detailed deployment instructions.

## x402 Payment Protocol

This service uses the x402 payment protocol for usage-based billing:

- **Price**: 0.05 USDC per request
- **Network**: Base
- **Payment Address**: `0x01D11F7e1a46AbFC6092d7be484895D2d505095c`
- **Facilitator**: https://facilitator.daydreams.systems

## Technical Details

### Metric Calculation

**TVL (Total Value Locked):**
- DEX Pools: Calculate from reserves and token prices
- Lending Pools: Query from protocol contracts
- Uses CoinGecko for token price feeds

**APY (Annual Percentage Yield):**
- DEX Pools: Calculate from 24h trading fees and TVL
- Lending Pools: Annualize rates from smart contracts
- Formula: APY = (daily_fees / TVL) × 365 × 100

### Alert Logic

Alerts are triggered when:
1. Current metrics are fetched from on-chain data
2. Historical snapshots are compared (5min, 15min, 1hr windows)
3. Change percentage exceeds configured threshold
4. Severity is calculated based on magnitude

### Data Sources

- **On-chain**: Direct smart contract calls via Web3
- **DeFi Llama API**: Protocol TVL and APY data
- **CoinGecko API**: Token price feeds
- **The Graph**: Historical pool analytics

## Testing

Run the test script:
```bash
./test_endpoints.sh
```

This will test:
- Health endpoint
- Protocol listing
- Pool monitoring with sample data
- AP2/x402 endpoints

## License

MIT

## Built By

DeganAI - Bounty #6 Submission for Daydreams AI Agent Bounties
