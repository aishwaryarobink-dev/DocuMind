import React, { useState, useRef, useCallback } from 'react'
import styles from './FilePanel.module.scss'

// ── Icons ─────────────────────────────────────────────────────────────────────
const UploadIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="17 8 12 3 7 8"/>
    <line x1="12" y1="3" x2="12" y2="15"/>
  </svg>
)

const FileIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
  </svg>
)

const TrashIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6l-1 14H6L5 6"/>
    <path d="M10 11v6M14 11v6"/>
    <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
  </svg>
)

const ShieldIcon = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    <polyline points="9 12 11 14 15 10"/>
  </svg>
)

// ── DropZone ──────────────────────────────────────────────────────────────────
function DropZone({ onUpload, uploadProgress }) {
  const [isDragging, setIsDragging] = useState(false)
  const fileRef = useRef()

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) onUpload(file)
  }, [onUpload])

  const handleChange = useCallback((e) => {
    const file = e.target.files[0]
    if (file) {
      onUpload(file)
      e.target.value = ''
    }
  }, [onUpload])

  return (
    <div
      className={`${styles.dropZone} ${isDragging ? styles.dragging : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => fileRef.current?.click()}
      role="button"
      aria-label="Upload PDF file"
    >
      <input
        ref={fileRef}
        type="file"
        accept=".pdf"
        className={styles.hiddenInput}
        onChange={handleChange}
      />

      {uploadProgress ? (
        <div className={styles.uploadState}>
          {uploadProgress.status === 'uploading' && (
            <>
              <div className={styles.spinner} />
              <p className={styles.uploadName}>{uploadProgress.name}</p>
              <p className={styles.uploadSub}>Extracting and indexing...</p>
            </>
          )}
          {uploadProgress.status === 'done' && (
            <>
              <div className={styles.uploadDone}>✓</div>
              <p className={styles.uploadName}>{uploadProgress.name}</p>
              <p className={styles.uploadSub}>Indexed successfully</p>
            </>
          )}
          {uploadProgress.status === 'error' && (
            <>
              <div className={styles.uploadError}>✗</div>
              <p className={styles.uploadName}>{uploadProgress.name}</p>
              <p className={styles.uploadSub}>{uploadProgress.error}</p>
            </>
          )}
        </div>
      ) : (
        <>
          <div className={styles.dropIcon}><UploadIcon /></div>
          <p className={styles.dropTitle}>Drop PDF here</p>
          <p className={styles.dropSub}>or click to browse · max 10MB</p>
        </>
      )}
    </div>
  )
}

// ── DocItem ───────────────────────────────────────────────────────────────────
function DocItem({ doc, onDelete }) {
  const [confirming, setConfirming] = useState(false)

  const handleDelete = () => {
    if (confirming) {
      onDelete(doc.doc_id)
    } else {
      setConfirming(true)
      setTimeout(() => setConfirming(false), 2500)
    }
  }

  return (
    <div className={styles.docItem}>
      <div className={styles.docIcon}><FileIcon /></div>
      <div className={styles.docInfo}>
        <p className={styles.docName} title={doc.name}>{doc.name}</p>
        <p className={styles.docMeta}>{doc.pages} pages · {doc.chunks} chunks</p>
      </div>
      <button
        className={`${styles.docDelete} ${confirming ? styles.confirming : ''}`}
        onClick={handleDelete}
        title={confirming ? 'Click again to confirm' : 'Remove document'}
      >
        {confirming ? '?' : <TrashIcon />}
      </button>
    </div>
  )
}

// ── FilePanel ─────────────────────────────────────────────────────────────────
export default function FilePanel({ documents, uploadProgress, onUpload, onDelete }) {
  return (
    <aside className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>Documents</span>
        {documents.length > 0 && (
          <span className={styles.count}>{documents.length}</span>
        )}
      </div>

      <DropZone onUpload={onUpload} uploadProgress={uploadProgress} />

      <div className={styles.docList}>
        {documents.length === 0 ? (
          <p className={styles.emptyText}>
            No documents yet.<br />Upload a PDF to get started.
          </p>
        ) : (
          documents.map(doc => (
            <DocItem key={doc.doc_id} doc={doc} onDelete={onDelete} />
          ))
        )}
      </div>

      <div className={styles.footer}>
        <div className={styles.footerBadge}>
          <ShieldIcon />
          <span>Files processed locally</span>
        </div>
        <p className={styles.footerSub}>Powered by ChromaDB + Groq</p>
      </div>
    </aside>
  )
}