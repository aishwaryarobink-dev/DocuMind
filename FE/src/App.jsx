import React, { useRef, useEffect, useState } from 'react'
import { useDocuMind }   from './hooks/useDocuMind.js'
import FilePanel         from './components/FilePanel.jsx'
import MessageBubble     from './components/MessageBubble.jsx'
import ChatInput         from './components/ChatInput.jsx'
import EmptyState        from './components/EmptyState.jsx'
import styles            from './App.module.scss'

// ── Icons ─────────────────────────────────────────────────────────────────────
const MenuIcon  = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <line x1="3" y1="6"  x2="21" y2="6"/>
    <line x1="3" y1="12" x2="21" y2="12"/>
    <line x1="3" y1="18" x2="21" y2="18"/>
  </svg>
)
const TrashIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6l-1 14H6L5 6"/>
    <path d="M10 11v6M14 11v6"/>
  </svg>
)

export default function App() {
  const {
    documents, messages, input, setInput,
    isStreaming, uploadProgress,
    uploadPdf, deleteDoc, sendMessage, clearChat,
  } = useDocuMind()

  const [panelOpen,   setPanelOpen]   = useState(false)
  const bottomRef   = useRef()
  const hasMessages = messages.length > 0

  // Auto-scroll to bottom when messages update
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])

  // Close panel on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') setPanelOpen(false) }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const handleSuggest = (text) => {
    setInput(text)
  }

  return (
    <div className={styles.root}>

      {/* ── Topbar ────────────────────────────────────────────────────────── */}
      <header className={styles.topbar}>
        <div className={styles.topLeft}>
          <button
            className={styles.menuBtn}
            onClick={() => setPanelOpen(o => !o)}
            aria-label="Toggle file panel"
          >
            <MenuIcon />
          </button>
          <div className={styles.logoGroup}>
            <span className={styles.logoName}>DocuMind</span>
            <span className={styles.logoBadge}>Clinical Intelligence</span>
          </div>
        </div>

        <div className={styles.topRight}>
          <div className={styles.statusRow}>
            <span className={styles.statusDot} />
            <span className={styles.statusText}>Groq · Llama 3.3 70B · Free</span>
          </div>
          {hasMessages && (
            <button className={styles.clearBtn} onClick={clearChat}>
              <TrashIcon />
              <span>Clear</span>
            </button>
          )}
        </div>
      </header>

      {/* ── Body ──────────────────────────────────────────────────────────── */}
      <div className={styles.body}>

        {/* Mobile overlay */}
        {panelOpen && (
          <div className={styles.overlay} onClick={() => setPanelOpen(false)} />
        )}

        {/* File panel */}
        <div className={`${styles.panelWrap} ${panelOpen ? styles.panelOpen : ''}`}>
          <FilePanel
            documents={uploadProgress}
            uploadProgress={uploadProgress}
            onUpload={uploadPdf}
            onDelete={deleteDoc}
            documents={documents}
          />
        </div>

        {/* Chat area */}
        <main className={styles.main}>
          <div className={styles.messagesArea}>
            {!hasMessages ? (
              <EmptyState
                hasDocuments={documents.length > 0}
                onSuggest={handleSuggest}
              />
            ) : (
              <div className={styles.messagesList}>
                {messages.map(msg => (
                  <MessageBubble key={msg.id} message={msg} />
                ))}
                <div ref={bottomRef} className={styles.anchor} />
              </div>
            )}
          </div>

          {/* Input */}
          <div className={styles.inputArea}>
            <ChatInput
              value={input}
              onChange={setInput}
              onSend={sendMessage}
              onStop={() => {}}
              isStreaming={isStreaming}
              disabled={documents.length === 0}
            />
          </div>
        </main>
      </div>
    </div>
  )
}