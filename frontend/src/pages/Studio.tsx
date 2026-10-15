import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, api } from "../api";
import {
  emptyContent,
  type ResumeContent,
  type ResumeDetail,
  type ResumeSummary,
  type TemplateInfo,
  type User,
  type Version,
} from "../types";

const STEPS = ["Contact", "Summary", "Experience", "Education", "Skills", "Projects"] as const;

export function Studio() {
  const navigate = useNavigate();
  const [me, setMe] = useState<User | null>(null);
  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [resume, setResume] = useState<ResumeDetail | null>(null);
  const [versionId, setVersionId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [template, setTemplate] = useState("classic");
  const [content, setContent] = useState<ResumeContent>(emptyContent());
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [step, setStep] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState("");

  useEffect(() => {
    api<User>("/api/auth/me")
      .then(async (user) => {
        setMe(user);
        const [listed, catalog] = await Promise.all([
          api<ResumeSummary[]>("/api/resumes"),
          api<{ templates: TemplateInfo[] }>("/api/templates"),
        ]);
        setResumes(listed);
        setTemplates(catalog.templates);
        if (listed[0]) {
          await openResume(listed[0].id, null);
        }
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          navigate("/login");
          return;
        }
        setError(err instanceof Error ? err.message : "Could not open the studio.");
      });
  }, [navigate]);

  function applyVersion(next: Version) {
    setVersionId(next.id);
    setTemplate(next.template);
    setContent(next.content);
    setDirty(false);
  }

  async function openResume(resumeId: string, preferredVersion: string | null) {
    const detail = await api<ResumeDetail>(`/api/resumes/${resumeId}`);
    setResume(detail);
    setTitle(detail.title);
    const chosen =
      detail.versions.find((item) => item.id === preferredVersion) ??
      detail.versions[detail.versions.length - 1];
    if (chosen) {
      applyVersion(chosen);
    }
    const listed = await api<ResumeSummary[]>("/api/resumes");
    setResumes(listed);
  }

  function edit(next: ResumeContent) {
    setContent(next);
    setDirty(true);
  }

  async function createResume() {
    setError(null);
    try {
      const created = await api<ResumeDetail>("/api/resumes", {
        method: "POST",
        body: JSON.stringify({ title: "Untitled resume" }),
      });
      await openResume(created.id, created.versions[0]?.id ?? null);
      setStep(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create a resume.");
    }
  }

  async function save(): Promise<boolean> {
    if (!resume || !versionId) return false;
    setBusy(true);
    setError(null);
    try {
      await api(`/api/resumes/${resume.id}`, {
        method: "PUT",
        body: JSON.stringify({ title }),
      });
      const saved = await api<Version>(`/api/versions/${versionId}`, {
        method: "PUT",
        body: JSON.stringify({ content, template }),
      });
      await openResume(resume.id, saved.id);
      setMessage("Saved.");
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function saveAsNew() {
    if (!resume) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api<Version>(`/api/resumes/${resume.id}/versions`, {
        method: "POST",
        body: JSON.stringify({ content, template }),
      });
      await openResume(resume.id, created.id);
      setMessage(`Saved ${created.label}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save a new version.");
    } finally {
      setBusy(false);
    }
  }

  async function duplicate(id: string) {
    if (!resume) return;
    setError(null);
    try {
      const created = await api<Version>(`/api/resumes/${resume.id}/versions`, {
        method: "POST",
        body: JSON.stringify({ from_version_id: id }),
      });
      await openResume(resume.id, created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not duplicate.");
    }
  }

  async function removeVersion(id: string) {
    if (!resume || !window.confirm("Delete this version?")) return;
    setError(null);
    try {
      await api(`/api/versions/${id}`, { method: "DELETE" });
      await openResume(resume.id, null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete.");
    }
  }

  async function removeResume() {
    if (!resume || !window.confirm("Delete this resume?")) return;
    await api(`/api/resumes/${resume.id}`, { method: "DELETE" });
    const listed = await api<ResumeSummary[]>("/api/resumes");
    setResumes(listed);
    if (listed[0]) {
      await openResume(listed[0].id, null);
    } else {
      setResume(null);
      setVersionId(null);
      setContent(emptyContent());
    }
  }

  function chooseTemplate(next: TemplateInfo) {
    if (next.pro && me?.plan !== "pro") {
      setError("That template is part of Pro.");
      return;
    }
    setTemplate(next.id);
    setDirty(true);
    setError(null);
  }

  async function download() {
    if (!resume || !versionId) return;
    setError(null);
    try {
      if (dirty) {
        const saved = await save();
        if (!saved) return;
      }
      const response = await fetch(`/api/versions/${versionId}/pdf`, {
        credentials: "same-origin",
      });
      if (!response.ok) {
        const data = await response.json();
        throw new ApiError(response.status, data.detail || "PDF failed.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const disposition = response.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="([^"]+)"/);
      link.href = url;
      link.download = match?.[1] || "resume.pdf";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF failed.");
    }
  }

  async function rewrite(section: "experience" | "education" | "projects", index: number, line: number) {
    if (!versionId) return;
    if (dirty) {
      setError("Save this version before rewriting.");
      return;
    }
    const bullet = content[section][index].highlights[line];
    setBusy(true);
    setError(null);
    try {
      const result = await api<{ bullet: string }>("/api/ai/rewrite", {
        method: "POST",
        body: JSON.stringify({ version_id: versionId, bullet, section, index }),
      });
      const next = structuredClone(content);
      next[section][index].highlights[line] = result.bullet;
      edit(next);
      setMessage("Rewritten. Save to keep it.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rewrite failed.");
    } finally {
      setBusy(false);
    }
  }

  async function tailor() {
    if (!resume || !versionId) return;
    if (dirty) {
      setError("Save this version before tailoring. Tailor copies the saved version.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await api<Version>("/api/ai/tailor", {
        method: "POST",
        body: JSON.stringify({ version_id: versionId, job_description: job }),
      });
      await openResume(resume.id, created.id);
      setMessage("Tailored version saved. The source version is unchanged.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tailor failed.");
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    await api("/api/auth/logout", { method: "POST" });
    navigate("/");
  }

  return (
    <div className="studio">
      <header className="studio-top">
        <div>
          <Link className="wordmark" to="/">
            Folio
          </Link>
          <p className="muted small">{me ? `${me.email} · ${me.plan}` : ""}</p>
        </div>
        <nav className="nav">
          <Link to="/billing">Billing</Link>
          <button className="button quiet" type="button" onClick={logout}>
            Log out
          </button>
        </nav>
      </header>

      {error ? <p className="notice error">{error}</p> : null}
      {message ? <p className="notice">{message}</p> : null}

      <div className="row-actions">
        <button className="button" type="button" onClick={createResume}>
          New resume
        </button>
        {resumes.length > 0 ? (
          <select
            value={resume?.id ?? ""}
            onChange={(event) => openResume(event.target.value, null)}
            aria-label="Resume"
          >
            {resumes.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>
        ) : null}
      </div>

      {!resume ? (
        <section className="panel">
          <h1>No resumes yet</h1>
          <p>Create one and fill the form. The name field uses the placeholder Alex Morgan.</p>
        </section>
      ) : (
        <div className="studio-grid">
          <aside className="panel">
            <h2 className="small">Versions</h2>
            <div className="version-list">
              {resume.versions.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  aria-current={item.id === versionId}
                  onClick={() => applyVersion(item)}
                >
                  {item.label}
                  <div className="muted small">{item.template}</div>
                </button>
              ))}
            </div>
            <div className="row-actions">
              <button className="button quiet" type="button" onClick={() => versionId && duplicate(versionId)}>
                Duplicate
              </button>
              <button className="button quiet" type="button" onClick={() => versionId && removeVersion(versionId)}>
                Delete
              </button>
            </div>
          </aside>

          <section className="panel">
            <label className="field">
              <span>Resume title</span>
              <input value={title} onChange={(event) => { setTitle(event.target.value); setDirty(true); }} />
            </label>
            <div className="step-nav">
              {STEPS.map((label, index) => (
                <button
                  key={label}
                  type="button"
                  aria-current={step === index}
                  onClick={() => setStep(index)}
                >
                  {label}
                </button>
              ))}
            </div>
            {step === 0 ? <ContactStep content={content} edit={edit} /> : null}
            {step === 1 ? (
              <label className="field">
                <span>Summary</span>
                <textarea
                  value={content.summary}
                  onChange={(event) => edit({ ...content, summary: event.target.value })}
                />
              </label>
            ) : null}
            {step === 2 ? (
              <EntryList
                empty={{ company: "", position: "", location: "", start_date: "", end_date: "", highlights: [""] }}
                items={content.experience}
                addLabel="Add a role"
                onChange={(experience) => edit({ ...content, experience })}
                render={(item, index, update) => (
                  <>
                    <div className="two">
                      <Field label="Company" value={item.company} onChange={(company) => update({ company })} />
                      <Field label="Title" value={item.position} onChange={(position) => update({ position })} />
                      <Field label="Location" value={item.location} onChange={(location) => update({ location })} />
                      <Field label="Start" value={item.start_date} placeholder="YYYY-MM" onChange={(start_date) => update({ start_date })} />
                      <Field label="End" value={item.end_date} placeholder="YYYY-MM or present" onChange={(end_date) => update({ end_date })} />
                    </div>
                    <Bullets
                      lines={item.highlights}
                      onChange={(highlights) => update({ highlights })}
                      onRewrite={(line) => rewrite("experience", index, line)}
                      pro={me?.plan === "pro"}
                    />
                  </>
                )}
              />
            ) : null}
            {step === 3 ? (
              <EntryList
                empty={{ institution: "", degree: "", area: "", location: "", start_date: "", end_date: "", highlights: [] }}
                items={content.education}
                addLabel="Add a school"
                onChange={(education) => edit({ ...content, education })}
                render={(item, index, update) => (
                  <>
                    <div className="two">
                      <Field label="School" value={item.institution} onChange={(institution) => update({ institution })} />
                      <Field label="Degree" value={item.degree} onChange={(degree) => update({ degree })} />
                      <Field label="Field of study" value={item.area} onChange={(area) => update({ area })} />
                      <Field label="Location" value={item.location} onChange={(location) => update({ location })} />
                      <Field label="Start" value={item.start_date} placeholder="YYYY-MM" onChange={(start_date) => update({ start_date })} />
                      <Field label="End" value={item.end_date} placeholder="YYYY-MM" onChange={(end_date) => update({ end_date })} />
                    </div>
                    <Bullets
                      lines={item.highlights}
                      onChange={(highlights) => update({ highlights })}
                      onRewrite={(line) => rewrite("education", index, line)}
                      pro={me?.plan === "pro"}
                    />
                  </>
                )}
              />
            ) : null}
            {step === 4 ? (
              <EntryList
                empty={{ label: "", details: "" }}
                items={content.skills}
                addLabel="Add a skill line"
                onChange={(skills) => edit({ ...content, skills })}
                render={(item, index, update) => (
                  <div className="two">
                    <Field label={`Label ${index + 1}`} value={item.label} onChange={(label) => update({ label })} />
                    <Field label="Details" value={item.details} onChange={(details) => update({ details })} />
                  </div>
                )}
              />
            ) : null}
            {step === 5 ? (
              <EntryList
                empty={{ name: "", url: "", location: "", start_date: "", end_date: "", summary: "", highlights: [""] }}
                items={content.projects}
                addLabel="Add a project"
                onChange={(projects) => edit({ ...content, projects })}
                render={(item, index, update) => (
                  <>
                    <div className="two">
                      <Field label="Name" value={item.name} onChange={(name) => update({ name })} />
                      <Field label="Link" value={item.url} onChange={(url) => update({ url })} />
                      <Field label="Start" value={item.start_date} placeholder="YYYY-MM" onChange={(start_date) => update({ start_date })} />
                      <Field label="End" value={item.end_date} placeholder="YYYY-MM or present" onChange={(end_date) => update({ end_date })} />
                    </div>
                    <label className="field">
                      <span>Summary</span>
                      <textarea value={item.summary} onChange={(event) => update({ summary: event.target.value })} />
                    </label>
                    <Bullets
                      lines={item.highlights}
                      onChange={(highlights) => update({ highlights })}
                      onRewrite={(line) => rewrite("projects", index, line)}
                      pro={me?.plan === "pro"}
                    />
                  </>
                )}
              />
            ) : null}
            <div className="row-actions">
              <button className="button primary" type="button" onClick={save} disabled={busy}>
                {busy ? "Saving" : "Save"}
              </button>
              <button
                className="button"
                type="button"
                onClick={saveAsNew}
                disabled={busy || me?.plan !== "pro"}
                title={me?.plan === "pro" ? "Save a new version" : "Free keeps one version. Saving updates it."}
              >
                Save as new version
              </button>
              {dirty ? <span className="muted small">Unsaved changes</span> : null}
            </div>
          </section>

          <aside className="panel">
            <h2 className="small">Template</h2>
            {templates.map((item) => (
              <button
                key={item.id}
                type="button"
                className="template-option"
                aria-pressed={template === item.id}
                onClick={() => chooseTemplate(item)}
              >
                <strong>{item.label}</strong>{" "}
                {item.pro ? <span className="muted">Pro</span> : <span className="muted">Free</span>}
                <div className="small">{item.blurb}</div>
              </button>
            ))}
            <button className="button primary" type="button" onClick={download}>
              Download PDF
            </button>
            <h2 className="small">Tailor</h2>
            <p className="small muted">
              Tailor writes a new version. The version you have open stays as it is.
              Numbers, employers, titles, and dates have to already be on the resume.
            </p>
            <textarea
              value={job}
              onChange={(event) => setJob(event.target.value)}
              placeholder="Paste a job description"
            />
            <button className="button" type="button" onClick={tailor} disabled={busy || me?.plan !== "pro"}>
              Save tailored version
            </button>
            <div className="row-actions">
              <button className="button quiet" type="button" onClick={removeResume}>
                Delete resume
              </button>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

function ContactStep({
  content,
  edit,
}: {
  content: ResumeContent;
  edit: (next: ResumeContent) => void;
}) {
  const contact = content.contact;
  function set<K extends keyof typeof contact>(key: K, value: string) {
    edit({ ...content, contact: { ...contact, [key]: value } });
  }
  return (
    <div className="two">
      <Field label="Name" value={contact.name} placeholder="Alex Morgan" onChange={(value) => set("name", value)} />
      <Field label="Headline" value={contact.headline} onChange={(value) => set("headline", value)} />
      <Field label="Email" value={contact.email} onChange={(value) => set("email", value)} />
      <Field label="Phone" value={contact.phone} placeholder="+1 512 555 0100" onChange={(value) => set("phone", value)} />
      <Field label="Location" value={contact.location} onChange={(value) => set("location", value)} />
      <Field label="Website" value={contact.website} onChange={(value) => set("website", value)} />
      <Field label="LinkedIn" value={contact.linkedin} placeholder="username" onChange={(value) => set("linkedin", value)} />
      <Field label="GitHub" value={contact.github} placeholder="username" onChange={(value) => set("github", value)} />
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function Bullets({
  lines,
  onChange,
  onRewrite,
  pro,
}: {
  lines: string[];
  onChange: (lines: string[]) => void;
  onRewrite: (index: number) => void;
  pro: boolean;
}) {
  const shown = lines.length ? lines : [""];
  return (
    <div>
      <span className="label">Bullets</span>
      {shown.map((line, index) => (
        <div className="bullet-row" key={index}>
          <input
            value={line}
            onChange={(event) => {
              const next = [...shown];
              next[index] = event.target.value;
              onChange(next);
            }}
          />
          <button
            className="button quiet"
            type="button"
            disabled={!pro || !line.trim()}
            title={pro ? "Rewrite this bullet" : "Rewrite is part of Pro"}
            onClick={() => onRewrite(index)}
          >
            Rewrite
          </button>
        </div>
      ))}
      <button className="button quiet" type="button" onClick={() => onChange([...shown, ""])}>
        Add bullet
      </button>
    </div>
  );
}

function EntryList<T>({
  items,
  empty,
  addLabel,
  onChange,
  render,
}: {
  items: T[];
  empty: T;
  addLabel: string;
  onChange: (items: T[]) => void;
  render: (item: T, index: number, update: (patch: Partial<T>) => void) => ReactNode;
}) {
  return (
    <div>
      {items.map((item, index) => (
        <div className="entry" key={index}>
          {render(item, index, (patch) => {
            const next = items.map((current, currentIndex) =>
              currentIndex === index ? { ...current, ...patch } : current,
            );
            onChange(next);
          })}
          <button
            className="button quiet"
            type="button"
            onClick={() => onChange(items.filter((_, current) => current !== index))}
          >
            Remove
          </button>
        </div>
      ))}
      <button className="button" type="button" onClick={() => onChange([...items, empty])}>
        {addLabel}
      </button>
    </div>
  );
}
