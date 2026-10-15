export type Plan = "free" | "pro";

export type User = {
  id: string;
  email: string;
  plan: Plan;
};

export type Contact = {
  name: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  website: string;
  linkedin: string;
  github: string;
};

export type Experience = {
  company: string;
  position: string;
  location: string;
  start_date: string;
  end_date: string;
  highlights: string[];
};

export type Education = {
  institution: string;
  degree: string;
  area: string;
  location: string;
  start_date: string;
  end_date: string;
  highlights: string[];
};

export type Skill = {
  label: string;
  details: string;
};

export type Project = {
  name: string;
  url: string;
  location: string;
  start_date: string;
  end_date: string;
  summary: string;
  highlights: string[];
};

export type ResumeContent = {
  contact: Contact;
  summary: string;
  experience: Experience[];
  education: Education[];
  skills: Skill[];
  projects: Project[];
};

export type Version = {
  id: string;
  resume_id: string;
  label: string;
  template: string;
  content: ResumeContent;
  created_at: string;
};

export type ResumeDetail = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  versions: Version[];
};

export type ResumeSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  version_count: number;
};

export type TemplateInfo = {
  id: string;
  label: string;
  pro: boolean;
  blurb: string;
};

export type BillingInfo = {
  plan: Plan;
  price_label: string;
  resume_limit: number;
  version_limit: number;
  checkout_available: boolean;
  missing: string[];
};

export const PRICE_LABEL = "$2.99/month";

export function emptyContent(): ResumeContent {
  return {
    contact: {
      name: "",
      headline: "",
      email: "",
      phone: "",
      location: "",
      website: "",
      linkedin: "",
      github: "",
    },
    summary: "",
    experience: [],
    education: [],
    skills: [],
    projects: [],
  };
}
