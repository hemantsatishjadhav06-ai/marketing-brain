# Airtable Content Operations

The `Content Generation` Airtable base (`appvpMfpbNQDkUGeF`) is the operator
frontend. The FastAPI application in this repository is the backend and n8n
owns triggers and retry scheduling.

## Data model

| Table | ID | Responsibility |
|---|---|---|
| Content Master | `tblWu3YzDoasrj0OG` | Master queue and workflow state |
| Carousel Slides | `tblAbMcwp6DipTQqu` | Carousel slides and Motion Lite storyboard frames |
| Verified Claims | `tbluMV1yECqSjpY0S` | Source-locked claims; only `Verified` rows are usable |
| Projects & Locations | `tblXdFUMM6E6qSKLF` | Sourced project/location facts |
| Brand Rules | `tblP2Gqh59vI79IqW` | Active allowlisted brand rules |
| Generation Runs | `tblir6QJU0Vo4qBeP` | AI/backend audit trail |
| Approval History | `tbl7C6O77DDf6zd9D` | Direction, copy, design, and final decisions |

All new tables are isolated from the legacy product, SEO, and video tables.
Links are reciprocal Airtable record links; never copy IDs into text fields.

## Workflow

1. Add a Content Master row and link exactly one active Brand Rules row.
2. Add a topic, format, template, platform, and optional perspective.
3. Link verified claims/projects when the topic uses prices, RERA/registration,
   distances, investment language, or project/infrastructure facts.
4. Check `Trigger Generation`.
5. Airtable Automation calls n8n with the Airtable record ID.
6. n8n calls the backend with `stage=auto`.
7. The backend clears the trigger, writes a Generation Run, and executes the
   only valid stage:
   - `New`, `Researching`, or `NEEDS_RESEARCH` → A/B/C concepts.
   - `Direction Selected` → copy and storyboard package.
   - `QA Review` → deterministic evidence gate plus AI content audit.
8. A factual item without verified evidence returns `NEEDS_RESEARCH` without
   calling the model.
9. Humans approve direction, copy, design, and final scheduling in Airtable;
   n8n records each decision through the approval endpoint.

The backend is synchronous and idempotent. n8n may retry network failures, but
must reuse the same idempotency key for a single logical attempt.

## Backend API

Health:

```http
GET /api/airtable/health
X-Marketing-Brain-Secret: <AIRTABLE_WEBHOOK_SECRET>
```

Run a content stage:

```http
POST /api/airtable/content/recXXXXXXXXXXXXXX/run
X-Marketing-Brain-Secret: <AIRTABLE_WEBHOOK_SECRET>
Content-Type: application/json

{
  "stage": "auto",
  "dry_run": false,
  "idempotency_key": "airtable-record-id-and-automation-run-id"
}
```

Use `dry_run=true` to validate routing, brand linkage, and evidence without
writes or AI calls. The independent webhook secret remains required even when
`DIRECT_ACCESS=true`.

Record an approval:

```http
POST /api/airtable/content/recXXXXXXXXXXXXXX/approval
X-Marketing-Brain-Secret: <AIRTABLE_WEBHOOK_SECRET>
Content-Type: application/json

{
  "stage": "Direction",
  "decision": "Approved",
  "comment": "Proceed with concept B",
  "approved_by": "content-lead"
}
```

Supported stages are `Direction`, `Copy`, `Design`, and `Final`. Every call
creates an Approval History row and enforces the expected source status. A
final approval moves to `Scheduled` only when `Scheduled At` is populated.

## n8n connection

Recommended nodes:

1. **Webhook** receives `record_id` and a stable automation run ID.
2. **Set** creates `idempotency_key`.
3. **HTTP Request** calls the backend endpoint, adds
   `X-Marketing-Brain-Secret`, and sends the JSON body above.
4. **IF** branches on `status == NEEDS_RESEARCH`; this is a human research task,
   not a retryable failure.
5. Retry only HTTP 429/502/503 with exponential backoff. Do not retry HTTP
   401/409/422 until the input or configuration changes.

Store `AIRTABLE_TOKEN` and `AIRTABLE_WEBHOOK_SECRET` in Render/n8n credentials,
never in Airtable fields or workflow JSON committed to Git.

## Render checklist

- Set `AIRTABLE_TOKEN` to a PAT with record read/write access to the selected
  base.
- Set `AIRTABLE_WEBHOOK_SECRET` to a long random value and use the same value in
  n8n credentials.
- Deploy the repository root as the Python service described in `render.yaml`.
- Confirm the authenticated `/api/airtable/health` reports
  `configuration_ready: true`.
- Run one `dry_run` request before enabling the Airtable Automation.

GitHub stores and tests the backend; Render still executes it.

## Airtable quota

If Airtable returns HTTP 422 saying the base is over its record limit, schema
and Interface changes can still exist, but new content, brand, run, and slide
records cannot be created. Upgrade the workspace or deliberately archive/delete
legacy rows before enabling the automation. Do not delete legacy data as part
of an automated deployment.
