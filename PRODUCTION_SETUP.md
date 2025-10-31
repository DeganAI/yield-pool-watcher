# Production Setup Guide

Complete deployment guide for Yield Pool Watcher.

## Prerequisites

1. GitHub account
2. Railway account (free tier works)
3. Domain (optional, Railway provides one)

## Step 1: Prepare Repository

### Initialize Git Repository

```bash
cd yield-pool-watcher
git init
git add .
git commit -m "Initial commit: Yield Pool Watcher agent"
```

### Create GitHub Repository

1. Go to https://github.com/new
2. Create repository: `yield-pool-watcher`
3. Push code:

```bash
git remote add origin https://github.com/YOUR_USERNAME/yield-pool-watcher.git
git branch -M main
git push -u origin main
```

## Step 2: Deploy to Railway

### Create New Project

1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your `yield-pool-watcher` repository
5. Railway will auto-detect the Dockerfile

### Configure Environment Variables

In Railway project settings, add these variables:

```bash
# Required
PORT=8000
FREE_MODE=false
PAYMENT_ADDRESS=0x01D11F7e1a46AbFC6092d7be484895D2d505095c
BASE_URL=https://yield-pool-watcher-production.up.railway.app

# RPC URLs (use your own or public endpoints)
ETHEREUM_RPC_URL=https://eth.llamarpc.com
POLYGON_RPC_URL=https://polygon.llamarpc.com
ARBITRUM_RPC_URL=https://arbitrum.llamarpc.com
OPTIMISM_RPC_URL=https://optimism.llamarpc.com
BASE_RPC_URL=https://base.llamarpc.com
BSC_RPC_URL=https://bsc.llamarpc.com
AVALANCHE_RPC_URL=https://avalanche.llamarpc.com
```

### Deploy

Railway will automatically:
1. Build Docker image from Dockerfile
2. Start the service using railway.toml configuration
3. Expose the service on a public URL
4. Run health checks on `/health`

## Step 3: Verify Deployment

### Test Endpoints

```bash
# Health check (should return 200)
curl -I https://yield-pool-watcher-production.up.railway.app/health

# AP2 metadata (should return 200)
curl -I https://yield-pool-watcher-production.up.railway.app/.well-known/agent.json

# x402 metadata (should return 402)
curl -I https://yield-pool-watcher-production.up.railway.app/.well-known/x402

# Entrypoint (should return 402 with proper schema)
curl -I https://yield-pool-watcher-production.up.railway.app/entrypoints/yield-pool-watcher/invoke
```

### Verify Response Format

```bash
# Check agent.json structure
curl https://yield-pool-watcher-production.up.railway.app/.well-known/agent.json | jq

# Check x402 metadata
curl https://yield-pool-watcher-production.up.railway.app/.well-known/x402 | jq
```

Verify:
- ✅ `url` field uses `http://` (not `https://`)
- ✅ `payments.endpoint` is `https://facilitator.daydreams.systems`
- ✅ `payments.extensions.x402.facilitatorUrl` is `https://facilitator.daydreams.systems`
- ✅ All x402 fields present: `scheme`, `network`, `maxAmountRequired`, `resource`, `description`, `mimeType`, `payTo`, `maxTimeoutSeconds`, `asset`

## Step 4: Register on x402scan

### Registration

1. Go to https://www.x402scan.com/resources/register
2. Enter your entrypoint URL:
   ```
   https://yield-pool-watcher-production.up.railway.app/entrypoints/yield-pool-watcher/invoke
   ```
3. Leave headers blank
4. Click "Add"

### Verify Registration

1. Should see "Resource Added" confirmation
2. Check https://www.x402scan.com to see your service listed
3. Verify status shows as "Active"

## Step 5: Test Production Service

### Test Pool Monitoring

```bash
curl -X POST https://yield-pool-watcher-production.up.railway.app/pools/watch \
  -H "Content-Type: application/json" \
  -d '{
    "protocol_ids": ["uniswap-v3"],
    "pools": ["0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"],
    "chain": 1,
    "threshold_rules": [
      {
        "metric": "tvl_drop",
        "threshold_percent": 20.0,
        "timeframe_minutes": 60
      }
    ]
  }'
```

### Test with Payment (x402)

When `FREE_MODE=false`, requests require payment via x402 protocol.

The daydreams facilitator will:
1. Intercept the request
2. Verify payment on Base
3. Forward request with `x-payment-txhash` header
4. Return response to user

## Step 6: Monitor Service

### Railway Dashboard

Monitor in Railway:
- Deployment status
- Logs (real-time)
- Resource usage (CPU, memory)
- Health check status
- Request metrics

### Common Issues

**Service won't start:**
- Check logs in Railway dashboard
- Verify all environment variables are set
- Ensure Dockerfile builds correctly

**Health check failing:**
- Verify `/health` endpoint returns 200
- Check `healthcheckTimeout` in railway.toml
- Review application logs

**x402scan registration fails:**
- Ensure entrypoint returns HTTP 402
- Verify all required x402 fields present
- Check `resource` URL matches entrypoint

## Step 7: Production Checklist

Before going live:

- [ ] Service deployed and accessible on Railway
- [ ] `/.well-known/agent.json` returns HTTP 200
- [ ] `/.well-known/x402` returns HTTP 402
- [ ] `/entrypoints/yield-pool-watcher/invoke` returns HTTP 402
- [ ] 402 response includes ALL required fields
- [ ] agent.json `url` field uses `http://` not `https://`
- [ ] agent.json `payments.endpoint` is facilitator URL
- [ ] Both GET and HEAD methods supported
- [ ] Health check endpoint works
- [ ] Landing page loads
- [ ] Registered on x402scan
- [ ] Test requests work in FREE_MODE
- [ ] RPC endpoints configured for all chains
- [ ] Monitoring/logging configured

## Environment Configuration

### Development (FREE_MODE=true)

```bash
FREE_MODE=true
BASE_URL=http://localhost:8000
```

No payment verification, useful for testing.

### Production (FREE_MODE=false)

```bash
FREE_MODE=false
BASE_URL=https://yield-pool-watcher-production.up.railway.app
PAYMENT_ADDRESS=0x01D11F7e1a46AbFC6092d7be484895D2d505095c
```

Requires payment via x402 protocol on Base network.

## Scaling Considerations

### Database for Historical Data

Current implementation uses in-memory storage. For production at scale:

1. Add Redis for historical snapshots
2. Add PostgreSQL for long-term storage
3. Implement proper caching layer

### Rate Limiting

Implement rate limiting to prevent abuse:
- Per-IP limits
- Per-wallet limits (for paid users)
- Global service limits

### Multi-Region Deployment

For global availability:
- Deploy to multiple Railway regions
- Use Cloudflare for CDN/DDoS protection
- Implement load balancing

## Support

For issues or questions:
- GitHub Issues: https://github.com/YOUR_USERNAME/yield-pool-watcher/issues
- Email: hashmonkey@degenai.us

## License

MIT
