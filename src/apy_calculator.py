"""
APY calculator for DeFi pools

Handles APY calculations for DEX pools (from fees) and lending pools (from rates)
"""
from typing import Dict, Any
import logging

from src.data_sources import DataSourceManager

logger = logging.getLogger(__name__)


class APYCalculator:
    """Calculate APY for different pool types"""

    def __init__(self):
        self.data_sources = DataSourceManager()

    async def calculate_dex_apy(
        self, pool_address: str, protocol_id: str, chain_id: int
    ) -> Dict[str, Any]:
        """
        Calculate APY for DEX pools based on trading fees

        For DEX pools, APY is calculated from:
        1. 24h trading volume and fees
        2. Pool liquidity (TVL)
        3. Fee rate (e.g., 0.3% for Uniswap V2, variable for V3)

        APY = (24h fees / TVL) * 365 * 100
        """
        try:
            # Get pool data from DeFi Llama or The Graph
            pool_data = await self.data_sources.get_pool_stats(
                pool_address, protocol_id, chain_id
            )

            if not pool_data:
                logger.warning(f"No pool data available for {pool_address}")
                return {"apy": 0.0}

            fees_24h = pool_data.get("fees_24h", 0)
            volume_24h = pool_data.get("volume_24h", 0)
            tvl = pool_data.get("tvl", 0)

            if tvl > 0 and fees_24h > 0:
                # Calculate daily return
                daily_return = fees_24h / tvl

                # Annualize (simple, not compounded)
                apy = daily_return * 365 * 100

                return {
                    "apy": apy,
                    "fees_24h": fees_24h,
                    "volume_24h": volume_24h,
                }
            else:
                return {"apy": 0.0, "fees_24h": fees_24h, "volume_24h": volume_24h}

        except Exception as e:
            logger.error(f"Error calculating DEX APY: {e}")
            return {"apy": 0.0}

    def annualize_rate(self, rate: float) -> float:
        """
        Convert a per-second rate to APY

        For Aave and other lending protocols, rates are typically per second.
        APY = ((1 + rate)^seconds_per_year - 1) * 100

        For simplicity, we use: APY ≈ rate * seconds_per_year * 100
        """
        try:
            SECONDS_PER_YEAR = 365.25 * 24 * 60 * 60

            # Simple annualization
            apy = rate * SECONDS_PER_YEAR * 100

            return apy

        except Exception as e:
            logger.error(f"Error annualizing rate: {e}")
            return 0.0

    def compound_apy(self, daily_rate: float, compounds_per_year: int = 365) -> float:
        """
        Calculate compound APY from daily rate

        APY = ((1 + daily_rate)^compounds_per_year - 1) * 100
        """
        try:
            apy = (pow(1 + daily_rate, compounds_per_year) - 1) * 100
            return apy
        except Exception as e:
            logger.error(f"Error calculating compound APY: {e}")
            return 0.0
