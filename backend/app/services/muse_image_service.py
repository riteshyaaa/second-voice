"""Muse Image seam — optional visual-asset generation (Phase 9).

STATUS (2026-11-01): request/response shapes for Meta image generation
could NOT be verified against official Meta API documentation. Public
sources describe mutually inconsistent surfaces (Responses-API image
tools via a cookbook fragment, aggregator /images endpoints, third-party
wrappers) — none citable as the contract for OUR key + base URL.

So this module deliberately does NOT call any image endpoint. generate()
raises ImageUnavailable with the verification status; the /illustrate
route surfaces it as 409. Cards are fully functional without generated
imagery (emoji anchors + multilingual labels). When a shape is verified
live, implement it here behind this same function — card code won't change.

Hard rule carried over: generated imagery is a communication aid ONLY,
never evidence of what anyone said.
"""

STATUS = ("unverified: no citable official request/response shape for "
          "Meta image generation as of 2026-11-01; refusing to invent one")


class ImageUnavailable(Exception):
    pass


def generate_sync(card) -> str:
    """Illustrate a user-approved card concept. Always raises until a
    verified provider is wired (see STATUS)."""
    raise ImageUnavailable(
        f"AI illustration unavailable ({STATUS}). "
        f"Card '{getattr(card, 'label', '?')}' works fully with its emoji + labels.")
