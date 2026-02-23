"""
Phase 3: Performance - Offline Manager Tests

Tests for connectivity detection and offline mode management.
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from offline_manager import (
    OfflineManager, ConnectivityStatus, ServiceHealth, get_offline_manager
)


class TestConnectivityStatus:
    """Tests for ConnectivityStatus enum"""

    def test_online_value(self):
        assert ConnectivityStatus.ONLINE.value == "online"

    def test_offline_value(self):
        assert ConnectivityStatus.OFFLINE.value == "offline"

    def test_degraded_value(self):
        assert ConnectivityStatus.DEGRADED.value == "degraded"


class TestServiceHealth:
    """Tests for ServiceHealth dataclass"""

    def test_create(self):
        health = ServiceHealth(
            name="NBP",
            url="www.nbp.com.pk:443",
            status=ConnectivityStatus.ONLINE,
            last_check=time.time(),
            response_time_ms=150.0
        )
        assert health.name == "NBP"
        assert health.is_available

    def test_is_available_online(self):
        health = ServiceHealth("NBP", "url", ConnectivityStatus.ONLINE, time.time())
        assert health.is_available

    def test_is_available_offline(self):
        health = ServiceHealth("NBP", "url", ConnectivityStatus.OFFLINE, time.time())
        assert not health.is_available

    def test_age_display_never(self):
        health = ServiceHealth("NBP", "url", ConnectivityStatus.ONLINE, 0)
        assert health.age_display == "Never"

    def test_age_display_seconds(self):
        health = ServiceHealth("NBP", "url", ConnectivityStatus.ONLINE, time.time() - 30)
        assert "s ago" in health.age_display

    def test_age_display_minutes(self):
        health = ServiceHealth("NBP", "url", ConnectivityStatus.ONLINE, time.time() - 300)
        assert "m ago" in health.age_display

    def test_with_error(self):
        health = ServiceHealth(
            "NBP", "url", ConnectivityStatus.OFFLINE, time.time(),
            error="Connection timed out"
        )
        assert health.error == "Connection timed out"


class TestOfflineManager:
    """Tests for OfflineManager class"""

    def test_init_default_services(self):
        manager = OfflineManager()
        assert "nbp" in manager.services
        assert "weboc" in manager.services
        assert "openai" in manager.services
        assert "dns" in manager.services

    def test_init_custom_services(self):
        services = {
            "test": {"name": "Test", "host": "example.com", "port": 80}
        }
        manager = OfflineManager(services=services)
        assert "test" in manager.services
        assert "nbp" not in manager.services

    def test_initial_status_online(self):
        """Before checks, assume online"""
        manager = OfflineManager()
        # No checks have been performed, so all are assumed online with last_check=0
        status = manager.get_status()
        assert status == ConnectivityStatus.ONLINE

    def test_check_unknown_service(self):
        manager = OfflineManager()
        health = manager.check_service("nonexistent")
        assert health.status == ConnectivityStatus.OFFLINE
        assert health.error == "Unknown service"

    def test_get_health_all(self):
        manager = OfflineManager()
        health = manager.get_health()
        assert isinstance(health, dict)
        assert "nbp" in health

    def test_get_health_specific(self):
        manager = OfflineManager()
        health = manager.get_health("nbp")
        assert isinstance(health, ServiceHealth)
        assert health.name == "NBP Exchange Rates"

    def test_get_health_nonexistent(self):
        manager = OfflineManager()
        health = manager.get_health("nonexistent")
        assert health is None

    def test_needs_check_initially(self):
        manager = OfflineManager()
        assert manager.needs_check() is True

    def test_get_capabilities(self):
        manager = OfflineManager()
        caps = manager.get_capabilities()

        assert "live_exchange_rates" in caps
        assert "weboc_duty_lookup" in caps
        assert "rag_classification" in caps
        assert "manual_calculation" in caps
        assert caps["manual_calculation"] is True
        assert caps["pdf_export"] is True
        assert caps["excel_export"] is True

    def test_get_ui_status(self):
        manager = OfflineManager()
        ui = manager.get_ui_status()

        assert "status" in ui
        assert "status_emoji" in ui
        assert "messages" in ui
        assert "capabilities" in ui
        assert "services" in ui

    def test_ui_status_emoji_online(self):
        manager = OfflineManager()
        ui = manager.get_ui_status()
        # Initially online (not checked)
        assert ui["status_emoji"] in ["🟢", "🟡", "🔴"]

    def test_add_listener(self):
        manager = OfflineManager()
        callback = MagicMock()
        manager.add_listener(callback)
        assert callback in manager._listeners


class TestOfflineManagerWithMockedSocket:
    """Tests with mocked socket for deterministic behavior"""

    @patch('offline_manager.socket.socket')
    def test_check_service_online(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket_class.return_value = mock_sock

        manager = OfflineManager()
        health = manager.check_service("dns")

        assert health.status == ConnectivityStatus.ONLINE
        assert health.response_time_ms is not None

    @patch('offline_manager.socket.socket')
    def test_check_service_offline(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 111  # Connection refused
        mock_socket_class.return_value = mock_sock

        manager = OfflineManager()
        health = manager.check_service("dns")

        assert health.status == ConnectivityStatus.OFFLINE
        assert "Connection refused" in health.error

    @patch('offline_manager.socket.socket')
    def test_check_service_timeout(self, mock_socket_class):
        import socket
        mock_sock = MagicMock()
        mock_sock.connect_ex.side_effect = socket.timeout("timed out")
        mock_socket_class.return_value = mock_sock

        manager = OfflineManager()
        health = manager.check_service("dns")

        assert health.status == ConnectivityStatus.OFFLINE
        assert "timed out" in health.error

    @patch('offline_manager.socket.socket')
    def test_check_service_dns_failure(self, mock_socket_class):
        import socket
        mock_sock = MagicMock()
        mock_sock.connect_ex.side_effect = socket.gaierror("DNS failed")
        mock_socket_class.return_value = mock_sock

        manager = OfflineManager()
        health = manager.check_service("dns")

        assert health.status == ConnectivityStatus.OFFLINE
        assert "DNS resolution failed" in health.error

    @patch('offline_manager.socket.socket')
    def test_check_all_services(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket_class.return_value = mock_sock

        manager = OfflineManager()
        results = manager.check_all()

        assert len(results) == 6  # Default services (nbp, sbp, weboc, tipp, openai, dns)
        for key, health in results.items():
            assert health.status == ConnectivityStatus.ONLINE

    @patch('offline_manager.socket.socket')
    def test_overall_status_all_online(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket_class.return_value = mock_sock

        manager = OfflineManager()
        manager.check_all()

        assert manager.get_status() == ConnectivityStatus.ONLINE

    @patch('offline_manager.socket.socket')
    def test_overall_status_all_offline(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 111
        mock_socket_class.return_value = mock_sock

        manager = OfflineManager()
        manager.check_all()

        assert manager.get_status() == ConnectivityStatus.OFFLINE

    @patch('offline_manager.socket.socket')
    def test_overall_status_degraded(self, mock_socket_class):
        """Test degraded status when some services are down"""
        call_count = [0]

        def mock_connect(addr):
            call_count[0] += 1
            # First two services online, rest offline
            return 0 if call_count[0] <= 2 else 111

        mock_sock = MagicMock()
        mock_sock.connect_ex.side_effect = mock_connect
        mock_socket_class.return_value = mock_sock

        manager = OfflineManager()
        manager.check_all()

        assert manager.get_status() == ConnectivityStatus.DEGRADED

    @patch('offline_manager.socket.socket')
    def test_check_internet(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket_class.return_value = mock_sock

        manager = OfflineManager()
        assert manager.check_internet() is True

    @patch('offline_manager.socket.socket')
    def test_ui_status_offline_messages(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 111
        mock_socket_class.return_value = mock_sock

        manager = OfflineManager()
        manager.check_all()

        ui = manager.get_ui_status()
        assert ui["status"] == "offline"
        assert len(ui["messages"]) > 0

    @patch('offline_manager.socket.socket')
    def test_needs_check_after_check(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket_class.return_value = mock_sock

        manager = OfflineManager(check_interval=3600)
        manager.check_all()

        assert manager.needs_check() is False


class TestGetOfflineManager:
    """Tests for global manager"""

    def test_returns_instance(self):
        manager = get_offline_manager()
        assert isinstance(manager, OfflineManager)

    def test_singleton(self):
        m1 = get_offline_manager()
        m2 = get_offline_manager()
        assert m1 is m2
