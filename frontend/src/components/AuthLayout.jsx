/**
 * Studio sign-in layout shared by the login, forgot-password and reset-password pages:
 * the form on a clean white side, and an animated showcase on a dark side - a slowly
 * drifting wall of sample creatives, the workflow lighting up step by step and a
 * "generating" card. The wall uses designed sample tiles, never real client work,
 * because this page is public.
 */

const TILES = [
  { tone: 'navy', eyebrow: 'Grand opening', title: 'Your new address of luxury', foot: 'Book a private tour' },
  { tone: 'ember', eyebrow: 'Weekend only', title: '40% off the summer edit', foot: 'Shop now' },
  { tone: 'cream', eyebrow: 'New collection', title: 'Crafted for everyday', foot: 'Discover more' },
  { tone: 'dusk', eyebrow: 'Festive greetings', title: 'Wishing you light and joy', foot: 'From all of us' },
  { tone: 'quote', eyebrow: 'What our clients say', title: '“They understood our vision perfectly.”', foot: '★★★★★' },
  { tone: 'forest', eyebrow: 'Open house', title: 'Sunday, 11 AM – 5 PM', foot: 'See the floor plans' },
  { tone: 'violet', eyebrow: 'Product launch', title: 'Meet the faster way to plan', foot: 'Try it free' },
  { tone: 'sand', eyebrow: 'Behind the scenes', title: 'How our team builds it', foot: 'Swipe →' },
  { tone: 'ink', eyebrow: 'Announcement', title: 'Now serving 12 cities', foot: 'Learn more' },
]

const COLUMNS = [
  [0, 3, 6, 1],
  [2, 5, 8, 4],
  [7, 1, 4, 0],
]

const FLOW = ['Brand', 'Plan', 'Create', 'Approve', 'Publish']

function Tile({ tile }) {
  return (
    <div className={`signin-tile signin-tile-${tile.tone}`}>
      <span className="signin-tile-eyebrow">{tile.eyebrow}</span>
      <span className="signin-tile-title">{tile.title}</span>
      <span className="signin-tile-foot">{tile.foot}</span>
    </div>
  )
}

function Showcase() {
  return (
    <aside className="signin-showcase" aria-label="About Creativo AI">
      <div className="signin-wall" aria-hidden="true">
        {COLUMNS.map((column, index) => (
          <div key={index} className={`signin-col signin-col-${index + 1}`}>
            {/* Two copies so the loop is seamless. */}
            {[...column, ...column].map((tileIndex, i) => (
              <Tile key={i} tile={TILES[tileIndex]} />
            ))}
          </div>
        ))}
      </div>
      <div className="signin-fade" aria-hidden="true" />

      <div className="signin-showcase-body">
        <span className="signin-pill">
          <span className="signin-pill-dot" aria-hidden="true" />
          AI creative studio for agencies
        </span>

        <div className="signin-pitch">
          <h2>
            Every post on brand.
            <br />
            <span>From brief to published.</span>
          </h2>
          <p>
            Plan the calendar, generate creatives and videos, get client approval and publish — one guided workflow for
            every brand you manage.
          </p>
          <ol className="signin-flow" aria-label="Workflow">
            {FLOW.map((label, index) => (
              <li key={label}>
                <span className="signin-flow-step" style={{ animationDelay: `${index * 0.9}s` }}>
                  {label}
                </span>
                {index < FLOW.length - 1 && (
                  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                )}
              </li>
            ))}
          </ol>
        </div>

        <div className="signin-generating" aria-hidden="true">
          <Tile tile={TILES[3]} />
          <div className="signin-generating-text">
            <strong>Generating 3 variations…</strong>
            <span>Festival · Instagram 4:5</span>
            <span className="signin-progress">
              <span />
            </span>
          </div>
        </div>
      </div>
    </aside>
  )
}

export function BrandMark() {
  return (
    <span className="signin-mark" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M17 7.5A6.5 6.5 0 1 0 17 16.5" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
      </svg>
    </span>
  )
}

export default function AuthLayout({ children }) {
  return (
    <div className="signin">
      <main className="signin-main">
        <div className="signin-brand signin-rise">
          <BrandMark />
          <span>Creativo AI</span>
        </div>
        <div className="signin-center">{children}</div>
        <footer className="signin-footer">© {new Date().getFullYear()} Creativo AI</footer>
      </main>
      <Showcase />
    </div>
  )
}
