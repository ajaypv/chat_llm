"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { FileUpIcon, UploadCloudIcon } from "lucide-react";

export default function KnowledgePage() {
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const [category, setCategory] = useState<string>("general");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<
    { filename: string; category: string; path: string }[]
  >([]);
  const [jobStatuses, setJobStatuses] = useState<
    Record<number, { status: string; progress_pct: number; message?: string | null }>
  >({});
  const [batchJobId, setBatchJobId] = useState<number | null>(null);

  const onPickFiles = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const picked = Array.from(e.target.files ?? []).filter(
        (f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf")
      );
      setFiles(picked);
      setUploadError(null);
      setUploadSuccess(null);
      setUploadResult([]);
      setUploadProgress(0);
      setJobStatuses({});
      setBatchJobId(null);
    },
    []
  );

  const canUpload = useMemo(() => {
    const cat = category.trim();
    return files.length > 0 && /^[A-Za-z0-9_-]+$/.test(cat) && cat.length <= 64;
  }, [category, files.length]);

  const onUpload = useCallback(async () => {
    setUploadError(null);
    setUploadSuccess(null);
    setUploadResult([]);
    setUploadProgress(0);
    setJobStatuses({});
    setBatchJobId(null);

    const cat = category.trim();
    if (!/^[A-Za-z0-9_-]+$/.test(cat) || cat.length > 64) {
      setUploadError("Category must match A-Z, 0-9, underscore, dash (max 64). ");
      return;
    }
    if (files.length === 0) {
      setUploadError("Please select at least one PDF.");
      return;
    }

    try {
      setIsUploading(true);
      const form = new FormData();
      form.set("category", cat);
      for (const f of files) form.append("files", f);

      const json = await new Promise<any>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "http://localhost:8000/knowledge/upload");

        xhr.upload.onprogress = (evt) => {
          if (!evt.lengthComputable) return;
          const pct = Math.round((evt.loaded / evt.total) * 100);
          setUploadProgress(pct);
        };

        xhr.onerror = () => reject(new Error("Network error"));
        xhr.onload = () => {
          let parsed: any = null;
          try {
            parsed = xhr.responseText ? JSON.parse(xhr.responseText) : null;
          } catch {
            parsed = null;
          }
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(parsed);
          } else {
            const msg = parsed?.detail ?? parsed?.error ?? `Upload failed (${xhr.status})`;
            reject(new Error(msg));
          }
        };

        xhr.send(form);
      });

      const saved = Array.isArray(json?.saved) ? json.saved : [];
      setUploadResult(saved);
      setUploadProgress(100);
      setUploadSuccess(`Uploaded ${saved.length || files.length} file(s) successfully.`);

      const jobId = typeof json?.job_id === "number" ? json.job_id : null;
      setBatchJobId(jobId);
      if (jobId) {
        router.push(`/knowledge/jobs/${jobId}`);
      }
    } catch (err: any) {
      setUploadError(err?.message ?? "Upload failed");
    } finally {
      setIsUploading(false);
    }
  }, [category, files, router]);

  return (
    <main className="min-h-screen bg-gradient-to-b from-red-50 via-white to-slate-50 text-slate-900">
      <header className="sticky top-0 z-10 border-b border-red-200/70 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="grid size-8 place-items-center rounded-xl bg-[#C74634]/10 text-[#C74634] ring-1 ring-[#C74634]/20">
              <UploadCloudIcon className="size-4" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-900">
                Knowledge
              </div>
              <div className="text-xs text-slate-500">
                Upload PDFs to build a knowledge base (UI only for now)
              </div>
            </div>
          </div>

          <a
            href="/"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 shadow-sm hover:bg-slate-50"
          >
            Back to Chat
          </a>
        </div>
      </header>

      <div className="mx-auto w-full max-w-5xl px-4 py-6">
        <div className="rounded-3xl border border-red-200/70 bg-white shadow-sm">
          <div className="border-b border-red-200/70 px-5 py-4">
            <div className="text-sm font-semibold text-slate-900">
              Create knowledge
            </div>
            <div className="mt-1 text-xs text-slate-500">
              Select one or more PDF files to upload.
            </div>
          </div>

          <div className="p-5">
            <label className="group flex cursor-pointer flex-col items-center justify-center gap-3 rounded-3xl border-2 border-dashed border-red-200/70 bg-gradient-to-b from-white to-red-50/40 p-8 text-center transition hover:border-[#C74634]/60 hover:bg-red-50/50">
              <div className="grid size-12 place-items-center rounded-2xl bg-[#C74634]/10 text-[#C74634] ring-1 ring-[#C74634]/20">
                <FileUpIcon className="size-5" />
              </div>

              <div className="space-y-1">
                <div className="text-sm font-semibold text-slate-900">
                  Click to upload PDFs
                </div>
                <div className="text-xs text-slate-600">
                  PDF only • Multiple files supported
                </div>
              </div>

              <input
                accept="application/pdf,.pdf"
                className="hidden"
                multiple
                onChange={onPickFiles}
                type="file"
              />
            </label>

            <div className="mt-5 grid gap-3">
              <div>
                <div className="text-xs font-semibold text-slate-700">
                  Category
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  Stored under backend/knowledge/&lt;category&gt;/. Allowed: A-Z, 0-9, _ and -
                </div>
                <input
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder="general"
                  className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none focus:ring-2 focus:ring-[#C74634]/30"
                />
              </div>

              <button
                type="button"
                onClick={onUpload}
                disabled={!canUpload || isUploading}
                className="inline-flex w-full items-center justify-center rounded-xl bg-[#C74634] px-3 py-2 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isUploading ? `Uploading… ${uploadProgress}%` : "Upload to backend"}
              </button>

              {isUploading ? (
                <div className="rounded-2xl border border-slate-200 bg-white p-3">
                  <div className="flex items-center justify-between text-xs text-slate-600">
                    <span className="font-semibold text-slate-700">Upload progress</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full bg-[#C74634]"
                      style={{ width: `${Math.min(100, Math.max(0, uploadProgress))}%` }}
                    />
                  </div>
                </div>
              ) : null}

              {uploadError ? (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
                  {uploadError}
                </div>
              ) : null}

              {uploadSuccess ? (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-900">
                  {uploadSuccess}
                </div>
              ) : null}

              {uploadResult.length > 0 ? (
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-xs font-semibold text-slate-700">
                    Uploaded
                  </div>
                  <ul className="mt-2 space-y-1 text-sm text-slate-900">
                    {uploadResult.map((r) => (
                      <li key={r.path} className="truncate">
                        {r.filename}
                        <span className="ml-2 text-xs text-slate-500">({r.path})</span>
                      </li>
                    ))}
                  </ul>

                  {batchJobId && Object.keys(jobStatuses).length > 0 ? (
                    <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-3">
                      <div className="text-xs font-semibold text-slate-700">RAG pipeline (batch job)</div>
                      <ul className="mt-2 space-y-2 text-xs text-slate-700">
                        {Object.entries(jobStatuses)
                          .sort((a, b) => Number(a[0]) - Number(b[0]))
                          .map(([id, s]) => (
                            <li key={id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                              <div className="flex items-center justify-between">
                                <span className="font-semibold">Batch #{id}</span>
                                <span>{s.status} • {s.progress_pct}%</span>
                              </div>
                              {s.message ? (
                                <div className="mt-1 text-slate-500">{s.message}</div>
                              ) : null}
                              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                                <div
                                  className="h-full bg-[#C74634]"
                                  style={{ width: `${Math.min(100, Math.max(0, s.progress_pct))}%` }}
                                />
                              </div>
                            </li>
                          ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>

            {files.length > 0 ? (
              <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs font-semibold text-slate-700">
                  Selected files
                </div>
                <ul className="mt-2 space-y-1 text-sm text-slate-900">
                  {files.map((f) => (
                    <li key={`${f.name}-${f.size}`} className="truncate">
                      {f.name}
                      <span className="ml-2 text-xs text-slate-500">
                        ({Math.ceil(f.size / 1024)} KB)
                      </span>
                    </li>
                  ))}
                </ul>

                <div className="mt-4 text-xs text-slate-500">
                  Files will be uploaded to the backend.
                </div>
              </div>
            ) : (
              <div className="mt-4 text-xs text-slate-500">
                No PDFs selected.
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
