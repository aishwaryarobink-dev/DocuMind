import React, { useState } from 'react'
import styles from './MessageBubble.module.scss'

// ── Icons ─────────────────────────────────────────────────────────────────────
const CopyIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2"/>
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
  </svg>
)
const CitationIcon = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <line x1="16" y1="13" x2="8" y2="13"/>
    <line x1="16" y1="17" x2="8" y2="17"/>
  </svg>
)
const BrainIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/>
    <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/>
  </svg>
)

// ── Simple markdown renderer ──────────────────────────────────────────────────
function renderContent(text) {
  if (!text) return null
  const lines = text.split('\n')
  const elements = []
  let listItems  = []
  let key        = 0

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`ul-${key++}`} className={styles.list}>{listItems}</ul>
      )
      listItems = []
    }
  }

  lines.forEach((line, i) => {
    if (!line.trim()) {
      flushList()
      if (elements.length > 0) elements.push(<br key={`br-${i}`} />)
      return
    }

    // Bullet point
    if (line.match(/^[•\-\*]\s/)) {
      const content = line.replace(/^[•\-\*]\s/, '')
      listItems.push(
        <li key={`li-${i}`} className={styles.listItem}>{parseBold(content)}</li>
      )
      return
    }

    // Numbered list
    if (line.match(/^\d+\.\s/)) {
      flushList()
      elements.push(
        <p key={`nl-${i}`} className={styles.numbered}>{parseBold(line)}</p>
      )
      return
    }

    flushList()

    // Bold header line
    if (line.startsWith('**') && line.endsWith('**') && line.length > 4) {
      elements.push(
        <p key={`h-${i}`} className={styles.boldHeader}>{line.slice(2, -2)}</p>
      )
      return
    }

    elements.push(
      <p key={`p-${i}`} className={styles.paragraph}>{parseBold(line)}</p>
    )
  })

  flushList()
  return elements
}

function parseBold(text) {
  return text.split(/(\*\*[^*]+\*\*)/).map((part, i) =>
    part.startsWith('**')
      ? <strong key={i}>{part.slice(2, -2)}</strong>
      : part
  )
}

function formatTime(date) {
  return date.toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', hour12: true
  })
}

// ── Main component ────────────────────────────────────────────────────────────
export default function MessageBubble({ message }) {
  const { role, content, citations, streaming, error, ts } = message
  const [copied, setCopied] = useState(false)

  const isUser   = role === 'user'
  const isSystem = role === 'system'

  // System message (upload notification)
  if (isSystem) {
    return (
      <div className={styles.systemMsg}>
        <span className={styles.systemIcon}>📄</span>
        <span>{content}</span>
      </div>
    )
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className={`${styles.wrapper} ${isUser ? styles.user : styles.assistant} animate-fade`}>
      {!isUser && (
        <div className={styles.avatar}>
          <BrainIcon />
        </div>
      )}

      <div className={styles.group}>
        {/* Bubble */}
        <div className={`${styles.bubble}
          ${isUser    ? styles.bubbleUser : styles.bubbleAi}
          ${error     ? styles.bubbleError : ''}
        `}>
          {isUser ? (
            <p className={styles.userText}>{content}</p>
          ) : (
            <div className={styles.aiContent}>
              {renderContent(content)}
              {streaming && <span className={styles.cursor} />}
            </div>
          )}
        </div>

        {/* Citations — shown below bubble, only when streaming is done */}
        {!isUser && !streaming && citations?.length > 0 && (
          <div className={styles.citations}>
            {citations.map((c, i) => (
              <span key={i} className={styles.citation}>
                <CitationIcon />
                {c.filename} · p.{c.pages.join(', ')}
              </span>
            ))}
          </div>
        )}

        {/* Meta: time + copy button */}
        <div className={`${styles.meta} ${isUser ? styles.metaUser : styles.metaAi}`}>
          <span className={styles.time}>{formatTime(ts)}</span>
          {!isUser && !streaming && content && (
            <button className={styles.copyBtn} onClick={handleCopy}>
              <CopyIcon />
              <span>{copied ? 'Copied!' : 'Copy'}</span>
            </button>
          )}
        </div>
      </div>

      {isUser && (
        <div className={styles.avatarUser}>A</div>
      )}
    </div>
  )
}