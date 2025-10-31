"""
Protocol adapters for different DeFi protocols

Handles protocol-specific contract interactions and data formatting
"""
from typing import Dict, List, Optional, Any
from web3 import Web3
from web3.contract import Contract
import logging

logger = logging.getLogger(__name__)

# Supported protocols and their chain deployments
SUPPORTED_PROTOCOLS = {
    "uniswap-v2": {
        "name": "Uniswap V2",
        "type": "dex",
        "chains": [1, 137, 42161, 10, 8453, 56, 43114],
    },
    "uniswap-v3": {
        "name": "Uniswap V3",
        "type": "dex",
        "chains": [1, 137, 42161, 10, 8453],
    },
    "sushiswap": {
        "name": "SushiSwap",
        "type": "dex",
        "chains": [1, 137, 42161, 10, 8453, 56, 43114],
    },
    "aave": {
        "name": "Aave",
        "type": "lending",
        "chains": [1, 137, 42161, 10, 8453, 43114],
    },
    "curve": {
        "name": "Curve Finance",
        "type": "dex",
        "chains": [1, 137, 42161, 10],
    },
    "pancakeswap": {
        "name": "PancakeSwap",
        "type": "dex",
        "chains": [56],
    },
    "traderjoe": {
        "name": "TraderJoe",
        "type": "dex",
        "chains": [43114],
    },
}


def get_supported_protocols() -> List[str]:
    """Get list of supported protocol IDs"""
    return list(SUPPORTED_PROTOCOLS.keys())


def get_protocol_info(protocol_id: str) -> Optional[Dict[str, Any]]:
    """Get protocol information"""
    return SUPPORTED_PROTOCOLS.get(protocol_id)


# Minimal ABIs for contract interactions
UNISWAP_V2_PAIR_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"name": "reserve0", "type": "uint112"},
            {"name": "reserve1", "type": "uint112"},
            {"name": "blockTimestampLast", "type": "uint32"},
        ],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token0",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token1",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function",
    },
]

UNISWAP_V3_POOL_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"name": "sqrtPriceX96", "type": "uint160"},
            {"name": "tick", "type": "int24"},
            {"name": "observationIndex", "type": "uint16"},
            {"name": "observationCardinality", "type": "uint16"},
            {"name": "observationCardinalityNext", "type": "uint16"},
            {"name": "feeProtocol", "type": "uint8"},
            {"name": "unlocked", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "liquidity",
        "outputs": [{"name": "", "type": "uint128"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]

AAVE_V3_POOL_ABI = [
    {
        "inputs": [{"name": "asset", "type": "address"}],
        "name": "getReserveData",
        "outputs": [
            {
                "components": [
                    {"name": "configuration", "type": "uint256"},
                    {"name": "liquidityIndex", "type": "uint128"},
                    {"name": "currentLiquidityRate", "type": "uint128"},
                    {"name": "variableBorrowIndex", "type": "uint128"},
                    {"name": "currentVariableBorrowRate", "type": "uint128"},
                    {"name": "currentStableBorrowRate", "type": "uint128"},
                    {"name": "lastUpdateTimestamp", "type": "uint40"},
                    {"name": "id", "type": "uint16"},
                    {"name": "aTokenAddress", "type": "address"},
                    {"name": "stableDebtTokenAddress", "type": "address"},
                    {"name": "variableDebtTokenAddress", "type": "address"},
                    {"name": "interestRateStrategyAddress", "type": "address"},
                    {"name": "accruedToTreasury", "type": "uint128"},
                    {"name": "unbacked", "type": "uint128"},
                    {"name": "isolationModeTotalDebt", "type": "uint128"},
                ],
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
]


class ProtocolAdapter:
    """Base protocol adapter"""

    def __init__(self, w3: Web3, chain_id: int):
        self.w3 = w3
        self.chain_id = chain_id

    def get_pool_data(self, pool_address: str) -> Optional[Dict[str, Any]]:
        """Get pool data - to be implemented by subclasses"""
        raise NotImplementedError


class UniswapV2Adapter(ProtocolAdapter):
    """Adapter for Uniswap V2 style DEXes"""

    def get_pool_data(self, pool_address: str) -> Optional[Dict[str, Any]]:
        """Get Uniswap V2 pool data"""
        try:
            pool_address = Web3.to_checksum_address(pool_address)
            contract = self.w3.eth.contract(address=pool_address, abi=UNISWAP_V2_PAIR_ABI)

            # Get reserves
            reserves = contract.functions.getReserves().call()
            token0 = contract.functions.token0().call()
            token1 = contract.functions.token1().call()

            return {
                "reserve0": reserves[0],
                "reserve1": reserves[1],
                "token0": token0,
                "token1": token1,
                "type": "v2",
            }
        except Exception as e:
            logger.error(f"Error getting Uniswap V2 pool data: {e}")
            return None


class UniswapV3Adapter(ProtocolAdapter):
    """Adapter for Uniswap V3 pools"""

    def get_pool_data(self, pool_address: str) -> Optional[Dict[str, Any]]:
        """Get Uniswap V3 pool data"""
        try:
            pool_address = Web3.to_checksum_address(pool_address)
            contract = self.w3.eth.contract(address=pool_address, abi=UNISWAP_V3_POOL_ABI)

            # Get slot0 and liquidity
            slot0 = contract.functions.slot0().call()
            liquidity = contract.functions.liquidity().call()
            token0 = contract.functions.token0().call()
            token1 = contract.functions.token1().call()

            return {
                "sqrtPriceX96": slot0[0],
                "tick": slot0[1],
                "liquidity": liquidity,
                "token0": token0,
                "token1": token1,
                "type": "v3",
            }
        except Exception as e:
            logger.error(f"Error getting Uniswap V3 pool data: {e}")
            return None


class AaveAdapter(ProtocolAdapter):
    """Adapter for Aave lending protocol"""

    # Aave V3 Pool addresses by chain
    POOL_ADDRESSES = {
        1: "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",  # Ethereum
        137: "0x794a61358D6845594F94dc1DB02A252b5b4814aD",  # Polygon
        42161: "0x794a61358D6845594F94dc1DB02A252b5b4814aD",  # Arbitrum
        10: "0x794a61358D6845594F94dc1DB02A252b5b4814aD",  # Optimism
        8453: "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5",  # Base
        43114: "0x794a61358D6845594F94dc1DB02A252b5b4814aD",  # Avalanche
    }

    def get_pool_data(self, asset_address: str) -> Optional[Dict[str, Any]]:
        """Get Aave reserve data for an asset"""
        try:
            asset_address = Web3.to_checksum_address(asset_address)
            pool_address = self.POOL_ADDRESSES.get(self.chain_id)

            if not pool_address:
                logger.error(f"Aave not supported on chain {self.chain_id}")
                return None

            pool_address = Web3.to_checksum_address(pool_address)
            contract = self.w3.eth.contract(address=pool_address, abi=AAVE_V3_POOL_ABI)

            # Get reserve data
            reserve_data = contract.functions.getReserveData(asset_address).call()

            # Extract rates (in ray units - 27 decimals)
            RAY = 10**27
            supply_rate = reserve_data[2] / RAY  # liquidityRate
            borrow_rate = reserve_data[4] / RAY  # variableBorrowRate

            return {
                "supply_rate": supply_rate,
                "borrow_rate": borrow_rate,
                "aToken": reserve_data[8],
                "asset": asset_address,
                "type": "lending",
            }
        except Exception as e:
            logger.error(f"Error getting Aave pool data: {e}")
            return None


class CurveAdapter(ProtocolAdapter):
    """Adapter for Curve Finance pools"""

    def get_pool_data(self, pool_address: str) -> Optional[Dict[str, Any]]:
        """Get Curve pool data"""
        try:
            # Curve pools have varying ABIs, so we'll use a simplified approach
            # In production, would need more robust handling
            pool_address = Web3.to_checksum_address(pool_address)

            # Get basic balance data
            balance = self.w3.eth.get_balance(pool_address)

            return {
                "balance": balance,
                "type": "curve",
            }
        except Exception as e:
            logger.error(f"Error getting Curve pool data: {e}")
            return None


def get_protocol_adapter(protocol_id: str, w3: Web3, chain_id: int) -> Optional[ProtocolAdapter]:
    """Get the appropriate protocol adapter"""
    adapters = {
        "uniswap-v2": UniswapV2Adapter,
        "sushiswap": UniswapV2Adapter,  # Uses V2 interface
        "pancakeswap": UniswapV2Adapter,  # Uses V2 interface
        "traderjoe": UniswapV2Adapter,  # Uses V2 interface
        "uniswap-v3": UniswapV3Adapter,
        "aave": AaveAdapter,
        "curve": CurveAdapter,
    }

    adapter_class = adapters.get(protocol_id)
    if adapter_class:
        return adapter_class(w3, chain_id)

    return None


def get_token_info(w3: Web3, token_address: str) -> Optional[Dict[str, Any]]:
    """Get token information (decimals, symbol)"""
    try:
        token_address = Web3.to_checksum_address(token_address)
        contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)

        decimals = contract.functions.decimals().call()
        symbol = contract.functions.symbol().call()

        return {
            "address": token_address,
            "decimals": decimals,
            "symbol": symbol,
        }
    except Exception as e:
        logger.error(f"Error getting token info: {e}")
        return None
