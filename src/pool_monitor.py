"""
Pool monitor for tracking metrics across DeFi protocols
"""
from typing import Optional, Dict, Any
from web3 import Web3
from datetime import datetime
import logging

from src.protocol_adapters import get_protocol_adapter, get_token_info
from src.apy_calculator import APYCalculator
from src.tvl_tracker import TVLTracker
from src.data_sources import DataSourceManager

logger = logging.getLogger(__name__)


class PoolMetric:
    """Pool metric data structure"""

    def __init__(
        self,
        pool_address: str,
        protocol: str,
        apy: float,
        tvl_usd: float,
        supply_apy: Optional[float] = None,
        borrow_apy: Optional[float] = None,
        fees_24h: Optional[float] = None,
        volume_24h: Optional[float] = None,
        timestamp: str = None,
    ):
        self.pool_address = pool_address
        self.protocol = protocol
        self.apy = apy
        self.tvl_usd = tvl_usd
        self.supply_apy = supply_apy
        self.borrow_apy = borrow_apy
        self.fees_24h = fees_24h
        self.volume_24h = volume_24h
        self.timestamp = timestamp or datetime.utcnow().isoformat() + "Z"


class PoolMonitor:
    """Monitor DeFi pools for metrics and changes"""

    def __init__(self, rpc_url: str, chain_id: int):
        """Initialize pool monitor"""
        self.rpc_url = rpc_url
        self.chain_id = chain_id
        self.w3 = None
        self.is_connected = False
        self.apy_calculator = APYCalculator()
        self.tvl_tracker = TVLTracker()
        self.data_sources = DataSourceManager()

        self._connect()

    def _connect(self):
        """Connect to blockchain RPC"""
        try:
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            self.is_connected = self.w3.is_connected()

            if self.is_connected:
                logger.info(f"Connected to chain {self.chain_id}")
            else:
                logger.error(f"Failed to connect to chain {self.chain_id}")

        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.is_connected = False

    async def get_pool_metrics(
        self, pool_address: str, protocol_id: str
    ) -> Optional[PoolMetric]:
        """Get current metrics for a pool"""
        try:
            if not self.is_connected:
                logger.error("Not connected to RPC")
                return None

            # Get protocol adapter
            adapter = get_protocol_adapter(protocol_id, self.w3, self.chain_id)
            if not adapter:
                logger.error(f"No adapter found for protocol {protocol_id}")
                return None

            # Get on-chain pool data
            pool_data = adapter.get_pool_data(pool_address)
            if not pool_data:
                logger.error(f"Failed to get pool data for {pool_address}")
                return None

            # Calculate TVL
            tvl_usd = await self._calculate_tvl(pool_address, pool_data, protocol_id)

            # Calculate APY
            apy_data = await self._calculate_apy(pool_address, pool_data, protocol_id)

            # Create metric object
            metric = PoolMetric(
                pool_address=pool_address,
                protocol=protocol_id,
                apy=apy_data.get("apy", 0.0),
                tvl_usd=tvl_usd,
                supply_apy=apy_data.get("supply_apy"),
                borrow_apy=apy_data.get("borrow_apy"),
                fees_24h=apy_data.get("fees_24h"),
                volume_24h=apy_data.get("volume_24h"),
            )

            return metric

        except Exception as e:
            logger.error(f"Error getting pool metrics: {e}", exc_info=True)
            return None

    async def _calculate_tvl(
        self, pool_address: str, pool_data: Dict[str, Any], protocol_id: str
    ) -> float:
        """Calculate TVL for a pool"""
        try:
            pool_type = pool_data.get("type")

            if pool_type == "v2":
                # Uniswap V2 style - calculate from reserves
                return await self.tvl_tracker.calculate_v2_tvl(
                    self.w3,
                    pool_data["token0"],
                    pool_data["token1"],
                    pool_data["reserve0"],
                    pool_data["reserve1"],
                )

            elif pool_type == "v3":
                # Uniswap V3 - calculate from liquidity
                return await self.tvl_tracker.calculate_v3_tvl(
                    self.w3,
                    pool_data["token0"],
                    pool_data["token1"],
                    pool_data["liquidity"],
                    pool_data["sqrtPriceX96"],
                )

            elif pool_type == "lending":
                # Aave - get TVL from DeFi Llama
                return await self.data_sources.get_aave_tvl(pool_address, self.chain_id)

            elif pool_type == "curve":
                # Curve - get TVL from DeFi Llama
                return await self.data_sources.get_curve_tvl(pool_address, self.chain_id)

            else:
                logger.warning(f"Unknown pool type: {pool_type}")
                return 0.0

        except Exception as e:
            logger.error(f"Error calculating TVL: {e}")
            return 0.0

    async def _calculate_apy(
        self, pool_address: str, pool_data: Dict[str, Any], protocol_id: str
    ) -> Dict[str, Any]:
        """Calculate APY for a pool"""
        try:
            pool_type = pool_data.get("type")

            if pool_type in ["v2", "v3"]:
                # DEX pool - calculate from fees
                return await self.apy_calculator.calculate_dex_apy(
                    pool_address, protocol_id, self.chain_id
                )

            elif pool_type == "lending":
                # Lending pool - use rates from contract
                supply_rate = pool_data.get("supply_rate", 0)
                borrow_rate = pool_data.get("borrow_rate", 0)

                # Convert to APY (rates are per second, annualize)
                supply_apy = self.apy_calculator.annualize_rate(supply_rate)
                borrow_apy = self.apy_calculator.annualize_rate(borrow_rate)

                return {
                    "apy": supply_apy,  # Use supply APY as main APY
                    "supply_apy": supply_apy,
                    "borrow_apy": borrow_apy,
                }

            elif pool_type == "curve":
                # Curve - get APY from DeFi Llama
                return await self.data_sources.get_curve_apy(pool_address, self.chain_id)

            else:
                logger.warning(f"Unknown pool type for APY: {pool_type}")
                return {"apy": 0.0}

        except Exception as e:
            logger.error(f"Error calculating APY: {e}")
            return {"apy": 0.0}
