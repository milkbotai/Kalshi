"""Load testing for Milkbot dashboard using Locust.

Simulates multiple concurrent users accessing the dashboard
to test performance under load.

Usage:
    locust -f tests/performance/locustfile.py --host=http://localhost:8501
"""

from locust import HttpUser, between, task


class DashboardUser(HttpUser):
    """Simulated dashboard user."""

    wait_time = between(2, 5)  # Wait 2-5 seconds between requests

    @task(3)
    def view_homepage(self) -> None:
        """View main dashboard page."""
        self.client.get("/")

    @task(2)
    def view_city_markets(self) -> None:
        """View city markets tab."""
        self.client.get("/?tab=city_markets")

    @task(2)
    def view_performance(self) -> None:
        """View performance tab."""
        self.client.get("/?tab=performance")

    @task(1)
    def view_trades(self) -> None:
        """View trade feed tab."""
        self.client.get("/?tab=trades")

    @task(1)
    def view_health(self) -> None:
        """View system health tab."""
        self.client.get("/?tab=health")

    @task(1)
    def check_health_endpoint(self) -> None:
        """Check health endpoint."""
        self.client.get("/health")


class APIUser(HttpUser):
    """Simulated API user (if analytics API is exposed)."""

    wait_time = between(1, 3)

    @task(3)
    def get_city_metrics(self) -> None:
        """Get city metrics."""
        self.client.get("/api/metrics/city")

    @task(2)
    def get_equity_curve(self) -> None:
        """Get equity curve."""
        self.client.get("/api/equity")

    @task(2)
    def get_public_trades(self) -> None:
        """Get public trades."""
        self.client.get("/api/trades/public")

    @task(1)
    def get_health_status(self) -> None:
        """Get health status."""
        self.client.get("/api/health")
