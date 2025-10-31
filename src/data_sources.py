"""
Data source integrations for external APIs

Handles DeFi Llama, CoinGecko, and The Graph integrations
"""
from typing import Dict, List, Optional, Any
import httpx
import logging

logger = logging.getLogger(__name__)


class DataSourceManager:
    """Manage external data source integrations"""

    def __init__(self):
        self.coingecko_base = "https://api.coingecko.com/api/v3"
        self.defillama_base = "https://api.llama.fi"
        # Cache for token prices (in production, use Redis with TTL)
        self.price_cache: Dict[str, float] = {}

    async def get_token_prices(self, token_addresses: List[str]) -> Dict[str, float]:
        """
        Get token prices from CoinGecko

        Returns dict mapping address (lowercase) to USD price
        """
        prices = {}

        try:
            # Check cache first
            uncached = []
            for addr in token_addresses:
                addr_lower = addr.lower()
                if addr_lower in self.price_cache:
                    prices[addr_lower] = self.price_cache[addr_lower]
                else:
                    uncached.append(addr)

            if not uncached:
                return prices

            # Fetch uncached prices
            # CoinGecko free API has rate limits, so we batch carefully
            async with httpx.AsyncClient(timeout=10.0) as client:
                # For simplicity, use hardcoded prices for common tokens
                # In production, would query CoinGecko properly
                known_prices = {
                    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": 3000.0,  # WETH
                    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": 1.0,  # USDC
                    "0xdac17f958d2ee523a2206206994597c13d831ec7": 1.0,  # USDT
                    "0x6b175474e89094c44da98b954eedeac495271d0f": 1.0,  # DAI
                    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": 65000.0,  # WBTC
                }

                for addr in uncached:
                    addr_lower = addr.lower()
                    price = known_prices.get(addr_lower, 0.0)
                    prices[addr_lower] = price
                    self.price_cache[addr_lower] = price

        except Exception as e:
            logger.error(f"Error fetching token prices: {e}")

        return prices

    async def get_pool_stats(
        self, pool_address: str, protocol_id: str, chain_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get pool statistics from DeFi Llama or The Graph

        Returns fees, volume, and TVL data
        """
        try:
            # In production, would query The Graph subgraphs for each protocol
            # For now, return mock data
            return {
                "fees_24h": 10000.0,  # $10k in fees
                "volume_24h": 1000000.0,  # $1M volume
                "tvl": 5000000.0,  # $5M TVL
            }

        except Exception as e:
            logger.error(f"Error fetching pool stats: {e}")
            return None

    async def get_aave_tvl(self, asset_address: str, chain_id: int) -> float:
        """Get Aave TVL from DeFi Llama"""
        try:
            # In production, query DeFi Llama API
            # Mock TVL for now
            return 1000000.0

        except Exception as e:
            logger.error(f"Error fetching Aave TVL: {e}")
            return 0.0

    async def get_curve_tvl(self, pool_address: str, chain_id: int) -> float:
        """Get Curve pool TVL from DeFi Llama"""
        try:
            # In production, query DeFi Llama API
            # Mock TVL for now
            return 2000000.0

        except Exception as e:
            logger.error(f"Error fetching Curve TVL: {e}")
            return 0.0

    async def get_curve_apy(self, pool_address: str, chain_id: int) -> Dict[str, Any]:
        """Get Curve pool APY from DeFi Llama"""
        try:
            # In production, query Curve API or DeFi Llama
            # Mock APY for now
            return {
                "apy": 5.5,  # 5.5% base APY
                "fees_24h": 5000.0,
                "volume_24h": 500000.0,
            }

        except Exception as e:
            logger.error(f"Error fetching Curve APY: {e}")
            return {"apy": 0.0}

    async def get_defillama_protocol_tvl(self, protocol: str) -> Optional[float]:
        """
        Get protocol TVL from DeFi Llama

        Example: https://api.llama.fi/protocol/uniswap
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.defillama_base}/protocol/{protocol}")

                if response.status_code == 200:
                    data = response.json()
                    return data.get("tvl")

                logger.warning(f"DeFi Llama API returned {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching DeFi Llama TVL: {e}")
            return None

    async def get_coingecko_price(self, token_address: str, chain: str = "ethereum") -> Optional[float]:
        """
        Get token price from CoinGecko

        Example: https://api.coingecko.com/api/v3/simple/token_price/ethereum?contract_addresses=0x...&vs_currencies=usd
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.coingecko_base}/simple/token_price/{chain}",
                    params={
                        "contract_addresses": token_address,
                        "vs_currencies": "usd"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    token_data = data.get(token_address.lower(), {})
                    return token_data.get("usd")

                logger.warning(f"CoinGecko API returned {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching CoinGecko price: {e}")
            return None
