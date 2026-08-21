# Route claims evidence for review

A minimal, runnable Flask service that starts a
[Box Automate](https://developer.box.com/guides/box-automate/index)
manual-start workflow on selected claims evidence files.

Your claims system calls `POST /reviews` with a claim ID and file IDs. The
service writes the claim ID onto each file as Box metadata, then starts the
published Automate workflow. Box owns the approve or reject tasks; this app
does not poll for task state.

This is the companion repository to the tutorial
**[Route claims evidence for review with Box Automate](https://developer.box.com/tutorials/claims-evidence-review)**.

## What it does

| Capability | How |
| --- | --- |
| Authenticate as a managed user | Client Credentials Grant (`user_id`) |
| Tag selected evidence with a claim ID | `POST /2.0/files/:id/metadata/enterprise/:template` |
| Find the published workflow on the claims folder | `GET /2.0/automate_workflows?folder_id=...` (`box-version: 2026.0`) |
| Start approve and reject tasks on those files | `POST /2.0/automate_workflows/:id/start` |

## Project layout

```
Route-claims-evidence-for-review/
├── app.py                  # Flask POST /reviews
├── box_client.py           # CCG auth as a managed user (user_id)
├── automate.py             # Beta Automate list + start wrappers
├── claims_metadata.py      # Create or replace claim metadata
├── sample_review.json      # Example payload for local curl tests
├── requirements.txt
├── .env.example
└── .gitignore
```

## Prerequisites

- **Python 3.11+**
- A [Box Enterprise Advanced account](https://www.box.com/pricing) with
  **Box Automate** enabled. See
  [Enabling Box Automate](https://docs.box.com/en/box-automate/enabling-box-automate).
  These endpoints are **Beta**, are not available on the
  [Free Developer Plan](https://developer.box.com/platform/free-developer-plan),
  and require the `box-version: 2026.0` header.
- A **Client Credentials Grant (CCG)** Platform App with:
  - **Read and write all files and folders stored in Box**
  - **App + Enterprise Access**
  - **Generate user access tokens** enabled
  - The app **authorized** (and **re-authorized** after those changes) in the
    Admin Console
- The **user ID** of a managed user who can build and start Automate workflows
  (for testing, use your own). Automate list and start return workflows that
  user can start. They do not return results for the enterprise service account.
- **Admin access** to create a `Claim` metadata template (or an administrator
  who can create one for you)
- Permission to build and **publish** a Manual Start workflow in the Box
  Automate builder

Complete the one-time Box setup in the
[tutorial](https://developer.box.com/tutorials/claims-evidence-review#configure-box-once)
before you run this sample: metadata template, claims folder with sample
files, and a published **Claims evidence review** workflow scoped to that
folder.

## Setup

1. **Clone and enter the project**

   ```bash
   git clone https://github.com/box-community/Route-claims-evidence-for-review.git
   cd Route-claims-evidence-for-review
   ```

2. **Create a virtual environment and install dependencies**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

3. **Configure credentials**

   ```bash
   cp .env.example .env
   ```

   Fill in `BOX_CLIENT_ID`, `BOX_CLIENT_SECRET`, `BOX_USER_ID`,
   `BOX_CLAIMS_FOLDER_ID`, and `BOX_CLAIMS_TEMPLATE_KEY`. Leave
   `BOX_CLAIMS_WORKFLOW_NAME=Claims evidence review` unless you named the
   workflow something else.

   > **Never commit `.env`.** It is already in `.gitignore`.

## Run

```bash
python app.py
```

The server starts on `http://127.0.0.1:5000`.

> Do not use this endpoint unauthenticated in production. Verify a signed
> request from your claims system, or place the service behind your gateway.

## Try it

You need **two terminals**: one running the Flask server, one sending a
review request.

1. **Start the server** (terminal 1):

   ```bash
   source .venv/bin/activate
   python app.py
   ```

2. **Start a review** (terminal 2). Use evidence **file** IDs from the
   Claims Review folder, not the folder ID. Copy `sample_review.json` and
   replace the placeholders:

   ```bash
   curl -X POST http://127.0.0.1:5000/reviews \
     -H "Content-Type: application/json" \
     -d @sample_review.json
   ```

   Or inline JSON:

   ```bash
   curl -X POST http://127.0.0.1:5000/reviews \
     -H "Content-Type: application/json" \
     -d '{
       "claim_id": "CLM-1042",
       "file_ids": ["123456789", "987654321"]
     }'
   ```

   A successful response looks like:

   ```json
   {
     "status": "review_started",
     "claim_id": "CLM-1042",
     "workflow": "Claims evidence review",
     "file_ids": ["123456789", "987654321"]
   }
   ```

3. **Confirm in Box**

   - Open an evidence file → **Metadata** tab shows claim `CLM-1042` and
     status `in_review`.
   - As the task assignee, open the approval task and confirm the claim ID
     appears in the message (if you included that field in the workflow).
   - Approve or reject from the file's **Activity** sidebar panel, and
     confirm the matching branch runs.

## How it works

1. `POST /reviews` validates `claim_id` and `file_ids` (at least one file,
   at most 20).
2. `claims_metadata.py` creates enterprise metadata on each file
   (`claimId`, `reviewStatus: in_review`). A `409 Conflict` falls back to
   JSON-Patch replace so resubmitted evidence does not fail.
3. `automate.py` lists published Automate actions on `BOX_CLAIMS_FOLDER_ID`
   and resolves the workflow by `BOX_CLAIMS_WORKFLOW_NAME`.
4. It starts the run with `workflow_action_id` (the action ID from
   `entries[].id`) and `file_ids`. The path uses `entries[].workflow.id`,
   not the action ID.

During Beta, the start endpoint does not accept fields at runtime, so the
claim ID is written as metadata first. The Automate endpoints are not yet
in `box-sdk-gen`; `automate.py` uses `client.make_request` with
`box-version: 2026.0`.

## Security notes

- Authenticate as a dedicated managed user with the least Automate and
  folder access your flow needs, not as the enterprise service account.
- Keep client secrets and tokens server-side. Never expose them to a browser.
- Authenticate `POST /reviews` in production.
- A double-submitted request starts the workflow twice. Prefer an
  idempotency check in your claims system.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `invalid_client` | Check `BOX_CLIENT_ID` / `BOX_CLIENT_SECRET` in `.env`. Confirm the app is Client Credentials Grant and authorized. |
| `invalid_grant` | Enable **App + Enterprise Access** and **Generate user access tokens**, then re-authorize. Verify `BOX_USER_ID` is digits only. |
| Empty `entries` from Automate list | Authenticate as a **managed user**, not the service account. Confirm the workflow is **published**, uses **Manual Start**, and is scoped to `BOX_CLAIMS_FOLDER_ID`. |
| `400 Action not found` | The app is still using the service account, or the files are outside the Manual Start folder. Switch to `BOX_USER_ID`. |
| `404` on an Automate endpoint | Automate is not enabled, the account is on the Free Developer Plan, `box-version: 2026.0` is missing, or the **action** ID was used in the URL path. |
| Approval task shows no claim ID | Field keys in `claims_metadata.py` must match `fields[].key` from the template schema (`claimId`, `reviewStatus`). |
| `403 Forbidden` | Enable **Read and write all files and folders stored in Box** and re-authorize. |
| `ModuleNotFoundError` | Activate the venv: `source .venv/bin/activate`. |

## License

[MIT](./LICENSE)
