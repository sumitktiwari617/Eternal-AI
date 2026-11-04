from typing import Dict, Any, Optional
import logging
from config import Settings, settings as default_settings

logger = logging.getLogger(__name__)

# Check if NeoAPI is available in environment
try:
    from neo_api_client import NeoAPI
    HAS_NEO_SDK = True
except ImportError:
    HAS_NEO_SDK = False
    NeoAPI = None


class KotakNeoAdapter:
    """
    Adapter wrapper for Kotak Neo API SDK.
    Handles authentication, quote requests, and order safety.
    """

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or default_settings
        self.client = None
        self.is_authenticated = False
        self.last_login_time = None
        self._init_client()

    def _init_client(self):
        if not HAS_NEO_SDK:
            return

        consumer_key = self.config.kotak_consumer_key
        if consumer_key:
            try:
                self.client = NeoAPI(
                    consumer_key=consumer_key,
                    environment=self.config.kotak_environment
                )
            except Exception as e:
                # Fallback without http2 if h2 is unavailable
                try:
                    self.client = NeoAPI(
                        consumer_key=consumer_key,
                        environment=self.config.kotak_environment,
                        http2=False
                    )
                except Exception as inner_e:
                    logger.error(f"Failed to initialize NeoAPI client: {inner_e}")
                    self.client = None

    def status(self) -> Dict[str, Any]:
        return {
            "sdk_installed": HAS_NEO_SDK,
            "client_initialized": self.client is not None,
            "is_authenticated": self.is_authenticated,
            "has_credentials": bool(
                self.config.kotak_consumer_key and
                self.config.kotak_mobile_number and
                self.config.kotak_client_code
            ),
            "environment": self.config.kotak_environment,
            "token": self.config.kotak_token,
            "segment": self.config.kotak_segment,
        }

    def login_with_totp(self, totp_code: str, mpin: Optional[str] = None) -> Dict[str, Any]:
        """Performs TOTP and optional MPIN authentication using Kotak Neo client."""
        if not HAS_NEO_SDK:
            return {
                "success": False,
                "error": "Kotak Neo SDK ('neo_api_client') is not installed in the Python environment."
            }

        if not self.client:
            return {
                "success": False,
                "error": "Client not initialized. Missing KOTAK_CONSUMER_KEY in .env."
            }

        if not (self.config.kotak_mobile_number and self.config.kotak_client_code):
            return {
                "success": False,
                "error": "Missing KOTAK_MOBILE_NUMBER or KOTAK_CLIENT_CODE in .env."
            }

        # Normalize mobile number with country code (+91)
        mobile = str(self.config.kotak_mobile_number).strip()
        if not mobile.startswith("+"):
            if len(mobile) == 10:
                mobile = f"+91{mobile}"

        ucc_code = str(self.config.kotak_client_code).strip()
        totp_clean = str(totp_code).strip()

        try:
            res = self.client.totp_login(
                mobile_number=mobile,
                ucc=ucc_code,
                totp=totp_clean
            )
            # Check if SDK returned an error structure
            if isinstance(res, dict) and "error" in res:
                self.is_authenticated = False
                err_msg = res.get("error")
                if isinstance(err_msg, list) and len(err_msg) > 0:
                    err_msg = err_msg[0].get("message", str(err_msg))
                return {
                    "success": False,
                    "error": f"Kotak Neo TOTP Login Error: {err_msg}",
                    "details": res
                }

            # Step 2: Validate MPIN to upgrade to Trade Token (Full Order Access)
            mpin_to_use = mpin or getattr(self.config, "kotak_mpin", None)
            if mpin_to_use and hasattr(self.client, "totp_validate"):
                try:
                    res_val = self.client.totp_validate(mpin=str(mpin_to_use).strip())
                    if isinstance(res_val, dict) and "error" in res_val:
                        err_val = res_val.get("error")
                        if isinstance(err_val, list) and len(err_val) > 0:
                            err_val = err_val[0].get("message", str(err_val))
                        return {
                            "success": False,
                            "error": f"Kotak Neo MPIN Validation Error: {err_val}",
                            "details": res_val
                        }
                except Exception as mpin_err:
                    logger.warning(f"Kotak Neo totp_validate warning: {mpin_err}")

            self.is_authenticated = True
            return {
                "success": True,
                "message": "Kotak Neo authentication successful (Live quotes active. Real trade execution is strictly disabled; Guider suggestions only).",
                "response": res
            }
        except Exception as e:
            self.is_authenticated = False
            return {
                "success": False,
                "error": f"Login failed: {str(e)}"
            }

    def get_live_quote(
        self,
        token: Optional[str] = None,
        segment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetches live quote from Kotak Neo API."""
        if not self.is_authenticated or not self.client:
            return {
                "success": False,
                "error": "Kotak Neo client not authenticated."
            }

        tok = token or self.config.kotak_token
        seg = segment or self.config.kotak_segment

        try:
            res = self.client.quotes(
                instrument_tokens=[{"instrument_token": str(tok), "exchange_segment": str(seg)}],
                quote_type="all"
            )
            if isinstance(res, list) and len(res) > 0:
                quote = res[0]
            elif isinstance(res, dict):
                quote = res
            else:
                quote = None

            if quote:
                return {
                    "success": True,
                    "quote": quote,
                    "ltp": float(quote.get("ltp", 0.0)),
                    "timestamp": quote.get("lstup_time"),
                }
            return {"success": False, "error": "Empty quote response from Kotak Neo API."}
        except Exception as e:
            return {"success": False, "error": f"Quote request error: {str(e)}"}

    def get_trading_symbol(self, symbol: Optional[str] = None) -> str:
        """Formats an equity ticker to Kotak Neo standard (e.g. TATAMOTORS.NS -> TATAMOTORS-EQ)."""
        raw = symbol or getattr(self.config, "kotak_trading_symbol", None) or self.config.symbol
        if raw.endswith(".NS"):
            base = raw[:-3]
            return f"{base}-EQ"
        if raw.endswith(".BO"):
            base = raw[:-3]
            return f"{base}-EQ"
        if not raw.endswith("-EQ") and raw.isalpha():
            return f"{raw}-EQ"
        return raw

    def get_positions(self) -> Dict[str, Any]:
        """Fetches current real-money intraday & delivery positions for read-only monitoring."""
        if not self.is_authenticated or not self.client:
            return {"success": False, "error": "Kotak Neo client not authenticated.", "positions": []}
        try:
            res = self.client.positions()
            return {"success": True, "positions": res}
        except Exception as e:
            return {"success": False, "error": f"Fetch positions error: {str(e)}", "positions": []}

    def get_order_report(self) -> Dict[str, Any]:
        """Fetches the daily order report for read-only audit."""
        if not self.is_authenticated or not self.client:
            return {"success": False, "error": "Kotak Neo client not authenticated.", "orders": []}
        try:
            res = self.client.order_report()
            return {"success": True, "orders": res}
        except Exception as e:
            return {"success": False, "error": f"Fetch order report error: {str(e)}", "orders": []}


