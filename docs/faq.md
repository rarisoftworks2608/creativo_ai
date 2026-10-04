# FAQ

**Do I need to pay for any API to use the platform?**
No. Without keys the platform runs, and each AI feature reports clearly that it isn't
configured. Free options: Cloudflare Workers AI for images (daily free allowance), Groq
for text (free tier), gTTS voice-over (free, no key), and the Hugging Face free monthly
credit for AI motion (falls back to zoom/pan). WhatsApp runs in test mode (logged, not
sent) until you add Meta credentials. Facebook/Instagram/LinkedIn publishing needs only
your own developer apps, which are free.

**How do I switch image generation from Cloudflare to OpenAI?**
Put `OPENAI_API_KEY` in `backend/.env`. Then either set `AI_IMAGE_PROVIDER=openai` and
`AI_IMAGE_MODEL=gpt-image-1`, or choose *openai* under Admin Settings → AI providers.
Restart the backend and worker. Nothing else changes.

**Why didn't my post go to Instagram but Facebook worked?**
Instagram downloads media from a public URL. Set `BACKEND_PUBLIC_URL` (production domain,
or a tunnel locally) or use S3/R2 storage. See [Meta guide, Part D](meta-setup-guide.md#part-d-make-media-reachable-for-instagram).

**Can a client see other companies' data?**
No. Every company-scoped request checks membership, and an admin controls which pages each
client sees (Access).

**What happens if a client rejects content twice?**
The first rejection triggers one automatic AI regeneration with their feedback. The second
goes to the team for a manual revision, and admins are notified.

**Can posts go out automatically after approval?**
Yes. Turn on *Admin Settings → Auto-schedule on approval*. Approved content is scheduled to
every connected account for the item's platforms at its planned date and time.

**Is online payment supported?**
No. Subscriptions are managed manually by design (plans, dates, limits, invoices and
payments are recorded by an admin).

**Which languages can content be generated in?**
English, Hindi, Marathi, Gujarati, Tamil, Telugu, Kannada, Bengali, Malayalam, Spanish,
French, German and Arabic. Set it under Admin Settings → AI generation. Video voice-over
follows the same language.

**Do WhatsApp groups get created automatically?**
Creativo AI keeps a notification group per company (client and team numbers) and messages
each member individually, with delivery status per person. If you also want a regular
WhatsApp chat group, create it in WhatsApp and save its invite link on the company's
WhatsApp page.

**Where are reports stored?**
In media storage (local volume or S3/R2), with PDF, Excel and CSV versions of each report.
Monthly reports are generated automatically on the configured day.
