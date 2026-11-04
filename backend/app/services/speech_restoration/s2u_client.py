"""HTTP client for the S2U units sidecar (inference/ service).

The backend stays torch-free; all CLARIS weight/model code lives in the
sidecar. Every failure mode explains itself — never a silent fallback
to invented units.
"""
import httpx


class S2UUnavailable(RuntimeError):
    """The units stage cannot run; reason is in the message."""


async def fetch_units(wav: bytes, *, base_url: str, beam: int, timeout_s: float) -> dict:
    """POST normalized WAV to the sidecar; return validated units payload."""
    url = base_url.rstrip("/") + "/units"
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(url, params={"beam": beam}, content=wav,
                                     headers={"Content-Type": "audio/wav"})
    except httpx.ConnectError as exc:
        raise S2UUnavailable(f"inference sidecar unreachable at {base_url}: {exc}") from exc
    except httpx.TimeoutException as exc:
        raise S2UUnavailable(f"S2U inference timed out after {timeout_s}s") from exc
    if resp.status_code != 200:
        raise S2UUnavailable(f"inference sidecar HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        data = resp.json()
        units = data["units"]
        assert isinstance(units, list) and all(isinstance(u, int) for u in units)
    except (ValueError, KeyError, AssertionError, TypeError) as exc:
        raise S2UUnavailable(f"malformed units response from sidecar: {exc}") from exc
    return data
