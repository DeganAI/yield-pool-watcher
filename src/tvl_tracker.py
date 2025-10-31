"""
TVL tracker for calculating and monitoring Total Value Locked

Handles TVL calculations for different pool types and tracks historical data
"""
from typing import Dict, Any, List, Optional
from web3 import Web3
from datetime import datetime, timedelta
import logging

from src.data_sources import DataSourceManager

logger = logging.getLogger(__name__)


class Delta:
    """Delta data structure"""

    def __init__(
        self,
        metric: str,
        previous_value: float,
        current_value: float,
        change_percent: float,
        timeframe_minutes: int,
    ):
        self.metric = metric
        self.previous_value = previous_value
        self.current_value = current_value
        self.change_percent = change_percent
        self.timeframe_minutes = timeframe_minutes


class TVLTracker:
    """Track TVL and calculate changes over time"""

    def __init__(self):
        self.data_sources = DataSourceManager()
        # In-memory storage for historical data (in production, use Redis or DB)
        self.historical_data: Dict[str, List[Dict[str, Any]]] = {}

    async def calculate_v2_tvl(
        self,
        w3: Web3,
        token0: str,
        token1: str,
        reserve0: int,
        reserve1: int,
    ) -> float:
        """
        Calculate TVL for Uniswap V2 style pools

        TVL = (reserve0 * price0 + reserve1 * price1)
        """
        try:
            # Get token decimals
            from src.protocol_adapters import get_token_info

            token0_info = get_token_info(w3, token0)
            token1_info = get_token_info(w3, token1)

            if not token0_info or not token1_info:
                logger.error("Failed to get token info")
                return 0.0

            # Normalize reserves by decimals
            reserve0_normalized = reserve0 / (10 ** token0_info["decimals"])
            reserve1_normalized = reserve1 / (10 ** token1_info["decimals"])

            # Get token prices in USD
            prices = await self.data_sources.get_token_prices([token0, token1])

            price0 = prices.get(token0.lower(), 0)
            price1 = prices.get(token1.lower(), 0)

            # Calculate TVL
            tvl = (reserve0_normalized * price0) + (reserve1_normalized * price1)

            return tvl

        except Exception as e:
            logger.error(f"Error calculating V2 TVL: {e}")
            return 0.0

    async def calculate_v3_tvl(
        self,
        w3: Web3,
        token0: str,
        token1: str,
        liquidity: int,
        sqrtPriceX96: int,
    ) -> float:
        """
        Calculate TVL for Uniswap V3 pools

        This is a simplified calculation. Full V3 TVL calculation requires
        iterating over all positions and tick ranges.
        """
        try:
            # Get token decimals
            from src.protocol_adapters import get_token_info

            token0_info = get_token_info(w3, token0)
            token1_info = get_token_info(w3, token1)

            if not token0_info or not token1_info:
                logger.error("Failed to get token info")
                return 0.0

            # Get token prices
            prices = await self.data_sources.get_token_prices([token0, token1])
            price0 = prices.get(token0.lower(), 0)
            price1 = prices.get(token1.lower(), 0)

            # Simplified calculation using liquidity
            # In production, would need more accurate V3 math
            Q96 = 2**96

            # Calculate price from sqrtPriceX96
            price_ratio = (sqrtPriceX96 / Q96) ** 2

            # Estimate amounts (simplified)
            decimals_diff = token1_info["decimals"] - token0_info["decimals"]
            adjusted_price = price_ratio * (10**decimals_diff)

            # Rough TVL estimate
            liquidity_normalized = liquidity / (10 ** token0_info["decimals"])
            tvl_estimate = liquidity_normalized * (price0 + price1 * adjusted_price)

            return max(tvl_estimate, 0.0)

        except Exception as e:
            logger.error(f"Error calculating V3 TVL: {e}")
            return 0.0

    def store_snapshot(self, pool_address: str, tvl: float, apy: float):
        """Store a snapshot of pool metrics"""
        try:
            timestamp = datetime.utcnow()

            snapshot = {
                "timestamp": timestamp,
                "tvl": tvl,
                "apy": apy,
            }

            if pool_address not in self.historical_data:
                self.historical_data[pool_address] = []

            self.historical_data[pool_address].append(snapshot)

            # Keep only last 24 hours of data
            cutoff = timestamp - timedelta(hours=24)
            self.historical_data[pool_address] = [
                s for s in self.historical_data[pool_address] if s["timestamp"] > cutoff
            ]

        except Exception as e:
            logger.error(f"Error storing snapshot: {e}")

    def calculate_deltas(
        self, pool_address: str, current_tvl: float, current_apy: float
    ) -> List[Delta]:
        """Calculate deltas for different timeframes"""
        try:
            # Store current snapshot
            self.store_snapshot(pool_address, current_tvl, current_apy)

            deltas = []
            timeframes = [5, 15, 60]  # minutes

            history = self.historical_data.get(pool_address, [])
            if not history or len(history) < 2:
                return deltas

            current_time = datetime.utcnow()

            for timeframe_minutes in timeframes:
                # Find snapshot closest to timeframe ago
                target_time = current_time - timedelta(minutes=timeframe_minutes)

                closest_snapshot = None
                min_diff = timedelta(days=1)

                for snapshot in history:
                    diff = abs(snapshot["timestamp"] - target_time)
                    if diff < min_diff:
                        min_diff = diff
                        closest_snapshot = snapshot

                if closest_snapshot and min_diff < timedelta(minutes=timeframe_minutes / 2):
                    # Calculate TVL delta
                    prev_tvl = closest_snapshot["tvl"]
                    if prev_tvl > 0:
                        tvl_change = ((current_tvl - prev_tvl) / prev_tvl) * 100

                        deltas.append(
                            Delta(
                                metric="tvl",
                                previous_value=prev_tvl,
                                current_value=current_tvl,
                                change_percent=tvl_change,
                                timeframe_minutes=timeframe_minutes,
                            )
                        )

                    # Calculate APY delta
                    prev_apy = closest_snapshot["apy"]
                    if prev_apy > 0:
                        apy_change = ((current_apy - prev_apy) / prev_apy) * 100

                        deltas.append(
                            Delta(
                                metric="apy",
                                previous_value=prev_apy,
                                current_value=current_apy,
                                change_percent=apy_change,
                                timeframe_minutes=timeframe_minutes,
                            )
                        )

            return deltas

        except Exception as e:
            logger.error(f"Error calculating deltas: {e}")
            return []
