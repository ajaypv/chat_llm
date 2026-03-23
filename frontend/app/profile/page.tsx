"use client";

import Link from "next/link";
import { GlobeIcon, PlusIcon, TargetIcon, Trash2Icon, UserRoundIcon } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

type SavedLink = {
  id: string;
  label: string;
  url: string;
};

type UserProfileState = {
  goals: string[];
  interests: string[];
  links: SavedLink[];
};

const PROFILE_STORAGE_KEY = "chat.userProfile";

const emptyProfile: UserProfileState = {
  goals: [],
  interests: [],
  links: [],
};

const suggestedGoals = [
  "Track AI product launches",
  "Summarize daily tech news",
  "Monitor startup ecosystem updates",
  "Follow restaurant and food trends",
  "Watch OCI and GenAI announcements",
  "Collect useful web sources for research",
];

const suggestedLinks: Array<{ label: string; url: string }> = [
  {
    label: "TechCrunch",
    url: "https://techcrunch.com/",
  },
  {
    label: "Hacker News",
    url: "https://news.ycombinator.com/",
  },
];

const splitCommaSeparated = (value: string): string[] =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

export default function ProfilePage() {
  const [goalInput, setGoalInput] = useState("");
  const [interestInput, setInterestInput] = useState("");
  const [linkLabel, setLinkLabel] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [profile, setProfile] = useState<UserProfileState>(emptyProfile);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(PROFILE_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<UserProfileState>;
        setProfile({
          goals: Array.isArray(parsed.goals) ? parsed.goals.map(String) : [],
          interests: Array.isArray(parsed.interests) ? parsed.interests.map(String) : [],
          links: Array.isArray(parsed.links)
            ? parsed.links
                .map((item) => ({
                  id: String(item?.id ?? `link-${Date.now()}`),
                  label: String(item?.label ?? "").trim(),
                  url: String(item?.url ?? "").trim(),
                }))
                .filter((item) => item.url)
            : [],
        });
      }
    } catch {
      setProfile(emptyProfile);
    } finally {
      setHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (!hydrated) {
      return;
    }

    try {
      localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile));
    } catch {
      // ignore storage failures in the UI
    }
  }, [hydrated, profile]);

  const addGoals = useCallback(() => {
    const nextGoals = splitCommaSeparated(goalInput);
    if (!nextGoals.length) {
      return;
    }

    setProfile((prev) => ({
      ...prev,
      goals: Array.from(new Set([...prev.goals, ...nextGoals])),
    }));
    setGoalInput("");
  }, [goalInput]);

  const addSuggestedGoal = useCallback((goal: string) => {
    setProfile((prev) => ({
      ...prev,
      goals: prev.goals.includes(goal) ? prev.goals : [...prev.goals, goal],
    }));
  }, []);

  const addInterests = useCallback(() => {
    const nextInterests = splitCommaSeparated(interestInput);
    if (!nextInterests.length) {
      return;
    }

    setProfile((prev) => ({
      ...prev,
      interests: Array.from(new Set([...prev.interests, ...nextInterests])),
    }));
    setInterestInput("");
  }, [interestInput]);

  const addLink = useCallback(() => {
    const trimmedUrl = linkUrl.trim();
    if (!trimmedUrl) {
      return;
    }

    let normalizedUrl = trimmedUrl;
    if (!/^https?:\/\//i.test(normalizedUrl)) {
      normalizedUrl = `https://${normalizedUrl}`;
    }

    try {
      const parsed = new URL(normalizedUrl);
      setProfile((prev) => ({
        ...prev,
        links: [
          ...prev.links,
          {
            id: `link-${Date.now()}`,
            label: linkLabel.trim() || parsed.hostname,
            url: parsed.toString(),
          },
        ],
      }));
      setLinkLabel("");
      setLinkUrl("");
    } catch {
      // ignore invalid URL input
    }
  }, [linkLabel, linkUrl]);

  const addSuggestedLink = useCallback((label: string, url: string) => {
    setProfile((prev) => {
      const alreadyExists = prev.links.some((item) => item.url === url);
      if (alreadyExists) {
        return prev;
      }

      return {
        ...prev,
        links: [
          ...prev.links,
          {
            id: `link-${Date.now()}-${label}`,
            label,
            url,
          },
        ],
      };
    });
  }, []);

  const removeGoal = useCallback((goal: string) => {
    setProfile((prev) => ({
      ...prev,
      goals: prev.goals.filter((item) => item !== goal),
    }));
  }, []);

  const removeInterest = useCallback((interest: string) => {
    setProfile((prev) => ({
      ...prev,
      interests: prev.interests.filter((item) => item !== interest),
    }));
  }, []);

  const removeLink = useCallback((id: string) => {
    setProfile((prev) => ({
      ...prev,
      links: prev.links.filter((item) => item.id !== id),
    }));
  }, []);

  const profileSummary = useMemo(() => {
    return {
      goals: profile.goals.length,
      interests: profile.interests.length,
      links: profile.links.length,
    };
  }, [profile.goals.length, profile.interests.length, profile.links.length]);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(199,70,52,0.16),transparent_28%),linear-gradient(180deg,#fff7f5_0%,#ffffff_42%,#f8fafc_100%)] text-slate-900">
      <header className="sticky top-0 z-10 border-b border-red-200/70 bg-white/80 backdrop-blur">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="grid size-9 place-items-center rounded-2xl bg-[#C74634]/10 text-[#C74634] ring-1 ring-[#C74634]/20">
              <UserRoundIcon className="size-4" />
            </div>
            <div>
              <h1 className="text-sm font-semibold">Profile</h1>
              <p className="text-xs text-slate-500">Save your goals, interests, and preferred web sources locally.</p>
            </div>
          </div>
          <Link
            href="/"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 shadow-sm hover:bg-slate-50"
          >
            Back to Chat
          </Link>
        </div>
      </header>

      <section className="mx-auto grid w-full max-w-5xl gap-6 px-4 py-8 lg:grid-cols-[1.25fr_0.75fr]">
        <div className="space-y-6">
          <div className="relative overflow-hidden rounded-3xl border border-red-200/70 bg-white/90 p-6 shadow-lg shadow-black/5 backdrop-blur">
            <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-transparent via-[#C74634]/70 to-transparent" />
            <p className="inline-flex rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs font-semibold text-[#C74634]">
              Personal context
            </p>
            <h2 className="mt-4 text-2xl font-semibold tracking-tight">Shape how this workspace helps you</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
              Keep a lightweight local profile for what you care about, what you are trying to achieve, and which websites you want to monitor for fresh information.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center gap-2">
                <TargetIcon className="size-4 text-[#C74634]" />
                <h3 className="text-sm font-semibold">Goals</h3>
              </div>
              <p className="mt-2 text-sm text-slate-600">Add short outcomes you want the assistant to help you with.</p>
              <div className="mt-4 flex gap-2">
                <input
                  className="flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-[#C74634] focus:bg-white"
                  onChange={(event) => setGoalInput(event.target.value)}
                  placeholder="Example: Track AI product launches, summarize restaurant reviews"
                  value={goalInput}
                />
                <button
                  className="inline-flex items-center gap-2 rounded-2xl bg-[#C74634] px-4 py-3 text-sm font-semibold text-white hover:bg-[#B33C2D]"
                  onClick={addGoals}
                  type="button"
                >
                  <PlusIcon className="size-4" />
                  Add
                </button>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {profile.goals.map((goal) => (
                  <button
                    className="inline-flex items-center gap-2 rounded-full border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-slate-700 hover:border-red-300 hover:bg-red-100"
                    key={goal}
                    onClick={() => removeGoal(goal)}
                    type="button"
                  >
                    {goal}
                    <Trash2Icon className="size-3.5" />
                  </button>
                ))}
              </div>
              <div className="mt-5 border-t border-slate-100 pt-4">
                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                  Suggestions
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {suggestedGoals.map((goal) => (
                    <button
                      className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:border-[#C74634] hover:text-[#C74634]"
                      key={goal}
                      onClick={() => addSuggestedGoal(goal)}
                      type="button"
                    >
                      {goal}
                    </button>
                  ))}
                </div>
              </div>
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center gap-2">
                <UserRoundIcon className="size-4 text-[#C74634]" />
                <h3 className="text-sm font-semibold">Interests</h3>
              </div>
              <p className="mt-2 text-sm text-slate-600">Store topics you want prioritized in future exploration.</p>
              <div className="mt-4 flex gap-2">
                <input
                  className="flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-[#C74634] focus:bg-white"
                  onChange={(event) => setInterestInput(event.target.value)}
                  placeholder="Example: nutrition, OCI GenAI, local restaurants"
                  value={interestInput}
                />
                <button
                  className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white hover:bg-slate-800"
                  onClick={addInterests}
                  type="button"
                >
                  <PlusIcon className="size-4" />
                  Add
                </button>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {profile.interests.map((interest) => (
                  <button
                    className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 hover:border-slate-300 hover:bg-slate-100"
                    key={interest}
                    onClick={() => removeInterest(interest)}
                    type="button"
                  >
                    {interest}
                    <Trash2Icon className="size-3.5" />
                  </button>
                ))}
              </div>
            </section>
          </div>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <GlobeIcon className="size-4 text-[#C74634]" />
              <h3 className="text-sm font-semibold">Web Sources</h3>
            </div>
            <p className="mt-2 text-sm text-slate-600">
              Save page links you want to revisit for fresh updates later, such as news pages, product blogs, or release notes.
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-[0.9fr_1.1fr_auto]">
              <input
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-[#C74634] focus:bg-white"
                onChange={(event) => setLinkLabel(event.target.value)}
                placeholder="Label, e.g. OpenAI news"
                value={linkLabel}
              />
              <input
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-[#C74634] focus:bg-white"
                onChange={(event) => setLinkUrl(event.target.value)}
                placeholder="https://example.com/news"
                value={linkUrl}
              />
              <button
                className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#C74634] px-4 py-3 text-sm font-semibold text-white hover:bg-[#B33C2D]"
                onClick={addLink}
                type="button"
              >
                <PlusIcon className="size-4" />
                Save link
              </button>
            </div>

            <div className="mt-5 space-y-3">
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-4">
                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                  Suggested links
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {suggestedLinks.map((link) => (
                    <button
                      className="rounded-2xl border border-slate-200 bg-white px-4 py-4 text-left transition hover:border-[#C74634] hover:bg-red-50"
                      key={link.url}
                      onClick={() => addSuggestedLink(link.label, link.url)}
                      type="button"
                    >
                      <div className="text-sm font-semibold text-slate-900">{link.label}</div>
                      <div className="mt-1 truncate text-xs text-slate-500">{link.url}</div>
                    </button>
                  ))}
                </div>
              </div>

              {profile.links.map((link) => (
                <div
                  className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-4 sm:flex-row sm:items-center sm:justify-between"
                  key={link.id}
                >
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-slate-900">{link.label}</div>
                    <a
                      className="mt-1 block truncate text-sm text-[#C74634] hover:underline"
                      href={link.url}
                      rel="noreferrer"
                      target="_blank"
                    >
                      {link.url}
                    </a>
                  </div>
                  <button
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                    onClick={() => removeLink(link.id)}
                    type="button"
                  >
                    <Trash2Icon className="size-3.5" />
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </section>
        </div>

        <aside className="space-y-6">
          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900">Local profile summary</h3>
            <div className="mt-4 grid gap-3">
              <div className="rounded-2xl border border-red-100 bg-red-50 px-4 py-4">
                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[#C74634]">Goals</div>
                <div className="mt-2 text-2xl font-semibold text-slate-900">{profileSummary.goals}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Interests</div>
                <div className="mt-2 text-2xl font-semibold text-slate-900">{profileSummary.interests}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Saved links</div>
                <div className="mt-2 text-2xl font-semibold text-slate-900">{profileSummary.links}</div>
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-slate-900 p-5 text-slate-100 shadow-sm">
            <h3 className="text-sm font-semibold">How this works</h3>
            <ul className="mt-3 space-y-3 text-sm leading-6 text-slate-300">
              <li>Everything on this page is stored in your browser local storage.</li>
              <li>No backend database is needed for goals, interests, or saved links.</li>
              <li>You can later use these saved source links as preferred pages for fresh web lookups.</li>
            </ul>
          </div>
        </aside>
      </section>
    </main>
  );
}