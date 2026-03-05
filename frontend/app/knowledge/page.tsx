"use client";

import { useCallback, useState } from "react";
import { FileUpIcon, UploadCloudIcon } from "lucide-react";

export default function KnowledgePage() {
  const [files, setFiles] = useState<File[]>([]);

  const onPickFiles = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const picked = Array.from(e.target.files ?? []).filter(
        (f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf")
      );
      setFiles(picked);
    },
    []
  );

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
                  Upload is not wired to the backend yet.
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
