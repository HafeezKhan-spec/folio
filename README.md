# Folio

Folio is a local resume studio. You write a resume in a short form, pick one of four single-column templates, and download a PDF. Accounts, resumes, and versions stay in a SQLite database on the machine that runs the app.

The PDF engine is [RenderCV](https://github.com/rendercv/rendercv) 2.8, called as a Python library. It is not vendored. MIT notices are in `NOTICE` and `THIRD_PARTY_NOTICES`.

Pro is **$2.99/month**.

## Setup

Python 3.12 and Node 22 (or another current Node) are required.

```bash
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e "./backend[dev]"
cd frontend && npm install && cd ..
cp .env.example .env
chmod +x scripts/dev.sh
./scripts/dev.sh
```

`scripts/dev.sh` sources `.env`, starts the API on `http://127.0.0.1:8000`, and starts Vite on `http://127.0.0.1:5173`. The Vite dev server proxies `/api` to the API, so the session cookie stays on the page you have open.

- UI: http://127.0.0.1:5173
- Health: http://127.0.0.1:8000/api/health

You can also start the processes separately:

```bash
make api    # 127.0.0.1:8000
make web    # 127.0.0.1:5173
make test   # pytest
```

`.env` is gitignored. Do not commit it.

## Plans

| | Free | Pro ($2.99/month) |
| --- | --- | --- |
| Resumes | 1 | 25 |
| Versions per resume | 1 (saving updates it) | 30 |
| Templates | Classic | Classic, Engineering, SB2Nov, Harvard |
| PDF | Yes | Yes |
| Rewrite and tailor | No | Yes |

The account `hk386579@gmail.com` is always Pro, compared case-insensitively, on signup and on login. If that row already exists on Free, login upgrades it. Folio does not create a password for that account.

Tailor saves a new version. It does not overwrite the version you started from. Rewrite returns a new bullet and does not save by itself. Both refuse numbers that were not already in the source, and tailor also refuses a multi-word name that appears only in the job description.

## Environment

Copy `.env.example` to `.env`. Every variable:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Key for an OpenAI-compatible `POST /chat/completions`. Leave it empty to disable rewrite and tailor. The rest of the app still runs, and the AI routes return a clear error. |
| `OPENAI_BASE_URL` | API root. Default `https://api.openai.com/v1`. |
| `OPENAI_MODEL` | Model name. Default `gpt-4o-mini`. |
| `STRIPE_SECRET_KEY` | Stripe secret key. Use a test-mode key (`sk_test_...`) while trying checkout. |
| `STRIPE_PRICE_ID` | Stripe Price id for the **$2.99/month** recurring price. |
| `STRIPE_WEBHOOK_SECRET` | Signing secret (`whsec_...`) for `POST /api/billing/webhook`. |
| `FOLIO_DATABASE_PATH` | SQLite file. Default `data/folio.db`. |
| `FOLIO_COOKIE_SECURE` | `1` to mark the `folio_session` cookie Secure. Leave `0` on local HTTP. |
| `FOLIO_PUBLIC_URL` | Public origin used for Checkout success and cancel URLs. Default `http://127.0.0.1:5173`. |
| `FOLIO_STATIC_DIR` | Built frontend, served by the API when `index.html` is present. Default `frontend/dist`. The dev script uses Vite instead. |

The session cookie is named `folio_session`. It is `HttpOnly`, `SameSite=Lax`, and lasts 14 days. Passwords are stored as argon2id hashes.

If `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, or `STRIPE_WEBHOOK_SECRET` is empty, the billing page lists what is missing and the API returns that list in `missing`. Checkout returns 503 instead of raising. `price_label` is `$2.99/month` on the landing page, the billing page, `GET /api/billing`, and `GET /api/templates`.

## Stripe test mode

The displayed price is **$2.99/month**. Checkout charges whatever Price you put in `STRIPE_PRICE_ID`, so create that Price at $2.99/month in test mode.

1. In the [Stripe dashboard](https://dashboard.stripe.com), switch to **Test mode**.
2. Create a product named Folio Pro with a recurring price of **$2.99/month**.
3. Copy the price id (`price_...`) into `STRIPE_PRICE_ID`.
4. Open Developers → API keys and copy the test secret key into `STRIPE_SECRET_KEY`.
5. Install the [Stripe CLI](https://stripe.com/docs/stripe-cli) and forward webhooks:

   ```bash
   stripe listen --forward-to localhost:8000/api/billing/webhook
   ```

6. Put the CLI signing secret (`whsec_...`) into `STRIPE_WEBHOOK_SECRET`.
7. Restart `./scripts/dev.sh`.
8. Sign in, open Billing, and continue to checkout.
9. Pay with the test card `4242 4242 4242 4242`, any future expiry, and any CVC.
10. Stripe sends `checkout.session.completed`. Folio checks the signature and sets that account to Pro.

A canceled subscription does not downgrade the account.

## Tests

```bash
make test
```

The suite covers signup and login, the HttpOnly session cookie, the owner email becoming Pro, one user being unable to read another user's resume, version create / duplicate / delete, the free caps, the AI metric guard with a fake model, a signed Stripe webhook that sets Pro, and a PDF smoke test when RenderCV and Typst are installed.

## Docker

This repository is not deployed from here. To build and run locally:

```bash
docker build -t folio .
docker run --rm -p 8000:8000 --env-file .env \
  -e FOLIO_PUBLIC_URL=http://127.0.0.1:8000 \
  -e FOLIO_COOKIE_SECURE=0 \
  -v folio-data:/data \
  folio
```

The image listens on `0.0.0.0:8000` and serves the built frontend from the same origin. The container runs as root so a mounted data volume is writable. Set `FOLIO_COOKIE_SECURE=1` when the site is served over HTTPS.

## Fly.io

`fly.toml` is a starting point only. It expects a volume named `folio_data` mounted at `/data` and a health check on `/api/health`.

```bash
# Pick an app name that is yours, then:
fly launch --no-deploy --copy-config
fly volumes create folio_data --size 1 --region iad
fly secrets set \
  OPENAI_API_KEY=... \
  STRIPE_SECRET_KEY=... \
  STRIPE_PRICE_ID=... \
  STRIPE_WEBHOOK_SECRET=...
# Set FOLIO_PUBLIC_URL in fly.toml to the https app URL.
fly deploy
```

Point Stripe's live or test webhook at `https://<your-app>.fly.dev/api/billing/webhook`. Do not put secret values in `fly.toml`.

## Limits worth knowing

- There is no admin dashboard, email verification, or password reset.
- The session cookie is `SameSite=Lax` and there is no CSRF token.
- SQLite is one machine. Do not point two app instances at one file.
- Rewrite and tailor are available only on Pro. They are not otherwise rate-limited.
- AI refuses new numbers. It also refuses a multi-word name that shows up in the job text and not on the resume. Employers, titles, and dates on a tailored version are copied from the source version, not from the model.
