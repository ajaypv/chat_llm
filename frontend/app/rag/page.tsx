"use client";

import Link from "next/link";

export default function RagHowItWorksPage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-red-50 via-white to-slate-50 text-slate-900">
      <header className="sticky top-0 z-10 border-b border-red-200/70 bg-white/80 backdrop-blur">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-4 py-3">
          <h1 className="text-sm font-semibold">How this project works</h1>
          <Link
            href="/"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 shadow-sm hover:bg-slate-50"
          >
            Back to Chat
          </Link>
        </div>
      </header>

      <section className="mx-auto w-full max-w-5xl px-4 py-8 space-y-6">
        <div className="relative overflow-hidden rounded-3xl border border-red-200/70 bg-white/80 p-6 shadow-lg shadow-black/5 backdrop-blur">
          <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-transparent via-[#C74634]/60 to-transparent animate-pulse" />
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(199,70,52,0.14),transparent_55%)]" />
          <div className="pointer-events-none absolute -right-10 -top-10 size-40 rounded-full bg-[#C74634]/10 blur-2xl animate-pulse" />
          <div className="relative">
            <p className="inline-flex rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs font-semibold text-[#C74634] animate-pulse">
              System Overview
            </p>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">
              One assistant, multiple intelligent pipelines
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-700 sm:text-base">
              This project combines conversational AI, document retrieval (RAG), and database querying into a single chat experience. 
              It chooses the best path based on what the user asks, then streams results with tool visibility.
            </p>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-md">
            <h3 className="text-sm font-semibold text-slate-900">Frontend (Next.js)</h3>
            <p className="mt-2 text-sm text-slate-700">Modern chat UI, streaming responses, tool blocks, source display, knowledge upload, and category selection.</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-md">
            <h3 className="text-sm font-semibold text-slate-900">Backend (FastAPI)</h3>
            <p className="mt-2 text-sm text-slate-700">Routes each request, orchestrates model calls, retrieval, and SQL tools, then returns incremental updates to the UI.</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-md">
            <h3 className="text-sm font-semibold text-slate-900">RAG Knowledge Pipeline</h3>
            <p className="mt-2 text-sm text-slate-700">PDFs are uploaded, chunked, embedded, and indexed so relevant context can be retrieved for grounded responses.</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-md">
            <h3 className="text-sm font-semibold text-slate-900">NL2SQL Data Path</h3>
            <p className="mt-2 text-sm text-slate-700">For structured queries (like restaurant/menu questions), the app can query the database directly and return precise results.</p>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-base font-semibold">How a request flows</h3>
          <ol className="mt-3 space-y-2 text-sm text-slate-700 list-decimal pl-5">
            <li className="transition-colors hover:text-slate-900">User asks a question in chat.</li>
            <li className="transition-colors hover:text-slate-900">Backend detects intent (general, RAG-heavy, or structured data/NL2SQL).</li>
            <li className="transition-colors hover:text-slate-900">Relevant context or query results are retrieved.</li>
            <li className="transition-colors hover:text-slate-900">Model generates a grounded answer and streams it back.</li>
            <li className="transition-colors hover:text-slate-900">UI shows tool calls/results so users can trust what happened.</li>
          </ol>
        </div>

        <div className="rounded-2xl border border-red-200/70 bg-red-50/70 p-5 text-sm text-slate-700">
          <span className="font-semibold text-slate-900">Why this design works:</span> it keeps the chat natural for users while still giving strong accuracy via retrieval, deterministic DB results, and transparent tool traces.
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900">Key tools in this project</h3>
          <ul className="mt-3 grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
            <li className="rounded-lg bg-slate-50 px-3 py-2 transition-all hover:bg-red-50 hover:border-red-200 border border-transparent"><span className="font-semibold">semantic_search</span> — retrieves relevant document context</li>
            <li className="rounded-lg bg-slate-50 px-3 py-2 transition-all hover:bg-red-50 hover:border-red-200 border border-transparent"><span className="font-semibold">nl2sql_tool</span> — converts natural language into DB queries</li>
            <li className="rounded-lg bg-slate-50 px-3 py-2 transition-all hover:bg-red-50 hover:border-red-200 border border-transparent"><span className="font-semibold">Knowledge upload</span> — adds new PDFs into RAG pipeline</li>
            <li className="rounded-lg bg-slate-50 px-3 py-2 transition-all hover:bg-red-50 hover:border-red-200 border border-transparent"><span className="font-semibold">Streaming UI</span> — shows incremental response + tool states</li>
          </ul>
        </div>
      </section>
    </main>
  );
}
