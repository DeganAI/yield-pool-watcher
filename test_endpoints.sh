#!/bin/bash

# Test script for Yield Pool Watcher endpoints
# Tests AP2/x402 compliance and basic functionality

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"

echo -e "${YELLOW}Testing Yield Pool Watcher${NC}"
echo "Base URL: $BASE_URL"
echo ""

# Test 1: Health Check
echo -e "${YELLOW}Test 1: Health Check${NC}"
response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")
if [ "$response" -eq 200 ]; then
    echo -e "${GREEN}✓ Health check passed (HTTP $response)${NC}"
else
    echo -e "${RED}✗ Health check failed (HTTP $response)${NC}"
    exit 1
fi
echo ""

# Test 2: Landing Page
echo -e "${YELLOW}Test 2: Landing Page${NC}"
response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/")
if [ "$response" -eq 200 ]; then
    echo -e "${GREEN}✓ Landing page loaded (HTTP $response)${NC}"
else
    echo -e "${RED}✗ Landing page failed (HTTP $response)${NC}"
    exit 1
fi
echo ""

# Test 3: AP2 Metadata (agent.json)
echo -e "${YELLOW}Test 3: AP2 Metadata (/.well-known/agent.json)${NC}"
response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/.well-known/agent.json")
if [ "$response" -eq 200 ]; then
    echo -e "${GREEN}✓ agent.json returned HTTP 200${NC}"

    # Check structure
    agent_json=$(curl -s "$BASE_URL/.well-known/agent.json")

    # Verify url uses http://
    url=$(echo "$agent_json" | jq -r '.url')
    if [[ "$url" == http://* ]]; then
        echo -e "${GREEN}✓ url field uses http://${NC}"
    else
        echo -e "${RED}✗ url field must use http:// not https://${NC}"
        exit 1
    fi

    # Verify facilitator endpoint
    endpoint=$(echo "$agent_json" | jq -r '.payments[0].endpoint')
    if [ "$endpoint" == "https://facilitator.daydreams.systems" ]; then
        echo -e "${GREEN}✓ Payment endpoint correct${NC}"
    else
        echo -e "${RED}✗ Payment endpoint incorrect: $endpoint${NC}"
        exit 1
    fi

else
    echo -e "${RED}✗ agent.json failed (HTTP $response)${NC}"
    exit 1
fi
echo ""

# Test 4: x402 Metadata
echo -e "${YELLOW}Test 4: x402 Metadata (/.well-known/x402)${NC}"
response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/.well-known/x402")
if [ "$response" -eq 402 ]; then
    echo -e "${GREEN}✓ x402 metadata returned HTTP 402${NC}"

    # Check structure
    x402_json=$(curl -s "$BASE_URL/.well-known/x402")

    # Verify required fields
    version=$(echo "$x402_json" | jq -r '.x402Version')
    scheme=$(echo "$x402_json" | jq -r '.accepts[0].scheme')
    network=$(echo "$x402_json" | jq -r '.accepts[0].network')
    asset=$(echo "$x402_json" | jq -r '.accepts[0].asset')

    if [ "$version" == "1" ]; then
        echo -e "${GREEN}✓ x402Version correct${NC}"
    else
        echo -e "${RED}✗ x402Version incorrect: $version${NC}"
        exit 1
    fi

    if [ "$network" == "base" ]; then
        echo -e "${GREEN}✓ Network is base${NC}"
    else
        echo -e "${RED}✗ Network incorrect: $network${NC}"
        exit 1
    fi

    if [ "$asset" == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913" ]; then
        echo -e "${GREEN}✓ Base USDC asset correct${NC}"
    else
        echo -e "${RED}✗ Asset incorrect: $asset${NC}"
        exit 1
    fi

else
    echo -e "${RED}✗ x402 metadata failed (HTTP $response)${NC}"
    exit 1
fi
echo ""

# Test 5: AP2 Entrypoint (GET/HEAD)
echo -e "${YELLOW}Test 5: AP2 Entrypoint GET (should return 402)${NC}"
response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/entrypoints/yield-pool-watcher/invoke")
if [ "$response" -eq 402 ]; then
    echo -e "${GREEN}✓ Entrypoint GET returned HTTP 402${NC}"
else
    echo -e "${RED}✗ Entrypoint GET failed (HTTP $response)${NC}"
    exit 1
fi
echo ""

# Test 6: HEAD method support
echo -e "${YELLOW}Test 6: HEAD Method Support${NC}"
response=$(curl -s -o /dev/null -w "%{http_code}" -I "$BASE_URL/.well-known/agent.json")
if [ "$response" -eq 200 ]; then
    echo -e "${GREEN}✓ HEAD method supported on agent.json${NC}"
else
    echo -e "${RED}✗ HEAD method failed on agent.json (HTTP $response)${NC}"
    exit 1
fi
echo ""

# Test 7: List Protocols
echo -e "${YELLOW}Test 7: List Protocols${NC}"
response=$(curl -s "$BASE_URL/protocols")
protocol_count=$(echo "$response" | jq -r '.total')
if [ "$protocol_count" -gt 0 ]; then
    echo -e "${GREEN}✓ Found $protocol_count protocols${NC}"
    echo "$response" | jq -r '.protocols[]' | head -5
else
    echo -e "${RED}✗ No protocols found${NC}"
    exit 1
fi
echo ""

# Test 8: Pool Monitoring (if FREE_MODE)
echo -e "${YELLOW}Test 8: Pool Monitoring${NC}"
echo "Testing with Uniswap V3 USDC/WETH pool on Ethereum..."

payload='{
  "protocol_ids": ["uniswap-v3"],
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
}'

response=$(curl -s -X POST "$BASE_URL/pools/watch" \
  -H "Content-Type: application/json" \
  -d "$payload")

http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/pools/watch" \
  -H "Content-Type: application/json" \
  -d "$payload")

if [ "$http_code" -eq 200 ]; then
    echo -e "${GREEN}✓ Pool monitoring returned HTTP 200${NC}"
    echo "Response:"
    echo "$response" | jq '.'
elif [ "$http_code" -eq 402 ]; then
    echo -e "${YELLOW}⚠ Pool monitoring returned HTTP 402 (payment required)${NC}"
    echo "This is expected when FREE_MODE=false"
else
    echo -e "${RED}✗ Pool monitoring failed (HTTP $http_code)${NC}"
    echo "Response: $response"
fi
echo ""

# Summary
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}All critical tests passed!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo "Service is ready for deployment."
echo ""
echo "Next steps:"
echo "1. Deploy to Railway"
echo "2. Set BASE_URL environment variable"
echo "3. Register on x402scan: https://www.x402scan.com/resources/register"
echo "4. Test with x402 payment flow"
