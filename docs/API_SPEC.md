# API Specification

Status: initial draft (M0). Endpoints are from PRD §11. Request and response shapes will be filled in as each endpoint is implemented.

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

In M1, device auth is a development stub; real credentials arrive in M5.

## `POST /api/v1/sessions/{id}/message` (draft)

Request (M1, text input):

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
