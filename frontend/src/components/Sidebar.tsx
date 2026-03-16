import { useState } from 'react'
import type { IndexedDocument, Stats } from '../types'

interface Props {
  stats: Stats | null
  documents: IndexedDocument[]
  isIndexing: boolean
  onIndexFolder: (path: string) => void
}

const EXT_COLOR: Record<string, string> = {
  pdf:  '#f87171',
  docx: '#60a5fa',
  md:   '#a78bfa',
  txt:  '#94a3b8',
  csv:  '#4ade80',
  html: '#fb923c',
}

export function Sidebar({ stats, documents, isIndexing, onIndexFolder }: Props) {
  const [folderInput, setFolderInput] = useState('')
  const [showInput, setShowInput] = useState(false)

  const handleIndex = () => {
    if (!folderInput.trim()) return
    onIndexFolder(folderInput.trim())
    setFolderInput('')
    setShowInput(false)
  }

  return (
    <aside
      className="flex flex-col w-64 shrink-0 border-r overflow-hidden"
      style={{ background: '#0d1117', borderColor: '#2a3244' }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b" style={{ borderColor: '#2a3244' }}>
        <svg className="w-6 h-6 text-blue-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
          <line x1="11" y1="8" x2="11" y2="14" />
          <line x1="8" y1="11" x2="14" y2="11" />
        </svg>
        <span className="font-bold text-slate-100 tracking-tight">DeepLens</span>
      </div>

      {/* Stats */}
      <div className="px-4 py-3 border-b" style={{ borderColor: '#2a3244' }}>
        <p className="text-xs text-slate-600 uppercase tracking-wider mb-2">Index</p>
        {stats ? (
          <div className="grid grid-cols-2 gap-2">
            <StatPill label="Documents" value={stats.documents} />
            <StatPill label="Chunks" value={stats.chunks} />
          </div>
        ) : (
          <p className="text-xs text-slate-600">Loading…</p>
        )}
      </div>

      {/* Index folder section */}
      <div className="px-4 py-3 border-b" style={{ borderColor: '#2a3244' }}>
        {showInput ? (
          <div className="space-y-2">
            <input
              autoFocus
              type="text"
              value={folderInput}
              onChange={e => setFolderInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleIndex()}
              placeholder="/path/to/folder"
              className="w-full text-xs px-2.5 py-1.5 rounded-lg outline-none text-slate-200 placeholder-slate-600"
              style={{ background: '#1e2535', border: '1px solid #2a3244' }}
            />
            <div className="flex gap-1.5">
              <button
                onClick={handleIndex}
                disabled={isIndexing || !folderInput.trim()}
                className="flex-1 text-xs py-1 rounded-lg font-medium transition-colors disabled:opacity-40"
                style={{ background: '#4f8ef7', color: 'white' }}
              >
                {isIndexing ? 'Indexing…' : 'Index'}
              </button>
              <button
                onClick={() => setShowInput(false)}
                className="text-xs px-2 py-1 rounded-lg"
                style={{ background: '#1e2535', color: '#64748b' }}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowInput(true)}
            disabled={isIndexing}
            className="w-full flex items-center justify-center gap-1.5 text-xs py-1.5 rounded-lg font-medium transition-colors disabled:opacity-40"
            style={{ background: '#1e2535', color: '#94a3b8', border: '1px solid #2a3244' }}
          >
            {isIndexing ? (
              <>
                <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
                </svg>
                Indexing…
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                  <line x1="12" y1="11" x2="12" y2="17" />
                  <line x1="9" y1="14" x2="15" y2="14" />
                </svg>
                Index Folder
              </>
            )}
          </button>
        )}
      </div>

      {/* Document list */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        <p className="text-xs text-slate-600 uppercase tracking-wider mb-2">
          Indexed files {documents.length > 0 && `(${documents.length})`}
        </p>
        {documents.length === 0 ? (
          <p className="text-xs text-slate-700 leading-relaxed">
            No documents indexed yet. Use "Index Folder" to get started.
          </p>
        ) : (
          <ul className="space-y-1">
            {documents.map(doc => (
              <li key={doc.document_id}>
                <div
                  className="flex items-center gap-2 px-2 py-1.5 rounded-lg"
                  style={{ background: '#161b27' }}
                >
                  <span
                    className="shrink-0 text-xs font-bold px-1 rounded"
                    style={{
                      background: '#1e2535',
                      color: EXT_COLOR[doc.file_type] ?? '#94a3b8',
                    }}
                  >
                    {doc.file_type.toUpperCase()}
                  </span>
                  <span
                    className="text-xs text-slate-300 truncate"
                    title={doc.file_path}
                  >
                    {doc.filename}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  )
}

function StatPill({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg p-2 text-center" style={{ background: '#161b27' }}>
      <p className="text-base font-bold text-slate-200">{value.toLocaleString()}</p>
      <p className="text-xs text-slate-600">{label}</p>
    </div>
  )
}
