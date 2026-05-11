import React, { useRef, useEffect, useCallback } from 'react'
import styles from './ChatInput.module.scss'

const SendIcon = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13"/>
    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
)
const StopIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <rect x="4" y="4" width="16" height="16" rx="2"/>
  </svg>
)

export default function ChatInput({
  value, onChange, onSend, onStop,
  isStreaming, disabled
}) {
  const textareaRef = useRef()

  const adjustHeight = useCallback(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'
  }, [])

  useEffect(() => { adjustHeight() }, [value, adjustHeight])

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (isStreaming) { onStop(); return }
      if (value.trim()) onSend(value)
    }
  }

  const canSend = value.trim() && !isStreaming && !disabled

  return (
    <div className={styles.wrap}>
      <div className={`${styles.inputBox} ${disabled ? styles.inputDisabled : ''}`}>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          placeholder={
            disabled
              ? 'Upload a PDF on the left to start asking questions...'
              : 'Ask a question about your documents... (Shift+Enter for new line)'
          }
          value={value}
          onChange={e => { onChange(e.target.value); adjustHeight() }}
          onKeyDown={handleKey}
          rows={1}
          disabled={disabled}
          aria-label="Ask a question about your documents"
        />

        <button
          className={`
            ${styles.sendBtn}
            ${isStreaming ? styles.stopMode : ''}
            ${!canSend && !isStreaming ? styles.sendDisabled : ''}
          `}
          onClick={() => isStreaming ? onStop() : canSend && onSend(value)}
          title={isStreaming ? 'Stop generation' : 'Send message'}
          aria-label={isStreaming ? 'Stop' : 'Send'}
        >
          {isStreaming ? <StopIcon /> : <SendIcon />}
        </button>
      </div>

      <div className={styles.hints}>
        <span className={styles.hint}>
          <kbd>Enter</kbd> send · <kbd>Shift+Enter</kbd> new line
        </span>
        <span className={styles.hintRight}>
          Answers cite page numbers from your documents
        </span>
      </div>
    </div>
  )
}