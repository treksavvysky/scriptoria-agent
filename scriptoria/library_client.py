"""HTTP client for The Library — the Cortex OS daemon.

This is the ONLY module that talks to cortex-os. Endpoints mirror
ACEDaemonHandler in cortex-os src/core_ace.py:

    GET  /status /records /related /digest /catalog /checkout
    POST /ingest /curate /checkin /catalog/sync   (bearer-gated)
"""

from typing import Any, Dict, List, Optional

import httpx

from scriptoria import config


class LibraryError(Exception):
    """The Library refused or failed a request."""


class LibraryClient:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        self.base_url = (base_url or config.library_url()).rstrip("/")
        self.token = token if token is not None else config.cortex_api_token()
        self._client = httpx.Client(base_url=self.base_url, timeout=30.0)

    def _headers(self) -> Dict[str, str]:
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            response = self._client.get(path, params=params, headers=self._headers())
        except httpx.HTTPError as e:
            raise LibraryError(f"The Library is unreachable at {self.base_url}: {e}")
        return response

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = self._client.post(path, json=payload, headers=self._headers())
        except httpx.HTTPError as e:
            raise LibraryError(f"The Library is unreachable at {self.base_url}: {e}")
        body = self._json(response)
        if response.status_code >= 400:
            raise LibraryError(body.get("error") or f"HTTP {response.status_code} from {path}")
        return body

    @staticmethod
    def _json(response: httpx.Response) -> Dict[str, Any]:
        try:
            return response.json()
        except ValueError:
            raise LibraryError(
                f"Non-JSON response ({response.status_code}) from the Library: "
                f"{response.text[:200]}"
            )

    # -- reading room ---------------------------------------------------

    def status(self) -> Dict[str, Any]:
        return self._json(self._get("/status"))

    def search_records(
        self,
        text: Optional[str] = None,
        namespace: Optional[str] = None,
        record_type: Optional[str] = None,
        status: Optional[str] = None,
        linked_to: Optional[str] = None,
        domain: Optional[str] = None,
        packet: Optional[str] = None,
        conversion_pressure: Optional[str] = None,
        action_candidate: Optional[bool] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        response = self._get("/records", {
            "text": text,
            "namespace": namespace,
            "type": record_type,
            "status": status,
            "linked_to": linked_to,
            "domain": domain,
            "packet": packet,
            "conversion_pressure": conversion_pressure,
            "action_candidate": None if action_candidate is None else str(action_candidate).lower(),
            "limit": limit,
        })
        if response.status_code >= 400:
            raise LibraryError(self._json(response).get("error", f"HTTP {response.status_code}"))
        return self._json(response)

    def get_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        response = self._get("/records", {"record_id": record_id})
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise LibraryError(self._json(response).get("error", f"HTTP {response.status_code}"))
        return self._json(response)

    def related(self, record_id: str) -> Optional[Dict[str, Any]]:
        response = self._get("/related", {"record_id": record_id})
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise LibraryError(self._json(response).get("error", f"HTTP {response.status_code}"))
        return self._json(response)

    def digest(
        self,
        namespace: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        response = self._get("/digest", {"namespace": namespace, "status": status, "limit": limit})
        if response.status_code >= 400:
            raise LibraryError(self._json(response).get("error", f"HTTP {response.status_code}"))
        return response.text

    def catalog(
        self,
        source: Optional[str] = None,
        card_type: Optional[str] = None,
        status: Optional[str] = None,
        domain: Optional[str] = None,
        packet: Optional[str] = None,
        text: Optional[str] = None,
        held: Optional[bool] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        response = self._get("/catalog", {
            "source": source,
            "type": card_type,
            "status": status,
            "domain": domain,
            "packet": packet,
            "text": text,
            "held": None if held is None else str(held).lower(),
            "limit": limit,
        })
        if response.status_code >= 400:
            raise LibraryError(self._json(response).get("error", f"HTTP {response.status_code}"))
        return self._json(response)

    def checkout(self, record_id: str) -> Optional[Dict[str, Any]]:
        response = self._get("/checkout", {"record_id": record_id})
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise LibraryError(self._json(response).get("error", f"HTTP {response.status_code}"))
        return self._json(response)

    # -- the counter (mutations) ----------------------------------------

    def ingest(self, raw_capture: str, origin_context: str = "scriptoria") -> Dict[str, Any]:
        """Log a new capture into The Stack (async on the daemon side: 202)."""
        return self._post("/ingest", {
            "raw_capture": raw_capture,
            "origin_context": origin_context,
        })

    def curate(
        self,
        record_id: str,
        status: Optional[str] = None,
        record_type: Optional[str] = None,
        domain: Optional[str] = None,
        packet: Optional[str] = None,
        conversion_pressure: Optional[str] = None,
        action_candidate: Any = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"record_id": record_id}
        for key, value in (
            ("status", status),
            ("type", record_type),
            ("domain", domain),
            ("packet", packet),
            ("conversion_pressure", conversion_pressure),
        ):
            if value is not None:
                payload[key] = value
        if action_candidate is not None:
            payload["action_candidate"] = action_candidate
        return self._post("/curate", payload)

    def checkin(self, objects: List[Dict[str, Any]], source: str = "mnemos") -> Dict[str, Any]:
        return self._post("/checkin", {"source": source, "objects": objects})

    def catalog_sync(
        self,
        objects: Optional[List[Dict[str, Any]]] = None,
        source: str = "mnemos",
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"source": source}
        if objects is not None:
            payload["objects"] = objects
        if limit is not None:
            payload["limit"] = limit
        return self._post("/catalog/sync", payload)
