import { useEffect, useState } from "react";
import {
  Bot,
  Brain,
  FileStack,
  FolderOpen,
  Loader2,
  MessageSquareText,
  ShieldCheck,
  Trash2,
  UploadCloud,
  User
} from "lucide-react";
import ClaudeChatInput, { AttachedFile } from "./components/ui/claude-style-chat-input";

type ChatEntry = {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: string;
};

type SendPayload = {
  message: string;
  files: AttachedFile[];
  pastedContent: { id: string; content: string; timestamp: Date }[];
  model: string;
  isThinkingEnabled: boolean;
};

type View = "chat" | "library" | "overview";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";
const APP_NAME = "INVINCIBLE";

const starterPrompts = [
  "Summarize my uploaded report in simple language",
  "Create viva questions from these notes",
  "Explain the methodology step by step",
  "Turn this document into revision flashcards"
];

const navigationItems: { id: View; label: string; icon: typeof MessageSquareText }[] = [
  { id: "chat", label: "Study Chat", icon: MessageSquareText },
  { id: "library", label: "Library", icon: FolderOpen },
  { id: "overview", label: "Overview", icon: Brain }
];

function INVINCIBLELogo({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="6" y="6" width="52" height="52" rx="18" fill="#D36A43" />
      <path
        d="M20 41V24.8C20 22.7013 21.7013 21 23.8 21H24.448C25.6408 21 26.7614 21.5618 27.472 22.516L36.528 34.684C37.2386 35.6382 38.3592 36.2 39.552 36.2H40.2C42.2987 36.2 44 34.4987 44 32.4V23"
        stroke="white"
        strokeWidth="4.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M20 28L20 40.2C20 42.2987 21.7013 44 23.8 44H40.2C42.2987 44 44 42.2987 44 40.2V36" stroke="#F8D8CB" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}

function App() {
  const [activeView, setActiveView] = useState<View>("chat");
  const [messages, setMessages] = useState<ChatEntry[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Upload your notes, slides, and reports, then ask for summaries, quizzes, viva practice, or step-by-step explanations.",
      meta: `${APP_NAME} assistant`
    }
  ]);
  const [sessionId] = useState(() => crypto.randomUUID());
  const [documents, setDocuments] = useState<string[]>([]);
  const [statsData, setStatsData] = useState({ total_chunks: 0, total_files: 0, total_feedback: 0, total_sessions: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshSidebarData = async () => {
    const [filesRes, statsRes] = await Promise.all([fetch(`${API_BASE}/files`), fetch(`${API_BASE}/stats`)]);

    if (filesRes.ok) {
      const filesJson = await filesRes.json();
      setDocuments(filesJson.files ?? []);
    }

    if (statsRes.ok) {
      const statsJson = await statsRes.json();
      setStatsData(statsJson);
    }
  };

  useEffect(() => {
    refreshSidebarData().catch((err) => {
      setError(err instanceof Error ? err.message : "Failed to connect to API.");
    });
  }, []);

  const handleDeleteFile = async (filename: string) => {
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/files/${encodeURIComponent(filename)}`, {
        method: "DELETE"
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Failed to delete file.");
      }

      await refreshSidebarData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete file.");
    }
  };

  const handleSendMessage = async (data: SendPayload) => {
    const userMessage = data.message.trim() || "Analyze the attached study materials.";

    setError(null);
    setLoading(true);
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "user", content: userMessage }]);

    try {
      if (data.files.length > 0) {
        const formData = new FormData();
        data.files.forEach((file) => formData.append("files", file.file));

        const uploadResponse = await fetch(`${API_BASE}/upload`, {
          method: "POST",
          body: formData
        });
        const uploadJson = await uploadResponse.json();

        if (!uploadResponse.ok) {
          throw new Error(uploadJson.detail || "Upload failed.");
        }

        const failed = (uploadJson.results || []).filter((item: { status: string }) => item.status === "error");
        if (failed.length > 0) {
          throw new Error(failed[0].error || "One or more files failed to ingest.");
        }

        await refreshSidebarData();
        setActiveView("chat");
      }

      const chatResponse = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: userMessage,
          session_id: sessionId
        })
      });
      const chatJson = await chatResponse.json();

      if (!chatResponse.ok) {
        throw new Error(chatJson.detail || "Chat request failed.");
      }

      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: chatJson.answer,
          meta: chatJson.model
        }
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `Something went wrong: ${message}`,
          meta: "API error"
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const renderChatView = () => (
    <section className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_360px]">
      <div className="rounded-[32px] border border-white/70 bg-white/88 p-5 shadow-[0_24px_80px_rgba(25,33,52,0.08)] backdrop-blur md:p-7">
        <div className="mb-6 flex flex-col gap-4 border-b border-[#ebe6dd] pb-5 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#7d7366]">Study Chat</p>
            <h1 className="mt-2 max-w-2xl font-serif text-4xl font-semibold tracking-tight text-[#1d2433] md:text-5xl">
              Study with your own notes, without the clutter
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-8 text-[#5f6470]">
              A quieter workspace for summaries, revision questions, viva prep, and clear explanations from your uploaded material.
            </p>
          </div>
          <div className="rounded-[24px] border border-[#e8ddcf] bg-[#f8f1e6] px-4 py-3">
            <p className="text-xs uppercase tracking-[0.2em] text-[#8e7d67]">Library</p>
            <p className="mt-1 text-sm font-semibold text-[#2c3240]">
              {statsData.total_files} files · {statsData.total_chunks} chunks
            </p>
          </div>
        </div>

        <div className="mb-5 flex flex-wrap gap-3">
          {starterPrompts.map((prompt) => (
            <button
              key={prompt}
              onClick={() => handleSendMessage({ message: prompt, files: [], pastedContent: [], model: "invincible-balanced", isThinkingEnabled: false })}
              className="rounded-full border border-[#e8ddcf] bg-[#fffaf4] px-4 py-2 text-sm font-medium text-[#414655] transition hover:-translate-y-0.5 hover:border-[#d9c3ac] hover:bg-[#f8efe4]"
            >
              {prompt}
            </button>
          ))}
        </div>

        {error && <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        <div className="mb-6 max-h-[560px] space-y-4 overflow-y-auto rounded-[28px] border border-[#efe8dc] bg-[#fbf8f2] p-4 md:p-5">
          {messages.map((message) => (
            <div key={message.id} className={`flex items-end gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}>
              {message.role === "assistant" && (
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[#d86f4d] text-white shadow-[0_12px_30px_rgba(216,111,77,0.25)]">
                  <Bot className="h-5 w-5" />
                </div>
              )}

              <div
                className={`max-w-[85%] rounded-[24px] px-5 py-4 ${
                  message.role === "user" ? "bg-[#222c3d] text-white" : "border border-[#eadfce] bg-white text-[#1f2532]"
                }`}
              >
                <p className="whitespace-pre-wrap text-[15px] leading-7">{message.content}</p>
                {message.meta && (
                  <p className={`mt-3 text-[11px] uppercase tracking-[0.2em] ${message.role === "user" ? "text-white/60" : "text-[#908575]"}`}>
                    {message.meta}
                  </p>
                )}
              </div>

              {message.role === "user" && (
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[#dce7f7] text-[#33517f]">
                  <User className="h-5 w-5" />
                </div>
              )}
            </div>
          ))}
        </div>

        <ClaudeChatInput onSendMessage={handleSendMessage} />

        {loading && (
          <div className="mt-4 flex items-center justify-center gap-2 text-sm text-[#6c7280]">
            <Loader2 className="h-4 w-4 animate-spin" />
            Working on your request...
          </div>
        )}
      </div>

      <aside className="space-y-4">
        <section className="rounded-[28px] border border-[#1f2633]/10 bg-[#1f2633] p-6 text-white shadow-[0_24px_80px_rgba(21,28,41,0.24)]">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-white/10 p-3 text-[#ffb691]">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-xl font-semibold">Focused workflow</h2>
              <p className="text-sm text-white/65">A calmer layout for real study sessions</p>
            </div>
          </div>

          <div className="mt-5 space-y-3 text-sm leading-7 text-white/78">
            <p>Keep chat as the main task, documents in their own area, and extra details out of the way.</p>
            <p>Use this page for asking questions, uploading files, and continuing one revision session.</p>
          </div>
        </section>

        <section className="rounded-[28px] border border-[#eadfce] bg-[#fffaf4] p-6 shadow-[0_18px_50px_rgba(41,35,29,0.06)]">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-[#f5e6d2] p-3 text-[#ba633f]">
              <UploadCloud className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[#8c7b66]">Quick tips</p>
              <h3 className="mt-1 text-xl font-semibold text-[#202632]">Best results</h3>
            </div>
          </div>

          <div className="mt-5 space-y-3 text-sm leading-7 text-[#5c6470]">
            <p>Upload one unit or chapter at a time for sharper retrieval.</p>
            <p>Ask for summaries, quizzes, viva prep, or difficult concepts in simpler language.</p>
            <p>Delete old files from the library page to keep your workspace tidy.</p>
          </div>
        </section>
      </aside>
    </section>
  );

  const renderLibraryView = () => (
    <section className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_320px]">
      <div className="rounded-[32px] border border-white/70 bg-white/88 p-6 shadow-[0_24px_80px_rgba(25,33,52,0.08)] backdrop-blur md:p-7">
        <div className="mb-6 flex items-center justify-between gap-4 border-b border-[#ebe6dd] pb-5">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#7d7366]">Library</p>
            <h2 className="mt-2 font-serif text-4xl font-semibold tracking-tight text-[#1d2433]">Your uploaded material</h2>
          </div>
          <div className="rounded-[24px] border border-[#e8ddcf] bg-[#f8f1e6] px-4 py-3 text-right">
            <p className="text-xs uppercase tracking-[0.2em] text-[#8e7d67]">Feedback saved</p>
            <p className="mt-1 text-sm font-semibold text-[#2c3240]">{statsData.total_feedback}</p>
          </div>
        </div>

        {documents.length === 0 ? (
          <div className="rounded-[28px] border border-dashed border-[#d9cebf] bg-[#fbf8f2] px-6 py-14 text-center">
            <FileStack className="mx-auto h-10 w-10 text-[#b59b82]" />
            <h3 className="mt-4 text-xl font-semibold text-[#283040]">No files yet</h3>
            <p className="mx-auto mt-2 max-w-md text-sm leading-7 text-[#69707d]">
              Go to Study Chat and upload notes, reports, slides, or datasets to start building your library.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {documents.map((document, index) => (
              <div
                key={document}
                className="flex flex-col gap-4 rounded-[26px] border border-[#eee4d5] bg-[#fcfaf6] px-5 py-5 md:flex-row md:items-center md:justify-between"
              >
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#9a8c79]">Document {index + 1}</p>
                  <p className="mt-2 truncate text-lg font-semibold text-[#212835]">{document}</p>
                </div>

                <button
                  onClick={() => handleDeleteFile(document)}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[#e4d5c3] bg-white px-4 py-3 text-sm font-medium text-[#6a4331] transition hover:border-[#d5b79c] hover:bg-[#fbf1e7]"
                >
                  <Trash2 className="h-4 w-4" />
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <aside className="space-y-4">
        <section className="rounded-[28px] border border-[#eadfce] bg-[#fffaf4] p-6 shadow-[0_18px_50px_rgba(41,35,29,0.06)]">
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[#8c7b66]">Workspace stats</p>
          <div className="mt-5 space-y-4">
            <div className="rounded-2xl bg-white px-4 py-4">
              <p className="text-sm text-[#7f7264]">Files</p>
              <p className="mt-1 text-2xl font-semibold text-[#202632]">{statsData.total_files}</p>
            </div>
            <div className="rounded-2xl bg-white px-4 py-4">
              <p className="text-sm text-[#7f7264]">Chunks</p>
              <p className="mt-1 text-2xl font-semibold text-[#202632]">{statsData.total_chunks}</p>
            </div>
            <div className="rounded-2xl bg-white px-4 py-4">
              <p className="text-sm text-[#7f7264]">Corrections</p>
              <p className="mt-1 text-2xl font-semibold text-[#202632]">{statsData.total_feedback}</p>
            </div>
          </div>
        </section>
      </aside>
    </section>
  );

  const renderOverviewView = () => (
    <section className="grid gap-6 lg:grid-cols-3">
      <div className="rounded-[30px] border border-white/70 bg-white/88 p-6 shadow-[0_20px_70px_rgba(25,33,52,0.08)] backdrop-blur">
        <div className="rounded-2xl bg-[#f4ecdf] p-3 text-[#c56b47] w-fit">
          <MessageSquareText className="h-5 w-5" />
        </div>
        <h3 className="mt-5 text-2xl font-semibold text-[#1f2532]">Chat-first layout</h3>
        <p className="mt-3 text-sm leading-7 text-[#606775]">
          The homepage now prioritizes conversation and hides supporting information in cleaner side panels.
        </p>
      </div>

      <div className="rounded-[30px] border border-white/70 bg-white/88 p-6 shadow-[0_20px_70px_rgba(25,33,52,0.08)] backdrop-blur">
        <div className="rounded-2xl bg-[#e5edf8] p-3 text-[#456793] w-fit">
          <FolderOpen className="h-5 w-5" />
        </div>
        <h3 className="mt-5 text-2xl font-semibold text-[#1f2532]">Separate library page</h3>
        <p className="mt-3 text-sm leading-7 text-[#606775]">
          Uploaded files now have their own place, which makes the workspace feel more organized and easier to scan.
        </p>
      </div>

      <div className="rounded-[30px] border border-white/70 bg-white/88 p-6 shadow-[0_20px_70px_rgba(25,33,52,0.08)] backdrop-blur">
        <div className="rounded-2xl bg-[#1f2633] p-3 text-[#ffb691] w-fit">
          <INVINCIBLELogo className="h-5 w-5" />
        </div>
        <h3 className="mt-5 text-2xl font-semibold text-[#1f2532]">More product feel</h3>
        <p className="mt-3 text-sm leading-7 text-[#606775]">
          The visual system is calmer, more deliberate, and closer to a real student workspace than a landing-page mockup.
        </p>
      </div>
    </section>
  );

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f8f4ed_0%,#f3eee6_100%)] text-[#1f2532]">
      <div className="mx-auto max-w-[1500px] px-4 py-5 md:px-8 md:py-7">
        <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="rounded-[32px] border border-[#e6ddd0] bg-[#fdfbf7] p-5 text-[#20242c] shadow-[0_18px_60px_rgba(32,36,44,0.06)]">
            <div className="border-b border-[#ece2d5] pb-5">
              <div className="flex items-center gap-3">
                <div className="flex h-13 w-13 items-center justify-center rounded-2xl bg-[#fff3ee] text-white">
                  <INVINCIBLELogo className="h-11 w-11" />
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[#9a8f80]">New name</p>
                  <h1 className="mt-1 text-2xl font-semibold">{APP_NAME}</h1>
                </div>
              </div>
              <p className="mt-4 text-sm leading-7 text-[#68707c]">
                Your notes, your uploads, your revision flow. Clean, simple, and less dashboard-y.
              </p>
            </div>

            <nav className="mt-5 space-y-2">
              {navigationItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeView === item.id;

                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveView(item.id)}
                    className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left transition ${
                      isActive ? "bg-[#20242c] text-white" : "bg-[#f5efe5] text-[#555d69] hover:bg-[#efe6d9] hover:text-[#20242c]"
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                    <span className="font-medium">{item.label}</span>
                  </button>
                );
              })}
            </nav>

            <div className="mt-6 space-y-3">
              <div className="rounded-[24px] border border-[#ece1d2] bg-[#f7f1e8] p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-[#958774]">Files</p>
                <p className="mt-2 text-3xl font-semibold">{statsData.total_files}</p>
              </div>
              <div className="rounded-[24px] border border-[#ece1d2] bg-[#f7f1e8] p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-[#958774]">Chunks</p>
                <p className="mt-2 text-3xl font-semibold">{statsData.total_chunks}</p>
              </div>
            </div>
          </aside>

          <main className="space-y-6">
            {activeView === "chat" && renderChatView()}
            {activeView === "library" && renderLibraryView()}
            {activeView === "overview" && renderOverviewView()}
          </main>
        </div>
      </div>
    </div>
  );
}

export default App;
