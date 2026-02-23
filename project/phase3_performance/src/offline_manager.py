"""
RAG_HS_CODE - Offline Mode Manager
Phase 3: Performance & Caching

Manages connectivity detection and graceful degradation.
"""

import time
import socket
import threading
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum


class ConnectivityStatus(Enum):
    """Network connectivity status"""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"  # Some services reachable, some not


@dataclass
class ServiceHealth:
    """Health status of an external service"""
    name: str
    url: str
    status: ConnectivityStatus
    last_check: float
    response_time_ms: Optional[float] = None
    error: Optional[str] = None

    @property
    def is_available(self) -> bool:
        return self.status == ConnectivityStatus.ONLINE

    @property
    def age_display(self) -> str:
        if self.last_check == 0:
            return "Never"
        age = time.time() - self.last_check
        if age < 60:
            return f"{age:.0f}s ago"
        elif age < 3600:
            return f"{age / 60:.0f}m ago"
        return f"{age / 3600:.1f}h ago"


class OfflineManager:
    """
    Manages connectivity detection and offline mode.

    Features:
    - Check connectivity to specific services
    - DNS-based quick connectivity check
    - Track service health over time
    - Provide offline/online status for UI display
    - Graceful degradation recommendations
    """

    CHECK_INTERVAL = 60  # seconds between checks
    TIMEOUT = 5  # seconds for connectivity check

    # Services to monitor
    DEFAULT_SERVICES = {
        "nbp": {
            "name": "NBP Exchange Rates",
            "host": "www.nbp.com.pk",
            "port": 443
        },
        "sbp": {
            "name": "SBP Exchange Rates",
            "host": "www.sbp.org.pk",
            "port": 443
        },
        "weboc": {
            "name": "WEBOC Tariff Portal",
            "host": "www.weboc.gov.pk",
            "port": 443
        },
        "tipp": {
            "name": "FBR TIPP Portal",
            "host": "tipp.fbr.gov.pk",
            "port": 443
        },
        "openai": {
            "name": "OpenAI API",
            "host": "api.openai.com",
            "port": 443
        },
        "dns": {
            "name": "Internet (DNS)",
            "host": "8.8.8.8",
            "port": 53
        }
    }

    def __init__(self, services: Optional[Dict] = None,
                 check_interval: int = CHECK_INTERVAL,
                 timeout: int = TIMEOUT):
        self.services = services or self.DEFAULT_SERVICES
        self.check_interval = check_interval
        self.timeout = timeout
        self._health: Dict[str, ServiceHealth] = {}
        self._last_full_check = 0
        self._lock = threading.Lock()
        self._listeners: List[Callable] = []

        # Initialize health entries
        for key, svc in self.services.items():
            self._health[key] = ServiceHealth(
                name=svc["name"],
                url=f"{svc['host']}:{svc['port']}",
                status=ConnectivityStatus.ONLINE,  # Assume online initially
                last_check=0
            )

    def check_service(self, service_key: str) -> ServiceHealth:
        """
        Check connectivity to a specific service.

        Args:
            service_key: Key from services dict (e.g., 'nbp', 'weboc')

        Returns:
            ServiceHealth with updated status
        """
        if service_key not in self.services:
            return ServiceHealth(
                name=service_key,
                url="unknown",
                status=ConnectivityStatus.OFFLINE,
                last_check=time.time(),
                error="Unknown service"
            )

        svc = self.services[service_key]
        start = time.time()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((svc["host"], svc["port"]))
            sock.close()

            duration_ms = (time.time() - start) * 1000

            if result == 0:
                health = ServiceHealth(
                    name=svc["name"],
                    url=f"{svc['host']}:{svc['port']}",
                    status=ConnectivityStatus.ONLINE,
                    last_check=time.time(),
                    response_time_ms=round(duration_ms, 2)
                )
            else:
                health = ServiceHealth(
                    name=svc["name"],
                    url=f"{svc['host']}:{svc['port']}",
                    status=ConnectivityStatus.OFFLINE,
                    last_check=time.time(),
                    error=f"Connection refused (code: {result})"
                )
        except socket.timeout:
            health = ServiceHealth(
                name=svc["name"],
                url=f"{svc['host']}:{svc['port']}",
                status=ConnectivityStatus.OFFLINE,
                last_check=time.time(),
                error="Connection timed out"
            )
        except socket.gaierror:
            health = ServiceHealth(
                name=svc["name"],
                url=f"{svc['host']}:{svc['port']}",
                status=ConnectivityStatus.OFFLINE,
                last_check=time.time(),
                error="DNS resolution failed"
            )
        except Exception as e:
            health = ServiceHealth(
                name=svc["name"],
                url=f"{svc['host']}:{svc['port']}",
                status=ConnectivityStatus.OFFLINE,
                last_check=time.time(),
                error=str(e)
            )

        with self._lock:
            self._health[service_key] = health

        return health

    def check_all(self) -> Dict[str, ServiceHealth]:
        """
        Check connectivity to all services.

        Returns:
            Dictionary of service_key -> ServiceHealth
        """
        results = {}
        for key in self.services:
            results[key] = self.check_service(key)

        self._last_full_check = time.time()
        return results

    def check_internet(self) -> bool:
        """Quick check if internet is available (via DNS)."""
        health = self.check_service("dns")
        return health.is_available

    def get_status(self) -> ConnectivityStatus:
        """
        Get overall connectivity status.

        Returns:
            ONLINE: All services reachable
            DEGRADED: Some services reachable
            OFFLINE: No services reachable
        """
        with self._lock:
            health_list = list(self._health.values())

        # Filter out entries that haven't been checked
        checked = [h for h in health_list if h.last_check > 0]

        if not checked:
            return ConnectivityStatus.ONLINE  # Not checked yet

        available = [h for h in checked if h.is_available]

        if len(available) == len(checked):
            return ConnectivityStatus.ONLINE
        elif len(available) == 0:
            return ConnectivityStatus.OFFLINE
        else:
            return ConnectivityStatus.DEGRADED

    def get_health(self, service_key: Optional[str] = None) -> Any:
        """
        Get health status.

        Args:
            service_key: If specified, return health for this service.
                        If None, return all service health.

        Returns:
            ServiceHealth or Dict[str, ServiceHealth]
        """
        with self._lock:
            if service_key:
                return self._health.get(service_key)
            return dict(self._health)

    def needs_check(self) -> bool:
        """Check if it's time for a health check."""
        return (time.time() - self._last_full_check) > self.check_interval

    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get what the app can currently do based on connectivity.

        Returns:
            Dictionary of capability -> available
        """
        with self._lock:
            health = dict(self._health)

        nbp_ok = health.get("nbp", ServiceHealth("", "", ConnectivityStatus.OFFLINE, 0)).is_available
        weboc_ok = health.get("weboc", ServiceHealth("", "", ConnectivityStatus.OFFLINE, 0)).is_available
        openai_ok = health.get("openai", ServiceHealth("", "", ConnectivityStatus.OFFLINE, 0)).is_available

        return {
            "live_exchange_rates": nbp_ok,
            "weboc_duty_lookup": weboc_ok,
            "rag_classification": openai_ok,
            "cached_exchange_rates": True,  # Always available if cache has data
            "cached_duty_data": True,       # Always available if cache has data
            "manual_calculation": True,     # Always available
            "pdf_export": True,             # Always available (local)
            "excel_export": True            # Always available (local)
        }

    def get_ui_status(self) -> Dict[str, Any]:
        """
        Get status information formatted for Streamlit UI display.

        Returns:
            Dictionary with status, messages, and recommendations
        """
        status = self.get_status()
        capabilities = self.get_capabilities()

        with self._lock:
            health = dict(self._health)

        messages = []
        if status == ConnectivityStatus.OFFLINE:
            messages.append("No internet connection. Using cached data.")
            messages.append("Manual calculations still work.")
        elif status == ConnectivityStatus.DEGRADED:
            offline_services = [
                h.name for h in health.values()
                if not h.is_available and h.last_check > 0
            ]
            if offline_services:
                messages.append(f"Some services unavailable: {', '.join(offline_services)}")
            messages.append("Using cached data where available.")

        return {
            "status": status.value,
            "status_emoji": {
                "online": "🟢",
                "offline": "🔴",
                "degraded": "🟡"
            }.get(status.value, "⚪"),
            "messages": messages,
            "capabilities": capabilities,
            "services": {
                key: {
                    "name": h.name,
                    "available": h.is_available,
                    "last_check": h.age_display,
                    "response_ms": h.response_time_ms,
                    "error": h.error
                }
                for key, h in health.items()
            }
        }

    def add_listener(self, callback: Callable):
        """Add a status change listener."""
        self._listeners.append(callback)


# Global instance
_global_offline_manager: Optional[OfflineManager] = None


def get_offline_manager() -> OfflineManager:
    """Get or create the global offline manager."""
    global _global_offline_manager
    if _global_offline_manager is None:
        _global_offline_manager = OfflineManager()
    return _global_offline_manager
