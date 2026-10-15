import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { PRICE_LABEL, type User } from "../types";

const TEMPLATES = [
  {
    id: "classic",
    label: "Classic",
    price: "Free",
    blurb: "Centered name, a partial rule, and a duration under each role.",
  },
  {
    id: "engineering",
    label: "Engineering",
    price: "Pro",
    blurb: "The title comes first. Contact details are separated with a pipe.",
  },
  {
    id: "sb2nov",
    label: "SB2Nov",
    price: "Pro",
    blurb: "The title sits on its own line, and the organization on the next.",
  },
  {
    id: "harvard",
    label: "Harvard",
    price: "Pro",
    blurb: "Section titles are centered, with tighter margins.",
  },
];

export function Landing() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    api<User>("/api/auth/me")
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  return (
    <>
      <header className="site-header">
        <Link className="wordmark" to="/">
          Folio
        </Link>
        <nav className="nav">
          <a href="#how">How it works</a>
          <a href="#templates">Templates</a>
          <a href="#pricing">Pricing</a>
          {user ? (
            <Link className="button primary" to="/app">
              Open studio
            </Link>
          ) : (
            <>
              <Link to="/login">Sign in</Link>
              <Link className="button primary" to="/signup">
                Start writing
              </Link>
            </>
          )}
        </nav>
      </header>

      <section className="hero">
        <p className="eyebrow">Local resume studio</p>
        <h1>A resume, set in type.</h1>
        <p className="lede">
          Write the facts once. Choose a single-column treatment. Download a
          PDF when the page looks quiet enough to send.
        </p>
        <div className="hero-actions">
          <Link className="button primary" to={user ? "/app" : "/signup"}>
            Start writing
          </Link>
          <a className="button" href="#templates">
            See the templates
          </a>
        </div>
      </section>

      <section className="band" id="how">
        <h2>How it works</h2>
        <div className="steps">
          <article className="card">
            <div className="step-no">01</div>
            <h3>Keep it on this machine</h3>
            <p>
              Create an account here. Your resumes live in the database on
              this computer, and you only see your own.
            </p>
          </article>
          <article className="card">
            <div className="step-no">02</div>
            <h3>Fill the short form</h3>
            <p>
              Contact, summary, experience, education, skills, and projects.
              The name field starts empty.
            </p>
          </article>
          <article className="card">
            <div className="step-no">03</div>
            <h3>Download, or keep a version</h3>
            <p>
              Classic is included. Pro can switch treatments, rewrite a
              bullet, and tailor to a job. Tailoring saves a new version and
              leaves the original in place.
            </p>
          </article>
        </div>
      </section>

      <section className="band" id="templates">
        <h2>Four templates</h2>
        <div className="templates">
          {TEMPLATES.map((template) => (
            <article className="card" key={template.id}>
              <Sheet kind={template.id} />
              <h3>
                {template.label} <span className="muted small">{template.price}</span>
              </h3>
              <p className="small">{template.blurb}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="band" id="pricing">
        <h2>Pricing</h2>
        <div className="prices">
          <article className="card">
            <h3>Free</h3>
            <p className="price">$0</p>
            <ul>
              <li>1 resume</li>
              <li>1 version, and saving updates it</li>
              <li>Classic template</li>
              <li>PDF download</li>
            </ul>
          </article>
          <article className="card pro-card">
            <h3>Pro</h3>
            <p className="price">{PRICE_LABEL}</p>
            <ul>
              <li>Up to 25 resumes</li>
              <li>30 versions on each resume</li>
              <li>Classic, Engineering, SB2Nov, and Harvard</li>
              <li>Rewrite a bullet</li>
              <li>Tailor to a pasted job description</li>
            </ul>
          </article>
        </div>
      </section>

      <footer className="site-footer">
        <p>Folio is a local studio. Resumes stay in the database on this machine.</p>
      </footer>
    </>
  );
}

function Sheet({ kind }: { kind: string }) {
  if (kind === "engineering") {
    return (
      <div className="sheet sheet-engineering" aria-hidden="true">
        <div className="who">Alex Morgan</div>
        <div>Austin · TX | alex@example.com</div>
        <div className="rule" />
        <strong>Engineer</strong>, Northwind
      </div>
    );
  }
  if (kind === "sb2nov") {
    return (
      <div className="sheet sheet-sb2nov" aria-hidden="true">
        <div className="who">Alex Morgan</div>
        <div className="rule" />
        <strong>Engineer</strong>
        <div className="org">Northwind</div>
      </div>
    );
  }
  if (kind === "harvard") {
    return (
      <div className="sheet sheet-harvard" aria-hidden="true">
        <div className="who">Alex Morgan</div>
        <div className="rule" />
        <div>Experience</div>
        <div>Northwind, Engineer</div>
      </div>
    );
  }
  return (
    <div className="sheet sheet-classic" aria-hidden="true">
      <div className="who">Alex Morgan</div>
      <div>Software engineer</div>
      <div className="rule" />
      <div>Northwind, Engineer</div>
      <div className="muted">Jan 2022 – present · 4 years</div>
    </div>
  );
}
