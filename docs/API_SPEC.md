# API Specification

Status: M1. The three session endpoints are implemented (text input only). Other endpoints are from PRD §11 and not built yet.

## Rules for every endpoint

- Authentication and authorization required.
- Input validation (Pydantic models; unknown fields rejected).
- Rate limiting.
- HTTPS only.
- Errors never include transcript or response text.
- The conversation endpoint never exposes direct access to the LLM. Clients send a message; they cannot set system prompts, models, tools, or generation parameters.

## Endpoints

| Method | Path | Purpose | Auth | Milestone |
|---|---|---|---|---|
| POST | `/api/v1/devices/register` | Register device | Operator (D-010) | M5 |
| POST | `/api/v1/devices/authenticate` | Authenticate device | Device credential | M5 |
| GET | `/api/v1/devices/status` | Retrieve device status | Device | M5 |
| POST | `/api/v1/sessions` | Create session | Device | M1 |
| POST | `/api/v1/sessions/{id}/message` | Process conversation | Device | M1 (text), M3 (audio) |
| DELETE | `/api/v1/sessions/{id}` | End session | Device | M1 |
| GET | `/api/v1/parent/settings` | Retrieve parent settings | Parent | Later |
| PATCH | `/api/v1/parent/settings` | Update parent settings | Parent | Later |
| DELETE | `/api/v1/parent/data` | Request eligible data deletion | Parent | M5 |

In M1, device auth is a development stub: every request must send `Authorization: Bearer <DEV_DEVICE_TOKEN>`. If `DEV_DEVICE_TOKEN` is unset, every request is rejected with 401. Real per-device credentials arrive in M5 (D-010). Rate limiting is not implemented yet (D-013).

## Errors

| Status | When | Body |
|---|---|---|
| 401 | Missing or wrong token | `{"detail": "Unauthorized"}` |
| 404 | Session unknown, expired, deleted, or belongs to another device | `{"detail": "Not Found"}` |
| 422 | Invalid body: unknown fields, empty or over 500 characters | `{"detail": "invalid request"}`, never echoing the input |

## `POST /api/v1/sessions`

Returns `201` with `{"session_id": "..."}`.

## `DELETE /api/v1/sessions/{id}`

Returns `204` and drops the session's in-memory context.

## `POST /api/v1/sessions/{id}/message`

Request (M1, text input, 1–500 characters, no other fields allowed):

```json
{ "text": "why is the sky blue?" }
```

Response:

```json
{
  "text": "Sunlight bounces off tiny bits of air, and blue light bounces the most! What's your favorite color?",
  "source": "generated"
}
```

`source` is one of `generated` (passed validation), `template` (restricted-category template), or `fallback` (fail-closed). The response never says which classifier or validator fired.

From M3 the endpoint accepts audio and returns synthesized audio for the approved text.
