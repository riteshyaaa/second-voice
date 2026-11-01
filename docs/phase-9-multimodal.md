# Phase 9 — Multimodal Communication (done 2026-11-01)

## What was built and why

Speech and typing existed; the quick board existed only as a frontend
page with no backend. Phase 9 adds server-side communication cards so
every path — speech, typing, board tap, visual card — funnels through
the same confirmation and audit workflow.

## Cards (`api/cards.py`, model `CommCard`, migration `0008`)

- Fields: label, optional native-language label, language, emoji anchor,
  category (needs/requests/feelings/questions/emergency/personal),
  phrase, favorite, optional image_url.
- 12 seeded defaults (emoji + verified native labels only where wording
  is already proven in this repo; everything else honestly
  English-only), lazily seeded per user, never duplicated.
- CRUD + favorite filter + category filter, all ownership-checked.
- `POST /cards/{id}/speak`: the tap IS the confirmation — mints
  ApprovedMessage (source `card`) + ConfirmationEvent, then delegates
  to the standard synthesis endpoint, so the server-side gate still
  sees a confirmed row. Required migration `0009` (card taps have no
  session; `ApprovedMessage.session_id` now nullable — readers tolerate it).
- Cards are covered by account export and full wipe (a wipe test proves
  favorited rows actually disappear).

## Muse Image: verified status, not integrated

Image-endpoint shapes could not be verified against official Meta API
docs (only aggregator endpoints, third-party wrappers, and cookbook
fragments — mutually inconsistent). Per project rules no call was
invented: `muse_image_service` documents the status and raises
`ImageUnavailable`; `/illustrate` returns 409 `IMAGE_UNAVAILABLE`.
Cards are fully useful without generated imagery. When a shape is
verified live, it slots behind `generate_sync()` with no card changes.
Hard rule kept: generated imagery is an aid only, never evidence.

## Verification (observed)

- 5 new tests in `test_cards.py` (seeds once, CRUD/favorites/isolation,
  tap-to-speak audio, honest 409, export+wipe proof). Suite 85/85.
- Live Docker on `0009`: 12 seeds, emergency card spoke through the
  confirmed path, illustrate 409'd with reason. PHASE9-DOCKER-PASS.

## Limits

No AI-generated visuals until verified; no per-segment card audio;
switch-access and the accessible workspace rendering are Phase 13
frontend work; frontend board page still needs rewiring to this API.
