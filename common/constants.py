"""
DNSE API constants and endpoint definitions.
"""

# ============================================================================
# API Base URLs
# ============================================================================

DNSE_API_BASE_URL = "https://api.dnse.com.vn"
DNSE_MARKET_DATA_WSS_HOST = "datafeed-lts-krx.dnse.com.vn"
DNSE_MARKET_DATA_WSS_PORT = 443
DNSE_MARKET_DATA_WSS_PATH = "/wss"

# Alternative service URL (from documentation)
DNSE_SERVICES_URL = "https://services.entrade.com.vn"


# ============================================================================
# Authentication Endpoints
# ============================================================================

# Layer 1: Login with username/password -> JWT token
AUTH_LOGIN_ENDPOINT = "/auth-service/login"

# Layer 2: OTP verification -> Trading token
AUTH_TRADING_TOKEN_ENDPOINT = "/order-service/trading-token"

# Market data authentication
AUTH_MARKET_DATA_ENDPOINT = "/user-service/api/auth"


# ============================================================================
# Account Endpoints
# ============================================================================

# Get account info 
ACCOUNT_INFO_ENDPOINT = "/user-service/api/me"

# Get sub-accounts
SUB_ACCOUNTS_ENDPOINT = "/user-service/api/accounts"


# ============================================================================
# Base Trading Endpoints (Stocks)
# ============================================================================

# Place order
BASE_ORDER_ENDPOINT = "/order-service/v1/orders"

# Query orders (uses same endpoint with query params)
# GET /order-service/v1/orders?accountNo={accountNo}

# Order detail
# GET /order-service/v1/orders/{orderId}

# Cancel order
# DELETE /order-service/v1/orders/{orderId}?accountNo={accountNo}

# Loan packages
BASE_LOAN_PACKAGES_ENDPOINT = "/order-service/loan-packages"

# Buying power / selling power  
BASE_BUYING_POWER_ENDPOINT = "/order-service/pp"

# Holdings
BASE_HOLDINGS_ENDPOINT = "/order-service/holdings"


# ============================================================================
# Derivative Trading Endpoints
# ============================================================================

# Place derivative order
DERIVATIVE_ORDER_ENDPOINT = "/order-service/derivative/orders"

# Derivative loan packages
DERIVATIVE_LOAN_PACKAGES_ENDPOINT = "/order-service/derivative/loan-packages"

# Derivative buying power
DERIVATIVE_BUYING_POWER_ENDPOINT = "/order-service/derivative/pp"

# Derivative positions
DERIVATIVE_POSITIONS_ENDPOINT = "/order-service/derivative/positions"

# Derivative assets
DERIVATIVE_ASSETS_ENDPOINT = "/order-service/derivative/assets"


# ============================================================================
# Market Data Topics (MQTT)
# ============================================================================

# Stock Info (Last price, volume, high, low, etc.)
MQTT_TOPIC_STOCK_INFO = "plaintext/quotes/krx/mdds/stockinfo/v1/roundlot/symbol/{symbol}"

# Top Price (Best Bid/Ask)
MQTT_TOPIC_TOP_PRICE = "plaintext/quotes/krx/mdds/topprice/v1/roundlot/symbol/{symbol}"

# Trade Tick (Matched Execution)
MQTT_TOPIC_TICK = "plaintext/quotes/krx/mdds/tick/v1/roundlot/symbol/{symbol}"


# ============================================================================
# Token Expiry
# ============================================================================

# JWT and Trading tokens expire after 8 hours
TOKEN_EXPIRY_HOURS = 8
TOKEN_EXPIRY_SECONDS = TOKEN_EXPIRY_HOURS * 60 * 60

# Refresh tokens 30 minutes before expiry
TOKEN_REFRESH_BUFFER_SECONDS = 30 * 60


# ============================================================================
# Vietnamese Market Hours (GMT+7)
# ============================================================================

MARKET_TIMEZONE = "Asia/Ho_Chi_Minh"

# Morning session
MARKET_MORNING_OPEN = "09:00"
MARKET_MORNING_CLOSE = "11:30"

# Afternoon session  
MARKET_AFTERNOON_OPEN = "13:00"
MARKET_AFTERNOON_CLOSE = "14:45"

# ATC session
MARKET_ATC_START = "14:45"
MARKET_ATC_END = "15:00"


# ============================================================================
# Request/Response Constants
# ============================================================================

# HTTP Headers
HEADER_AUTHORIZATION = "Authorization"
HEADER_TRADING_TOKEN = "Trading-Token"
HEADER_SMART_OTP = "smart-otp"
HEADER_CONTENT_TYPE = "Content-Type"

# Content types
CONTENT_TYPE_JSON = "application/json"

# HTTP timeout (seconds)
HTTP_TIMEOUT = 30

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1
