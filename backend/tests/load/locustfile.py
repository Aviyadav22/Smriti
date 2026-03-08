"""Locust load test for Smriti API.

Run with:
    locust -f tests/load/locustfile.py --host=http://localhost:8000

Targets:
    - Search p95 < 2s
    - Chat first token < 5s
    - 50 concurrent users with 0 errors
"""

from __future__ import annotations

import json
import random

from locust import HttpUser, between, task

SEARCH_QUERIES = [
    "right to privacy Supreme Court",
    "Section 498A IPC dowry cruelty",
    "Kesavananda Bharati basic structure",
    "anticipatory bail conditions",
    "Article 21 right to life",
    "environmental protection PIL",
    "freedom of speech Article 19",
    "arbitration clause enforcement",
    "land acquisition compensation",
    "defamation criminal proceedings",
    "motor accident compensation",
    "divorce mutual consent",
    "habeas corpus detention",
    "contempt of court",
    "writ of mandamus",
]

CHAT_QUERIES = [
    "What is the basic structure doctrine?",
    "Explain the right to privacy judgment",
    "What are the grounds for anticipatory bail?",
    "How does Article 21 protect right to life?",
    "What is the test for granting interim injunction?",
]


class SmritiUser(HttpUser):
    """Simulates a typical Smriti user: mostly searching, occasionally chatting."""

    wait_time = between(1, 5)
    access_token: str = ""
    chat_session_id: str = ""

    def on_start(self) -> None:
        """Register and login to get access token."""
        email = f"loadtest_{random.randint(10000, 99999)}@test.local"
        password = "LoadTest1234"

        # Register
        resp = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "name": "Load Tester",
                "consent_given": True,
            },
        )
        if resp.status_code == 201:
            data = resp.json()
            self.access_token = data["access_token"]
        elif resp.status_code == 409:
            # Already registered, login
            resp = self.client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            if resp.status_code == 200:
                self.access_token = resp.json()["access_token"]

    @property
    def _headers(self) -> dict[str, str]:
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    @task(5)
    def search(self) -> None:
        """Search — most common action (50% of traffic)."""
        query = random.choice(SEARCH_QUERIES)
        self.client.get(
            "/api/v1/search",
            params={"q": query, "page": 1, "page_size": 10},
            headers=self._headers,
            name="/api/v1/search",
        )

    @task(2)
    def search_with_filters(self) -> None:
        """Filtered search (20% of traffic)."""
        query = random.choice(SEARCH_QUERIES)
        self.client.get(
            "/api/v1/search",
            params={
                "q": query,
                "court": "Supreme Court of India",
                "year_from": 2020,
                "page": 1,
            },
            headers=self._headers,
            name="/api/v1/search [filtered]",
        )

    @task(1)
    def suggest(self) -> None:
        """Auto-complete suggestions (10% of traffic)."""
        prefix = random.choice(["right to", "Section 4", "Article 2", "bail"])
        self.client.get(
            "/api/v1/search/suggest",
            params={"q": prefix},
            headers=self._headers,
            name="/api/v1/search/suggest",
        )

    @task(1)
    def health_check(self) -> None:
        """Health check (10% of traffic)."""
        self.client.get("/health", name="/health")

    @task(1)
    def view_judges(self) -> None:
        """Judge list (10% of traffic)."""
        self.client.get(
            "/api/v1/judges",
            headers=self._headers,
            name="/api/v1/judges",
        )
