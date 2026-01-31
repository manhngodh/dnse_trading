# DNSE Trading API Integration Summary

This document summarizes the issues encountered and resolutions found while integrating with the DNSE (Vietnam) Lightspeed API for stock and covered warrant trading.

## 1. API Versioning Mismatch
- **Problem:** The original client used `v2` endpoints for `order-service` (e.g., `/order-service/v2/orders`).
- **Error:** `HTTP 403 Forbidden: {"status":403,"code":"FORBIDDEN","message":"must use order v1"}`.
- **Resolution:** Updated `rest/endpoints.py` and `common/constants.py` to use `v1` endpoints.
- **Key Lesson:** Always verify the specific API version supported by the sub-account type (e.g., SpaceX vs. RocketX).

## 2. Sub-Account Identification
- **Problem:** Using `custodyCode` (e.g., `064C...`) or `flexCustomerId` as the `accountNo` failed with validation errors.
- **Error:** `{"status":400,"code":"CO-ORD-006","message":"Validate Order Failed","description":"User is not own accountNo to place order"}`.
- **Resolution:** Use the specific sub-account ID (e.g., `0001010274` or `0001031199`) retrieved from the `/order-service/accounts` endpoint.

## 3. Loan Package Validation
- **Problem:** Standard orders and conditional orders require a specific `loanPackageId`. Using `0` or omitting it failed.
- **Error:** `{"status":400,"code":"CO-ORD-006","message":"Validate Order Failed","description":"account don't have loan package"}`.
- **Resolution:** Identified `loanPackageId: 1775` (labeled "GD Tiền mặt" - Cash Trading) as the mandatory package for basic trades on these account types.

## 4. Standard Order Service Stability
- **Problem:** Standard Limit Orders (LO) through the base `order-service` consistently returned backend errors.
- **Error:** `HTTP 500: {"status":500,"code":"REMOTE_SERVER_ERROR","message":"Error in backend service"}`.
- **Workaround:** Used the **Conditional Order API** (`https://api.dnse.com.vn/conditional-order-api/v1/orders`) instead. By setting a trigger condition (e.g., `price <= target`), the backend successfully processed the orders that standard endpoints rejected.

## 5. Successful Order Payload (Conditional)
The following payload structure was verified to work for both Stocks (VND) and Covered Warrants (CHPG2602):

```json
{
  "condition": "price <= 20400",
  "targetOrder": {
    "quantity": 100,
    "side": "NB",
    "price": 20400,
    "loanPackageId": 1775,
    "orderType": "LO"
  },
  "symbol": "VND",
  "props": {
    "stopPrice": 20400,
    "marketId": "UNDERLYING"
  },
  "accountNo": "0001010274",
  "category": "STOP",
  "timeInForce": {
    "expireTime": "2026-01-21T07:30:00.000Z",
    "kind": "GTD"
  }
}
```

## 6. Data Fetching & Visualization
- **Market Data:** WebSocket (MQTT) provides real-time `DNSEMarketDataTick` objects.
- **History/Charts:** Historical 5m OHLC data is best retrieved via the `vnstock` library (Source: `VCI`) for charting.
- **Terminal Charts:** `plotext` can be used for terminal visualization, but requires mocking `sys.stdout.isatty = lambda: True` in certain non-interactive environments to force color output.

---
*Last Updated: 2026-01-20*
