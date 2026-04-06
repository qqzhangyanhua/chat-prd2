export interface AssistantReplyVersionItem {
  assistantVersionId: string;
  content: string;
  createdAt?: string;
  isLatest: boolean;
  versionNo: number;
}

interface AssistantVersionHistoryDialogProps {
  onSelectVersion: (versionId: string) => void;
  open: boolean;
  onClose: () => void;
  selectedVersionId: string | null;
  versions: AssistantReplyVersionItem[];
}

export function AssistantVersionHistoryDialog({
  onSelectVersion,
  open,
  onClose,
  selectedVersionId,
  versions,
}: AssistantVersionHistoryDialogProps) {
  if (!open) {
    return null;
  }

  const orderedVersions = [...versions].sort((a, b) => b.versionNo - a.versionNo);
  const selectedVersion =
    orderedVersions.find((version) => version.assistantVersionId === selectedVersionId) ??
    orderedVersions.find((version) => version.isLatest) ??
    orderedVersions[0] ??
    null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/45 p-4">
      <div
        aria-labelledby="assistant-version-history-title"
        className="max-h-[80vh] w-full max-w-2xl overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-2xl"
        role="dialog"
      >
        <div className="flex items-center justify-between border-b border-stone-100 px-5 py-4">
          <div>
            <h3
              className="text-base font-semibold text-stone-900"
              id="assistant-version-history-title"
            >
              重新生成历史
            </h3>
            <p className="mt-1 text-xs text-stone-500">历史版本仅供查看，不会改变当前对话基线。</p>
          </div>
          <button
            className="rounded-lg border border-stone-200 px-3 py-1.5 text-xs font-medium text-stone-600 hover:border-stone-300 hover:text-stone-900"
            onClick={onClose}
            type="button"
          >
            关闭历史
          </button>
        </div>

        <div className="grid max-h-[60vh] gap-4 overflow-y-auto p-4 md:grid-cols-[220px_minmax(0,1fr)]">
          {orderedVersions.length === 0 ? (
            <p className="rounded-xl border border-stone-100 bg-stone-50 p-3 text-sm text-stone-500 md:col-span-2">
              暂无历史版本
            </p>
          ) : (
            <>
              <div className="space-y-2">
                {orderedVersions.map((version) => {
                  const isSelected =
                    version.assistantVersionId === selectedVersion?.assistantVersionId;

                  return (
                    <button
                      aria-label={`查看版本 ${version.versionNo}`}
                      aria-pressed={isSelected}
                      className={`w-full rounded-xl border px-3 py-3 text-left transition-colors ${
                        isSelected
                          ? "border-stone-900 bg-stone-950 text-white"
                          : "border-stone-200 bg-stone-50 text-stone-700 hover:border-stone-300"
                      }`}
                      key={version.assistantVersionId}
                      onClick={() => onSelectVersion(version.assistantVersionId)}
                      type="button"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-semibold">版本 {version.versionNo}</span>
                        {version.isLatest ? (
                          <span
                            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                              isSelected
                                ? "bg-white/15 text-white"
                                : "bg-amber-100 text-amber-700"
                            }`}
                          >
                            当前版本
                          </span>
                        ) : null}
                      </div>
                      <div
                        className={`mt-1 text-[11px] ${
                          isSelected ? "text-stone-300" : "text-stone-500"
                        }`}
                      >
                        {version.createdAt ?? "等待时间戳"}
                      </div>
                    </button>
                  );
                })}
              </div>
              <article className="rounded-2xl border border-stone-200 bg-white p-4">
                {selectedVersion ? (
                  <>
                    <div className="flex items-center justify-between gap-2 border-b border-stone-100 pb-3">
                      <div>
                        <p className="text-sm font-semibold text-stone-900">
                          版本 {selectedVersion.versionNo}
                        </p>
                        <p className="mt-1 text-xs text-stone-500">
                          {selectedVersion.createdAt ?? "暂无生成时间"}
                        </p>
                      </div>
                      {selectedVersion.isLatest ? (
                        <span className="rounded-full bg-amber-100 px-2.5 py-1 text-[11px] font-semibold text-amber-700">
                          当前版本
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-stone-700">
                      {selectedVersion.content}
                    </p>
                  </>
                ) : null}
              </article>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
