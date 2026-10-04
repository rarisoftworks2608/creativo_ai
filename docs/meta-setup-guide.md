# Meta setup guide: Facebook, Instagram auto-posting and WhatsApp

This guide connects Creativo AI to Meta so the platform can **publish approved content to
Facebook Pages and Instagram**, **read post analytics**, and **send WhatsApp notifications**.
You do it once for the agency. After that, each client's Page and Instagram account is
connected with one click ("Continue with Facebook").

> Meta changes menu names often. If a label below doesn't match exactly, search the
> developer dashboard for the product name (for example "Facebook Login for Business").

---

## Part A: Prepare the accounts (for each client)

Instagram posting through the API only works for **professional** Instagram accounts that
are **linked to a Facebook Page**.

1. **Facebook Page.** The client needs a Facebook Page for the brand.
2. **Professional Instagram account.**
   In the Instagram app go to *Settings → Account type and tools → Switch to professional
   account*, then choose **Business** (or Creator).
3. **Link Instagram to the Page.**
   In the Instagram app go to *Settings → Accounts Center*, or on Facebook go to *Page →
   Settings → Linked accounts → Instagram*, and connect the account.
4. **Give the agency access.**
   The person who will click "Continue with Facebook" needs **full control** of the Page.
   The cleanest way:
   - The client adds your agency's **Business portfolio** as a partner in their Meta Business
     Suite (*Settings → Partners*), with **full control of the Page and Instagram account**.
   - Alternatively, they add your team member as a Page admin.

## Part B: Create the Meta app (once, for the agency)

### B1. Business portfolio and app

1. Go to <https://business.facebook.com>. Create or choose the agency's **Business
   portfolio**, and fill in the business details.
2. Go to <https://developers.facebook.com>, then *My Apps → Create app*.
3. When asked what the app should do, choose all of these use cases (or app type
   **Business**, if you see that option):
   - **Manage everything on your Page**
   - **Manage messaging & content on Instagram**: pick the *"API setup with Facebook
     login"* option.
   - **Connect with customers through WhatsApp** (for Part E)
4. Connect the app to your Business portfolio when asked.

### B2. App settings

In *App settings → Basic*:

| Field | Value |
|---|---|
| App ID | copy it into `backend/.env` as `META_APP_ID` |
| App secret | click *Show* and copy it into `backend/.env` as `META_APP_SECRET` |
| App domains | your domain, for example `app.yourdomain.com` |
| Privacy policy URL | a public page on your website (required to go live) |
| Terms of service URL | a public page on your website |
| User data deletion | a URL or instructions page (required) |
| App icon, category | anything appropriate |

### B3. Facebook Login for Business

1. Add the **Facebook Login for Business** product if it isn't already there.
2. Under *Settings*, add these **Valid OAuth Redirect URIs**:
   ```
   https://app.yourdomain.com/oauth/callback/meta
   http://localhost:5173/oauth/callback/meta        (for local development)
   ```
   The exact URIs your installation expects are shown under **Admin Settings →
   Integrations** and in the "how to enable" dialog on the Social accounts page. They are
   built from `SOCIAL_OAUTH_REDIRECT_BASE`, which defaults to `FRONTEND_URL`.
3. **Recommended: create a configuration.**
   Go to *Facebook Login for Business → Configurations → Create configuration*:
   - Login variation: **General**
   - Access token: **User access token**
   - Permissions: select all the permissions in the table below
   - Save it, then copy the **Configuration ID** into `backend/.env` as
     `META_LOGIN_CONFIG_ID`.

   Without a configuration the app requests the scopes from `META_OAUTH_SCOPES` directly.
   Business apps are expected to use configurations, though.

### B4. Permissions the platform uses

| Permission | Used for |
|---|---|
| `pages_show_list` | listing the Pages the login manages |
| `pages_read_engagement` | reading Page and post data |
| `pages_manage_posts` | **publishing to Facebook Pages** |
| `read_insights` | Facebook Page and post analytics |
| `business_management` | Pages and Instagram accounts shared through a Business portfolio |
| `instagram_basic` | reading the linked Instagram account |
| `instagram_content_publish` | **publishing to Instagram** (posts, carousels, reels, stories) |
| `instagram_manage_insights` | Instagram post and account analytics |
| `whatsapp_business_messaging`, `whatsapp_business_management` | WhatsApp (Part E, on the system user token) |

### B5. Test before App Review (development mode)

While the app is in **Development** mode, these permissions already work for anyone with
a role on the app (*App roles → Roles*: admins, developers, testers) and for Pages they
manage. Use this to test the whole flow with the agency's own Page and Instagram account
first. Set up the public media URL from Part D before testing Instagram.

### B6. Business verification, App Review and Live mode (to manage client Pages)

To use the app on Pages owned by **other businesses** (your clients), Meta requires all of
the following:

1. **Business verification.** In Business portfolio go to *Settings → Security Center →
   Start verification* and upload business documents, for example a GST certificate and a
   utility bill.
2. **Advanced access + App Review.** In the developer dashboard go to *App Review →
   Permissions and features* and request **Advanced access** for each permission in B4.
   For each one:
   - Explain how it is used. You can copy from the "Used for" column above.
   - Upload a **screencast**: log in to Creativo AI, open Social accounts, click "Continue
     with Facebook", pick a Page, then schedule and publish a post that appears on
     Facebook and Instagram.
   - Give the reviewer a test login for your Creativo AI installation.
3. When approved, switch the app to **Live** at the top of the dashboard.

## Part C: Connect accounts in Creativo AI

1. Fill in `backend/.env`:
   ```
   META_APP_ID=...
   META_APP_SECRET=...
   META_LOGIN_CONFIG_ID=...             # optional but recommended
   META_GRAPH_API_VERSION=v23.0         # keep at a currently supported Graph API version
   FRONTEND_URL=https://app.yourdomain.com
   BACKEND_PUBLIC_URL=https://app.yourdomain.com
   ```
2. Restart the backend and the Celery worker.
3. Open **Companies → (company) → Social accounts → Continue with Facebook**.
4. Log in to Facebook. In the dialog, **select the client's Page and its Instagram
   account** and allow every permission.
5. Back in Creativo AI, tick the accounts to connect: the Facebook Page, the Instagram
   account, or both. Then click **Connect**.
6. Click **Test connection** on each account card.

**About tokens.** Page tokens obtained this way don't expire on a timer. They stop working
only if someone changes their Facebook password, removes the app, or loses access to the
Page. If that happens the account is marked **Expired**, admins get a notification, and
you click **Reconnect**.

**Manual fallback.** You can also click **Connect manually** and paste a Page access token
from the Graph API Explorer. For Instagram, enter the Instagram account ID and the parent
Page ID.

## Part D: Make media reachable for Instagram

Facebook and LinkedIn receive the actual file from Creativo AI. **Instagram doesn't**: it
downloads each image or video from a **public HTTPS URL**. Instagram also accepts only
**JPEG** images with an aspect ratio between **4:5 and 1.91:1**. Creativo AI converts and
crops images automatically before publishing.

- **Production (Docker + your domain).** Set `BACKEND_PUBLIC_URL=https://app.yourdomain.com`.
  The bundled Nginx serves `/media/` publicly.
- **S3 / Cloudflare R2.** Set `USE_S3_STORAGE=True` with a bucket (or CDN domain in
  `AWS_S3_CUSTOM_DOMAIN`) that allows public reads. URLs are then public automatically.
- **Local development.** Your laptop isn't reachable from the internet, so expose the
  backend with a tunnel:
  ```
  cloudflared tunnel --url http://localhost:8000      # or: ngrok http 8000
  ```
  Put the printed `https://....trycloudflare.com` URL into `BACKEND_PUBLIC_URL`, then
  restart the backend and worker.

The scheduling dialog warns you ("Instagram needs a public media URL") when this isn't set
up yet.

**Video (Reels).** Rendered videos are already MP4 H.264/AAC with fast-start. Vertical
9:16 videos are posted as Reels.

**Publishing limit.** Meta enforces a rolling 24-hour limit on how many posts each
Instagram account can publish through the API. Normal agency volumes stay well under it.

## Part E: WhatsApp Business Cloud API

Until this part is done, WhatsApp runs in **test mode** (`WHATSAPP_PROVIDER=console`).
Every message is logged in the company's WhatsApp delivery log but not actually sent, so
you can build and test the whole workflow first.

1. **Add WhatsApp to the app.** Use the "Connect with customers through WhatsApp" use case
   or add the **WhatsApp** product. Meta creates a test WhatsApp Business Account (WABA)
   and a test number that can message up to 5 verified numbers. Add your own phone under
   *API Setup → To* for testing.
2. **Add the real business number.** In *WhatsApp Manager → Phone numbers → Add phone
   number*:
   - Use a number **not** currently registered in the WhatsApp app (or migrate it).
   - Verify it by SMS or voice call.
   - Set the display name. Meta reviews it.
3. **Create a permanent token** with a system user:
   - In *Business portfolio → Settings → Users → System users → Add*, create one with the
     **Admin** role.
   - Use *Assign assets* to give it the app (full control) and the WhatsApp account (full
     control).
   - Click *Generate token*, choose the app, set expiry to **Never**, and select
     `whatsapp_business_messaging`, `whatsapp_business_management` and
     `business_management`.
   - Copy the token into `WHATSAPP_ACCESS_TOKEN`.
4. **Copy the IDs.** In *WhatsApp → API Setup*, copy the **Phone number ID** into
   `WHATSAPP_PHONE_NUMBER_ID` and the **WhatsApp Business Account ID** into
   `WHATSAPP_BUSINESS_ACCOUNT_ID`. Then set `WHATSAPP_PROVIDER=meta`.
5. **Create the message templates.** Business-initiated messages must use templates Meta
   has approved. In *WhatsApp Manager → Message templates → Create template*, create each
   one below with:
   - Category: **Utility**
   - Language: **English**
   - The exact name and body shown
   - Example values for each `{{n}}` when Meta asks for them

   | Name | Body |
   |---|---|
   | `content_approval_required` | Hello! New content for {{1}} is ready for your review: "{{2}}" (planned for {{3}}). Please review and approve it here: {{4}} |
   | `content_regenerated` | Updated content for {{1}} is ready: "{{2}}" has been regenerated using your feedback. Please review it here: {{3}} |
   | `content_approved` | "{{1}}" for {{2}} was approved by {{3}}. It will be published as scheduled. |
   | `content_changes_requested` | Changes requested on "{{1}}" for {{2}}. Feedback: {{3}}. Review: {{4}} |
   | `content_published` | "{{1}}" is now live on {{2}} for {{3}}. View it here: {{4}} |
   | `publishing_failed` | Publishing "{{1}}" to {{2}} failed for {{3}}. Reason: {{4}}. Please check the publishing queue. |
   | `approval_reminder` | Reminder: "{{1}}" for {{2}} has been waiting {{3}} hours for your approval. Review it here: {{4}} |
   | `monthly_report_ready` | Your {{1}} marketing report for {{2}} is ready. View and download it here: {{3}} |

   These mappings are pre-loaded under **WhatsApp → Templates** in Creativo AI. If you
   change a name or wording in WhatsApp Manager, edit the mapping there to match. Once
   Meta approves them, click **Sync status from Meta**.
6. **Webhook for delivery and read receipts.** In the app go to *WhatsApp → Configuration →
   Webhook*:
   - Callback URL: `https://app.yourdomain.com/api/v1/whatsapp/webhook/`
   - Verify token: any random string, which you also put in `WHATSAPP_WEBHOOK_VERIFY_TOKEN`
   - Click *Verify and save*, then **subscribe to the `messages` field**.

   Signatures are checked with `WHATSAPP_APP_SECRET`, which defaults to `META_APP_SECRET`.
7. **Billing.** Add a payment method in *WhatsApp Manager → Payment methods*. Meta bills
   template messages; check Meta's current WhatsApp pricing for your country.
8. **Test it.** Restart the backend and worker. Then open *Company → WhatsApp → Send test*,
   which uses Meta's built-in `hello_world` template.
9. **Set up each company.** On the company's WhatsApp page:
   - Enable WhatsApp.
   - Add the client's numbers and your internal team numbers (with country code, for
     example +91…).
   - Choose which events send messages.
   - Click **Create group**.

**About "groups".** Creativo AI sends every message to each member of the company's
notification group individually. This works on every WhatsApp Business account and gives
per-person delivery status. If the team also wants a normal WhatsApp group for
conversation, create it in the WhatsApp app and paste its invite link on the company's
WhatsApp page for reference.

## Part F: Common errors

| Error | Meaning | Fix |
|---|---|---|
| `(#10) ... does not have permission` / `(#200)` | A permission is missing or not approved | Reconnect and allow every permission. For client Pages, finish App Review (B6). |
| `(#190) Invalid OAuth access token` | Token revoked or expired | Account shows **Expired**; click **Reconnect**. |
| "No Facebook Pages were found" | The login doesn't manage any Page, or Pages weren't ticked in the dialog | Give the person full control of the Page, log in again and tick it. |
| "No Instagram professional account is linked" | The Instagram account is personal or not linked | Do Part A steps 2–3. |
| Instagram "media could not be fetched" / "needs a public media URL" | Media URL isn't reachable from the internet | Part D. |
| WhatsApp `131030` recipient not allowed | Test number can only message verified recipients | Add the recipient under *API Setup → To*, or use the real number. |
| WhatsApp `132001` template does not exist | Template name or language doesn't match WhatsApp Manager | Fix the mapping under WhatsApp → Templates, then *Sync*. |
| WhatsApp message stuck at "Sent" | No webhook configured | Part E step 6. |
