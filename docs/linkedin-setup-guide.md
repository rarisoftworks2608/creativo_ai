# LinkedIn setup guide

This guide lets Creativo AI publish to LinkedIn **Company Pages** (or a personal profile)
and read Page post analytics.

## 1. Create the app

1. Go to <https://www.linkedin.com/developers/apps> and click **Create app**.
2. Associate it with the agency's own LinkedIn **Company Page**. A Page admin has to
   approve the association.
3. Add a logo and the privacy policy URL, then create the app.

## 2. Add products

Under the **Products** tab, request:

| Product | Gives you | Approval |
|---|---|---|
| Sign In with LinkedIn using OpenID Connect | `openid`, `profile` (who logged in) | instant |
| Share on LinkedIn | `w_member_social` (post as a personal profile) | instant |
| **Community Management API** | `w_organization_social`, `r_organization_social`, `rw_organization_admin` (post as and read analytics for **Company Pages**) | reviewed by LinkedIn (business details + use case) |

Until Community Management API is approved, "Continue with LinkedIn" still works but only
offers the personal profile. Creativo AI shows a warning explaining this.

## 3. Auth settings

In the **Auth** tab:

- Copy the **Client ID** and **Primary Client Secret** into `backend/.env` as
  `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET`.
- Add these **Authorized redirect URLs**:
  ```
  https://app.yourdomain.com/oauth/callback/linkedin
  http://localhost:5173/oauth/callback/linkedin
  ```
  The exact URLs for your installation are shown under Admin Settings → Integrations.

## 4. API version

LinkedIn's REST API is versioned by month (`LINKEDIN_API_VERSION=YYYYMM`). Each version
stays supported for about a year. If LinkedIn calls start failing with a "version"
error, set it to a recent month and restart the backend and worker.

## 5. Connect

1. Restart the backend and worker.
2. Open **Company → Social accounts → Continue with LinkedIn** and log in as someone who
   is an **admin of the client's Company Page**.
3. Tick the Company Page (or the personal profile) and click **Connect**.

LinkedIn access tokens last about 60 days. When LinkedIn issues a refresh token (partner
apps), Creativo AI renews it automatically every night, and you can also click **Refresh
token**. Otherwise the account is flagged before it expires; reconnect it with the
LinkedIn button.

## Notes

- **Hashtags** are converted to real, clickable LinkedIn hashtags, and special characters
  are escaped automatically.
- **Analytics** (impressions, clicks, likes, comments, shares, followers) are available
  only for **Company Page** posts. LinkedIn doesn't expose them for personal profiles.
- **Videos** are uploaded in chunks and LinkedIn processes them after publishing. They can
  take a few minutes to appear.
