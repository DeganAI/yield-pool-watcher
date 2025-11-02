"""
Yield Pool Watcher - Track APY and TVL across DeFi pools

x402 micropayment-enabled pool monitoring service
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import logging

from src.pool_monitor import PoolMonitor
from src.apy_calculator import APYCalculator
from src.tvl_tracker import TVLTracker
from src.alert_engine import AlertEngine
from src.protocol_adapters import get_supported_protocols
from src.x402_middleware_dual import X402Middleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Yield Pool Watcher",
    description="Track APY and TVL across DeFi pools - powered by x402",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configuration
payment_address = os.getenv("PAYMENT_ADDRESS", "0x01D11F7e1a46AbFC6092d7be484895D2d505095c")
base_url = os.getenv("BASE_URL", "https://yield-pool-watcher-production.up.railway.app")
free_mode = os.getenv("FREE_MODE", "false").lower() == "true"

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# x402 Payment Verification Middleware
app.add_middleware(
    X402Middleware,
    payment_address=payment_address,
    base_url=base_url,
    facilitator_urls=[
        "https://facilitator.daydreams.systems",
        "https://api.cdp.coinbase.com/platform/v2/x402/facilitator"
    ],
    free_mode=free_mode,
)

logger.info(f"Running in {'FREE' if free_mode else 'PAID'} mode")

# RPC URLs per chain
RPC_URLS = {
    1: os.getenv("ETHEREUM_RPC_URL", "https://eth.llamarpc.com"),
    137: os.getenv("POLYGON_RPC_URL", "https://polygon.llamarpc.com"),
    42161: os.getenv("ARBITRUM_RPC_URL", "https://arbitrum.llamarpc.com"),
    10: os.getenv("OPTIMISM_RPC_URL", "https://optimism.llamarpc.com"),
    8453: os.getenv("BASE_RPC_URL", "https://base.llamarpc.com"),
    56: os.getenv("BSC_RPC_URL", "https://bsc.llamarpc.com"),
    43114: os.getenv("AVALANCHE_RPC_URL", "https://avalanche.llamarpc.com"),
}


# Request/Response Models
class ThresholdRule(BaseModel):
    """Threshold configuration for alerts"""
    metric: str = Field(..., description="Metric to monitor (tvl_drop, tvl_spike, apy_spike, apy_drop)")
    threshold_percent: float = Field(..., description="Threshold percentage for alert")
    timeframe_minutes: int = Field(..., description="Timeframe for comparison")


class WatchRequest(BaseModel):
    """Request for pool watching"""
    protocol_ids: List[str] = Field(
        ...,
        description="DeFi protocols to monitor (uniswap-v2, uniswap-v3, sushiswap, aave, curve, pancakeswap, traderjoe)",
        example=["uniswap-v3", "aave"],
    )
    pools: List[str] = Field(
        ...,
        description="Pool addresses to watch",
        example=["0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"],
    )
    chain: int = Field(
        ...,
        description="Target blockchain chain ID",
        example=1,
    )
    threshold_rules: List[ThresholdRule] = Field(
        ...,
        description="Alert threshold configuration",
        example=[
            {"metric": "tvl_drop", "threshold_percent": 20.0, "timeframe_minutes": 60},
            {"metric": "apy_spike", "threshold_percent": 100.0, "timeframe_minutes": 60}
        ],
    )


class PoolMetric(BaseModel):
    """Current pool metrics"""
    pool_address: str
    protocol: str
    apy: float
    tvl_usd: float
    supply_apy: Optional[float] = None
    borrow_apy: Optional[float] = None
    fees_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    timestamp: str


class Delta(BaseModel):
    """Change metrics"""
    metric: str
    previous_value: float
    current_value: float
    change_percent: float
    timeframe_minutes: int


class Alert(BaseModel):
    """Alert notification"""
    pool_address: str
    protocol: str
    alert_type: str
    metric: str
    threshold_percent: float
    actual_change_percent: float
    previous_value: float
    current_value: float
    triggered_at: str
    severity: str


class WatchResponse(BaseModel):
    """Response with pool metrics and alerts"""
    pool_metrics: List[PoolMetric]
    deltas: List[Delta]
    alerts: List[Alert]
    timestamp: str


# Landing Page
@app.get("/", response_class=HTMLResponse)
@app.head("/")
async def root():
    """Landing page"""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Yield Pool Watcher</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #7e22ce 100%);
                color: #e8f0f2;
                line-height: 1.6;
                min-height: 100vh;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
            header {{
                background: linear-gradient(135deg, rgba(126, 34, 206, 0.2), rgba(79, 70, 229, 0.2));
                border: 2px solid rgba(126, 34, 206, 0.3);
                border-radius: 15px;
                padding: 40px;
                margin-bottom: 30px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            }}
            h1 {{
                color: #c084fc;
                font-size: 2.5em;
                margin-bottom: 10px;
            }}
            .subtitle {{
                color: #e9d5ff;
                font-size: 1.2em;
                margin-bottom: 15px;
            }}
            .badge {{
                display: inline-block;
                background: rgba(126, 34, 206, 0.2);
                border: 1px solid #c084fc;
                color: #c084fc;
                padding: 6px 15px;
                border-radius: 20px;
                font-size: 0.9em;
                margin-right: 10px;
                margin-top: 10px;
            }}
            .section {{
                background: rgba(30, 60, 114, 0.6);
                border: 1px solid rgba(126, 34, 206, 0.2);
                border-radius: 12px;
                padding: 30px;
                margin-bottom: 30px;
                backdrop-filter: blur(10px);
            }}
            h2 {{
                color: #c084fc;
                margin-bottom: 20px;
                font-size: 1.8em;
                border-bottom: 2px solid rgba(126, 34, 206, 0.3);
                padding-bottom: 10px;
            }}
            .endpoint {{
                background: rgba(15, 32, 39, 0.6);
                border-left: 4px solid #c084fc;
                padding: 20px;
                margin: 20px 0;
                border-radius: 8px;
            }}
            .method {{
                display: inline-block;
                background: #c084fc;
                color: #1e3c72;
                padding: 5px 12px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 0.85em;
                margin-right: 10px;
            }}
            code {{
                background: rgba(0, 0, 0, 0.3);
                color: #e9d5ff;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: 'Monaco', 'Courier New', monospace;
            }}
            pre {{
                background: rgba(0, 0, 0, 0.5);
                border: 1px solid rgba(126, 34, 206, 0.2);
                border-radius: 6px;
                padding: 15px;
                overflow-x: auto;
                margin: 10px 0;
            }}
            pre code {{
                background: none;
                padding: 0;
                display: block;
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 20px;
                margin: 20px 0;
            }}
            .card {{
                background: rgba(15, 32, 39, 0.6);
                border: 1px solid rgba(126, 34, 206, 0.2);
                border-radius: 10px;
                padding: 20px;
                transition: transform 0.3s;
            }}
            .card:hover {{
                transform: translateY(-4px);
                border-color: rgba(126, 34, 206, 0.4);
            }}
            .card h4 {{
                color: #c084fc;
                margin-bottom: 10px;
            }}
            a {{
                color: #c084fc;
                text-decoration: none;
                border-bottom: 1px solid transparent;
                transition: border-color 0.3s;
            }}
            a:hover {{
                border-bottom-color: #c084fc;
            }}
            footer {{
                text-align: center;
                padding: 30px;
                color: #e9d5ff;
                opacity: 0.8;
            }}
            .protocol-list {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin: 15px 0;
            }}
            .protocol-item {{
                background: rgba(126, 34, 206, 0.15);
                border: 1px solid rgba(192, 132, 252, 0.3);
                padding: 8px 16px;
                border-radius: 8px;
                font-size: 0.9em;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Yield Pool Watcher</h1>
                <p class="subtitle">Track APY and TVL Across DeFi Pools</p>
                <p>Monitor yield farming pools and lending markets with real-time alerts on sharp changes</p>
                <div>
                    <span class="badge">Live & Ready</span>
                    <span class="badge">Multi-Protocol</span>
                    <span class="badge">x402 Payments</span>
                    <span class="badge">Real-Time Alerts</span>
                </div>
            </header>

            <div class="section">
                <h2>What is Yield Pool Watcher?</h2>
                <p>
                    Yield Pool Watcher monitors APY (Annual Percentage Yield) and TVL (Total Value Locked)
                    across major DeFi protocols. Get alerted when metrics change beyond your configured
                    thresholds - perfect for yield farmers, liquidity providers, and DeFi analysts.
                </p>

                <div class="grid">
                    <div class="card">
                        <h4>Real-Time Monitoring</h4>
                        <p>Track pool metrics and detect changes within 1 block.</p>
                    </div>
                    <div class="card">
                        <h4>Multi-Protocol Support</h4>
                        <p>Uniswap, SushiSwap, Aave, Curve, PancakeSwap, TraderJoe.</p>
                    </div>
                    <div class="card">
                        <h4>Smart Alerts</h4>
                        <p>Configure custom thresholds for TVL drains, spikes, and APY changes.</p>
                    </div>
                    <div class="card">
                        <h4>7 Chains</h4>
                        <p>Ethereum, Polygon, Arbitrum, Optimism, Base, BSC, Avalanche.</p>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>Supported Protocols</h2>
                <div class="protocol-list">
                    <div class="protocol-item">Uniswap V2/V3</div>
                    <div class="protocol-item">SushiSwap</div>
                    <div class="protocol-item">Aave (Lending)</div>
                    <div class="protocol-item">Curve Finance</div>
                    <div class="protocol-item">PancakeSwap (BSC)</div>
                    <div class="protocol-item">TraderJoe (Avalanche)</div>
                </div>
            </div>

            <div class="section">
                <h2>API Endpoints</h2>

                <div class="endpoint">
                    <h3><span class="method">POST</span>/pools/watch</h3>
                    <p>Monitor pools and receive alerts on threshold breaches</p>
                    <pre><code>curl -X POST https://yield-pool-watcher-production.up.railway.app/pools/watch \\
  -H "Content-Type: application/json" \\
  -d '{{
    "protocol_ids": ["uniswap-v3", "aave"],
    "pools": ["0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"],
    "chain": 1,
    "threshold_rules": [
      {{"metric": "tvl_drop", "threshold_percent": 20.0, "timeframe_minutes": 60}},
      {{"metric": "apy_spike", "threshold_percent": 100.0, "timeframe_minutes": 60}}
    ]
  }}'</code></pre>
                </div>

                <div class="endpoint">
                    <h3><span class="method">GET</span>/protocols</h3>
                    <p>List all supported DeFi protocols</p>
                </div>

                <div class="endpoint">
                    <h3><span class="method">GET</span>/health</h3>
                    <p>Health check and operational status</p>
                </div>
            </div>

            <div class="section">
                <h2>Alert Types</h2>
                <div class="grid">
                    <div class="card">
                        <h4>TVL Drain</h4>
                        <p>Alert when TVL drops beyond threshold (e.g., 20% in 1 hour)</p>
                    </div>
                    <div class="card">
                        <h4>TVL Spike</h4>
                        <p>Alert when TVL increases sharply (e.g., 50% in 1 hour)</p>
                    </div>
                    <div class="card">
                        <h4>APY Spike</h4>
                        <p>Alert when APY increases significantly (e.g., 100% change)</p>
                    </div>
                    <div class="card">
                        <h4>APY Drop</h4>
                        <p>Alert when APY decreases (e.g., 50% drop)</p>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>x402 Micropayments</h2>
                <p>This service uses the <strong>x402 payment protocol</strong> for usage-based billing.</p>
                <div class="grid">
                    <div class="card">
                        <h4>Payment Details</h4>
                        <p><strong>Price:</strong> 0.05 USDC per request</p>
                        <p><strong>Address:</strong> <code>{payment_address}</code></p>
                        <p><strong>Network:</strong> Base</p>
                    </div>
                    <div class="card">
                        <h4>Status</h4>
                        <p><em>{"Currently in FREE MODE for testing" if free_mode else "Payment verification active"}</em></p>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>Documentation</h2>
                <p>Interactive API documentation:</p>
                <div style="margin: 20px 0;">
                    <a href="/docs" style="display: inline-block; background: rgba(126, 34, 206, 0.2); padding: 10px 20px; border-radius: 5px; margin-right: 10px;">Swagger UI</a>
                    <a href="/redoc" style="display: inline-block; background: rgba(126, 34, 206, 0.2); padding: 10px 20px; border-radius: 5px;">ReDoc</a>
                </div>
            </div>

            <footer>
                <p><strong>Built by DeganAI</strong></p>
                <p>Bounty #6 Submission for Daydreams AI Agent Bounties</p>
            </footer>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# AP2 (Agent Payments Protocol) Metadata
@app.get("/.well-known/agent.json")
@app.head("/.well-known/agent.json")
async def agent_metadata():
    """AP2 metadata - returns HTTP 200"""
    base_url = os.getenv("BASE_URL", "https://yield-pool-watcher-production.up.railway.app")

    agent_json = {
        "name": "Yield Pool Watcher",
        "description": "Track APY and TVL across DeFi pools and alert on sharp changes. Monitor Uniswap, Aave, Curve, and more across 7 chains.",
        "url": base_url.replace("https://", "http://") + "/",
        "version": "1.0.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": True,
            "extensions": [
                {
                    "uri": "https://github.com/google-agentic-commerce/ap2/tree/v0.1",
                    "description": "Agent Payments Protocol (AP2)",
                    "required": True,
                    "params": {"roles": ["merchant"]},
                }
            ],
        },
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json", "text/plain"],
        "skills": [
            {
                "id": "yield-pool-watcher",
                "name": "yield-pool-watcher",
                "description": "Monitor pool APY and TVL with configurable threshold alerts",
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
                "streaming": False,
                "x_input_schema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "properties": {
                        "protocol_ids": {
                            "description": "DeFi protocols to monitor",
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "pools": {
                            "description": "Pool addresses to watch",
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "chain": {
                            "description": "Target blockchain chain ID",
                            "type": "integer",
                        },
                        "threshold_rules": {
                            "description": "Alert threshold configuration",
                            "type": "array",
                            "items": {"type": "object"},
                        },
                    },
                    "required": ["protocol_ids", "pools", "chain", "threshold_rules"],
                    "additionalProperties": False,
                },
                "x_output_schema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "properties": {
                        "pool_metrics": {"type": "array"},
                        "deltas": {"type": "array"},
                        "alerts": {"type": "array"},
                    },
                    "required": ["pool_metrics", "deltas", "alerts"],
                    "additionalProperties": False,
                },
            }
        ],
        "supportsAuthenticatedExtendedCard": False,
        "entrypoints": {
            "yield-pool-watcher": {
                "description": "Track APY and TVL across DeFi pools with real-time alerts",
                "streaming": False,
                "input_schema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "properties": {
                        "protocol_ids": {"description": "Protocols to monitor", "type": "array", "items": {"type": "string"}},
                        "pools": {"description": "Pool addresses", "type": "array", "items": {"type": "string"}},
                        "chain": {"description": "Chain ID", "type": "integer"},
                        "threshold_rules": {"description": "Threshold rules", "type": "array", "items": {"type": "object"}},
                    },
                    "required": ["protocol_ids", "pools", "chain", "threshold_rules"],
                    "additionalProperties": False,
                },
                "output_schema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "properties": {
                        "pool_metrics": {"type": "array"},
                        "deltas": {"type": "array"},
                        "alerts": {"type": "array"},
                    },
                    "additionalProperties": False,
                },
                "pricing": {"invoke": "0.05 USDC"},
            }
        },
        "payments": [
            {
                "method": "x402",
                "payee": payment_address,
                "network": "base",
                "endpoint": "https://facilitator.daydreams.systems",
                "priceModel": {"default": "0.05"},
                "extensions": {
                    "x402": {"facilitatorUrl": "https://facilitator.daydreams.systems"}
                },
            }
        ],
    }

    return JSONResponse(content=agent_json, status_code=200)


# x402 Protocol Metadata
@app.get("/.well-known/x402")
@app.head("/.well-known/x402")
async def x402_metadata():
    """x402 protocol metadata - returns HTTP 402"""
    base_url = os.getenv("BASE_URL", "https://yield-pool-watcher-production.up.railway.app")

    metadata = {
        "x402Version": 1,
        "accepts": [
            {
                "scheme": "exact",
                "network": "base",
                "maxAmountRequired": "50000",
                "resource": f"{base_url}/entrypoints/yield-pool-watcher/invoke",
                "description": "Monitor pool APY and TVL with configurable threshold alerts",
                "mimeType": "application/json",
                "payTo": payment_address,
                "maxTimeoutSeconds": 30,
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            }
        ],
    }

    return JSONResponse(content=metadata, status_code=402)


# Health Check
@app.get("/health")
async def health():
    """Health check"""
    protocols = get_supported_protocols()
    return {
        "status": "healthy",
        "supported_protocols": len(protocols),
        "protocols": protocols,
        "free_mode": free_mode,
    }


# List Protocols
@app.get("/protocols")
async def list_protocols():
    """List all supported DeFi protocols"""
    protocols = get_supported_protocols()
    return {"protocols": protocols, "total": len(protocols)}


# Main Pool Monitoring Endpoint
@app.post("/pools/watch", response_model=WatchResponse)
async def watch_pools(request: WatchRequest):
    """
    Monitor pools and receive alerts on threshold breaches

    Tracks APY and TVL metrics across protocols and generates alerts when
    configured thresholds are exceeded.
    """
    try:
        logger.info(f"Watch request: protocols={request.protocol_ids}, pools={request.pools}, chain={request.chain}")

        # Get RPC URL
        rpc_url = RPC_URLS.get(request.chain)
        if not rpc_url:
            raise HTTPException(
                status_code=503,
                detail=f"No RPC URL configured for chain {request.chain}",
            )

        # Initialize components
        pool_monitor = PoolMonitor(rpc_url, request.chain)
        apy_calculator = APYCalculator()
        tvl_tracker = TVLTracker()
        alert_engine = AlertEngine()

        if not pool_monitor.is_connected:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to RPC for chain {request.chain}",
            )

        # Get current metrics for all pools
        pool_metrics = []
        for pool_address in request.pools:
            for protocol_id in request.protocol_ids:
                try:
                    # Get pool metrics
                    metrics = await pool_monitor.get_pool_metrics(
                        pool_address, protocol_id
                    )

                    if metrics:
                        pool_metrics.append(metrics)
                except Exception as e:
                    logger.error(f"Error getting metrics for pool {pool_address} on {protocol_id}: {e}")

        # Calculate deltas based on historical data
        deltas = []
        for metric in pool_metrics:
            pool_deltas = tvl_tracker.calculate_deltas(
                metric.pool_address,
                metric.tvl_usd,
                metric.apy,
            )
            deltas.extend(pool_deltas)

        # Check thresholds and generate alerts
        alerts = []
        for rule in request.threshold_rules:
            triggered_alerts = alert_engine.check_thresholds(
                pool_metrics,
                deltas,
                rule.metric,
                rule.threshold_percent,
                rule.timeframe_minutes,
            )
            alerts.extend(triggered_alerts)

        return WatchResponse(
            pool_metrics=pool_metrics,
            deltas=deltas,
            alerts=alerts,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pool monitoring error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


# AP2 Entrypoint - GET/HEAD for x402 discovery
@app.get("/entrypoints/yield-pool-watcher/invoke")
@app.head("/entrypoints/yield-pool-watcher/invoke")
async def entrypoint_watch_get():
    """
    x402 discovery endpoint - returns HTTP 402 for x402scan registration
    """
    base_url = os.getenv("BASE_URL", "https://yield-pool-watcher-production.up.railway.app")

    return JSONResponse(
        status_code=402,
        content={
            "x402Version": 1,
            "accepts": [{
                "scheme": "exact",
                "network": "base",
                "maxAmountRequired": "50000",
                "resource": f"{base_url}/entrypoints/yield-pool-watcher/invoke",
                "description": "Yield Pool Watcher - Monitor pool APY and TVL with threshold alerts",
                "mimeType": "application/json",
                "payTo": payment_address,
                "maxTimeoutSeconds": 30,
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "inputSchema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "properties": {
                        "protocol_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "DeFi protocols to monitor"
                        },
                        "pools": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Pool addresses to watch"
                        },
                        "chain": {
                            "type": "number",
                            "description": "Target blockchain chain ID"
                        }
                    },
                    "required": ["protocol_ids", "pools", "chain"]
                },
                "outputSchema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "description": "APY and TVL tracking with sharp change alerts",
                    "properties": {
                        "pool_metrics": {"type": "array"},
                        "deltas": {"type": "array"},
                        "alerts": {"type": "array"}
                    }
                }
            }]
        }
    )


# AP2 Entrypoint - POST for actual requests
@app.post("/entrypoints/yield-pool-watcher/invoke")
async def entrypoint_watch_post(request: Optional[WatchRequest] = None, x_payment_txhash: Optional[str] = None):
    """
    AP2 (Agent Payments Protocol) compatible entrypoint

    Returns 402 if no payment provided (FREE_MODE overrides this for testing).
    Calls the main /pools/watch endpoint with the same logic if payment is valid.
    """
    # Return 402 if no request body provided
    if request is None:
        return await entrypoint_watch_get()

    # In FREE_MODE, bypass payment check
    if not free_mode and not x_payment_txhash:
        return await entrypoint_watch_get()

    return await watch_pools(request)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
