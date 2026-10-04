# Admin guide

For the agency team that runs Creativo AI day to day.

## The monthly workflow

1. **Company & client.**
   - *Companies → + Add company*: fill in the business information until onboarding shows
     100%.
   - *Add client* creates the client's login. They receive their credentials by email.
2. **Brand.** On *Company → Brand* add the logo (PNG with transparent background works
   best), colours, fonts, voice, do's and don'ts, and personas. Every AI generation uses it.
3. **Plan.** On *Company → Subscription → Assign plan*, pick the plan, dates and any custom
   limits.
4. **Connect channels.**
   - *Social accounts → Continue with Facebook / LinkedIn* (see the
     [Meta guide](meta-setup-guide.md)).
   - *WhatsApp*: add the client's and the team's numbers and create the group.
5. **Calendar.**
   - *Calendar → Excel template*, fill it in, then *Import*.
   - Or add items one by one.
   - Items generate automatically on their date and time, or click **Generate now**.
6. **Review.**
   - Generated content goes to the client for approval: in-app, by email if enabled, and
     on WhatsApp.
   - *Approvals* shows every company's queue, oldest first. You can approve or request
     changes on a client's behalf.
7. **Publish.**
   - Approved items appear under *Company → Publishing → Ready to publish*.
   - Click **Schedule / publish**, choose accounts, adjust the caption, and pick a time or
     **Publish now**.
   - Turn on *Admin Settings → Auto-schedule on approval* to skip this step: approved
     content then goes out at its planned time automatically.
8. **Measure.**
   - *Analytics* refreshes automatically (default every 6 hours) or with **Sync now**.
   - Monthly reports are generated on the configured day and emailed or sent on WhatsApp to
     clients.

## Where to find things

| I want to… | Go to |
|---|---|
| See what needs attention | **Dashboard** (pending approvals, failed posts, expiring plans, …) |
| Approve content for a client | **Approvals**, or *Company → Approvals* |
| See everything scheduled / published | **Publishing** (all companies) or *Company → Publishing* |
| Retry a failed post | *Company → Publishing → Failed → Retry* (the error log shows each attempt) |
| Edit a video's narration and re-render | *Company → Videos → Edit scenes & re-render* |
| Add background music for videos | **Music Library** (royalty-free tracks only) |
| Change AI provider (for example Cloudflare → OpenAI) | **Admin Settings → AI providers** (key in `.env` first) |
| Set content language (Hindi, Marathi, …) | **Admin Settings → AI generation** |
| Map WhatsApp templates | **WhatsApp** |
| Generate a report | *Company → Reports* (client reports) or **Reports** (admin reports) |
| Record a payment / invoice | *Company → Subscription → Billing* |
| See usage against plan limits | **Subscriptions → Usage overview** |
| Control what a client can see | **Access**: tick pages per client |
| Investigate who did what | **Activity Log** |
| Check background jobs | **Jobs** (generation, publishing, reports, analytics sync) |
| Check the servers | **System Health** (database, Redis, workers, storage, FFmpeg, integrations) |

## Approval rules

- A client can **approve**, or **request changes** with feedback.
- The **first** change request triggers **one automatic AI regeneration** that uses the
  feedback. A second change request goes to your team to revise manually (you'll get a
  notification).
- Clients who don't respond get one automatic reminder per review round, after the hours
  set in Admin Settings (default 24).
- Approving locks in the selected variation. That exact image and caption is what gets
  published.
- Every step is recorded in the item's **History**.

## Subscriptions and limits

- Plans hold monthly limits for creatives, videos, published posts, storage and social
  accounts (0 = unlimited). A subscription can override any limit for one company.
- Usage resets each month on the subscription's start day.
- Usage is always tracked. Work is only **blocked** at the limit when *Admin Settings →
  Enforce plan limits* is on. Admins are alerted once a day per limit.
- Billing is manual: record invoices, payments (UPI, bank transfer, cash, …) and
  references. Invoices past their due date flip to *Overdue* automatically.

## Admin settings reference

| Section | Settings |
|---|---|
| AI providers & models | Override `.env` per modality; shows which keys are configured |
| AI generation | Variations per request, daily limit per company, content language |
| Publishing | Kill switch, auto-schedule on approval, default publish time, retry attempts, timezone |
| Approvals & notifications | Reminder delay, notification emails, upload size limit |
| Analytics & reports | Auto-sync and interval, monthly reports (day, email, WhatsApp) |
| Subscriptions | Enforce limits, expiry reminder days |
