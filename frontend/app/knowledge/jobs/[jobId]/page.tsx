"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { UploadCloudIcon } from "lucide-react";

type JobStatus = {
  id: number;
  status: string;
  progress_pct: number;
  message?: string | null;
  files?: { id: number; category: string; filename: string; storage_path: string; bytes?: number | null }[];
};

export default function KnowledgeJobPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = useMemo(() => {
    const n = Number(params?.jobId);
    return Number.isFinite(n) ? n : null;
  }, [params]);

  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;

    let cancelled = false;
    let timeout: any = null;

    const poll = async () => {
      try {
        const res = await fetch(`http://localhost:8000/knowledge/jobs/${jobId}`, { cache: "no-store" });
        const json = await res.json();
        if (!res.ok) throw new Error(json?.detail ?? json?.error ?? `Failed (${res.status})`);

        if (!cancelled) {
          setJob({
            id: Number(json?.id ?? jobId),
            status: String(json?.status ?? "unknown"),
            progress_pct: Number(json?.progress_pct ?? 0),
            message: json?.message ?? null,
            files: Array.isArray(json?.files) ? json.files : [],
          });
          setError(null);
        }

        const status = String(json?.status ?? "unknown");
        if (status !== "completed" && status !== "failed") {
          timeout = setTimeout(poll, 1500);
        }
      } catch (e: any) {
        if (!cancelled) {
          setError(e?.message ?? "Failed to load job");
        }
        timeout = setTimeout(poll, 2000);
      }
    };

    poll();

    return () => {
      cancelled = true;
      if (timeout) clearTimeout(timeout);
    };
  }, [jobId]);

  return (
    <main className="min-h-screen bg-gradient-to-b from-red-50 via-white to-slate-50 text-slate-900">
      <header className="sticky top-0 z-10 border-b border-red-200/70 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="grid size-8 place-items-center rounded-xl bg-[#C74634]/10 text-[#C74634] ring-1 ring-[#C74634]/20">
              <UploadCloudIcon className="size-4" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-900">RAG Job Status</div>
              <div className="text-xs text-slate-500">Batch job progress</div>
            </div>
          </div>

          <a
            href="/knowledge"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 shadow-sm hover:bg-slate-50"
          >
            Upload more
          </a>
        </div>
      </header>

      <div className="mx-auto w-full max-w-5xl px-4 py-6">
        <div className="rounded-3xl border border-red-200/70 bg-white shadow-sm">
          <div className="border-b border-red-200/70 px-5 py-4">
            <div className="text-sm font-semibold text-slate-900">Batch #{jobId ?? "?"}</div>
            <div className="mt-1 text-xs text-slate-500">Polling backend status endpoint</div>
          </div>

          <div className="p-5">
            {error ? (
              <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{error}</div>
            ) : null}

            {job ? (
              <div className="rounded-2xl border border-slate-200 bg-white p-4">
                <div className="flex items-center justify-between text-sm text-slate-900">
                  <span className="font-semibold">{job.status}</span>
                  <span className="text-xs text-slate-600">{Math.min(100, Math.max(0, job.progress_pct))}%</span>
                </div>

                {job.message ? (
                  <div className="mt-2 text-xs text-slate-600">{job.message}</div>
                ) : null}

                <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full bg-[#C74634]"
                    style={{ width: `${Math.min(100, Math.max(0, job.progress_pct))}%` }}
                  />
                </div>

                {job.files && job.files.length > 0 ? (
                  <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <div className="text-xs font-semibold text-slate-700">Files in this batch</div>
                    <ul className="mt-2 space-y-1 text-xs text-slate-700">
                      {job.files.map((f) => (
                        <li key={f.id} className="truncate">
                          {f.filename}
                          <span className="ml-2 text-slate-500">({f.storage_path})</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="text-xs text-slate-500">Loading…</div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
