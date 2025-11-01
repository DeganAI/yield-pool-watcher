"""
x402 Payment Verification Middleware

Validates payment proofs for x402 micropayment protocol
"""
import logging
import json
import base64
import aiohttp
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class X402Middleware(BaseHTTPMiddleware):
    """
    Middleware for x402 payment verification

    Verifies payments via the Daydreams facilitator before allowing access
    """

    def __init__(
        self,
        app,
        payment_address: str,
        base_url: str,
        facilitator_url: str = "https://facilitator.daydreams.systems",
        free_mode: bool = False,
    ):
        super().__init__(app)
        self.payment_address = payment_address
        self.base_url = base_url
        self.facilitator_url = facilitator_url
        self.free_mode = free_mode

        logger.info(f"x402 Middleware initialized (FREE_MODE={free_mode}, facilitator={facilitator_url})")

    async def verify_payment(
        self,
        payment_header: str,
        resource_url: str,
        amount_required: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Verify payment via facilitator

        Returns: (is_valid, error_message)
        """
        try:
            # Decode X-Payment header
            try:
                payment_payload = json.loads(base64.b64decode(payment_header))
            except Exception as e:
                return False, f"Invalid payment header format: {str(e)}"

            # Construct verification request
            verification_request = {
                "paymentPayload": payment_payload,
                "paymentRequirements": {
                    "scheme": "exact",
                    "network": "base",
                    "maxAmountRequired": amount_required,
                    "resource": resource_url,
                    "description": "x402 micropayment",
                    "mimeType": "application/json",
                    "payTo": self.payment_address,
                    "maxTimeoutSeconds": 30,
                    "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC on Base
                }
            }

            # Call facilitator /verify endpoint
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.facilitator_url}/verify",
                    json=verification_request,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Facilitator returned {response.status}: {error_text}")
                        return False, f"Payment verification failed: {error_text}"

                    result = await response.json()

                    if result.get("isValid"):
                        logger.info(f"Payment verified for payer: {result.get('payer')}")
                        return True, None
                    else:
                        reason = result.get("invalidReason", "Unknown reason")
                        logger.warning(f"Payment invalid: {reason}")
                        return False, reason

        except aiohttp.ClientError as e:
            logger.error(f"Facilitator connection error: {str(e)}")
            return False, f"Payment verification service unavailable: {str(e)}"
        except Exception as e:
            logger.error(f"Payment verification error: {str(e)}")
            return False, f"Payment verification error: {str(e)}"

    def create_402_response(self, resource_url: str, description: str) -> JSONResponse:
        """Create HTTP 402 Payment Required response"""
        metadata = {
            "x402Version": 1,
            "accepts": [
                {
                    "scheme": "exact",
                    "network": "base",
                    "maxAmountRequired": "50000",  # 0.05 USDC (6 decimals)
                    "resource": resource_url,
                    "description": description,
                    "mimeType": "application/json",
                    "payTo": self.payment_address,
                    "maxTimeoutSeconds": 30,
                    "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC on Base
                }
            ]
        }
        return JSONResponse(content=metadata, status_code=402)

    async def dispatch(self, request: Request, call_next):
        """Process request and verify payment if required"""

        # Skip payment verification in free mode
        if self.free_mode:
            logger.debug("FREE_MODE enabled, skipping payment verification")
            return await call_next(request)

        # Skip verification for health check and metadata endpoints
        skip_paths = ["/health", "/.well-known", "/docs", "/redoc", "/openapi.json", "/"]
        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)

        # Check for payment endpoints (those that require payment)
        # These are typically POST endpoints that provide actual functionality
        requires_payment = (
            request.method == "POST" and
            "/entrypoints/" in request.url.path
        )

        if not requires_payment:
            # Allow GET requests through (they're for discovery/metadata)
            return await call_next(request)

        # Check for X-Payment header
        payment_header = request.headers.get("X-Payment")

        if not payment_header:
            logger.info(f"Payment required for {request.url.path}, no X-Payment header provided")
            return self.create_402_response(
                resource_url=str(request.url),
                description="Payment required to access this resource"
            )

        # Verify payment via facilitator
        is_valid, error_message = await self.verify_payment(
            payment_header=payment_header,
            resource_url=str(request.url),
            amount_required="50000"  # 0.05 USDC
        )

        if not is_valid:
            logger.warning(f"Payment verification failed: {error_message}")
            return JSONResponse(
                status_code=402,
                content={
                    "error": "Payment verification failed",
                    "message": error_message,
                    "x402Version": 1,
                    "accepts": [{
                        "scheme": "exact",
                        "network": "base",
                        "maxAmountRequired": "50000",
                        "resource": str(request.url),
                        "description": "Payment required to access this resource",
                        "mimeType": "application/json",
                        "payTo": self.payment_address,
                        "maxTimeoutSeconds": 30,
                        "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                    }]
                }
            )

        # Payment verified, proceed with request
        logger.info(f"Payment verified, processing request to {request.url.path}")
        return await call_next(request)
