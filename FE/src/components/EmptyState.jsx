import React from 'react'
import styles from './EmptyState.module.scss'

const FEATURES = [
  { emoji: '📄', title: 'Any PDF',        desc: 'Clinical reports, research papers, manuals' },
  { emoji: '🔍', title: 'Page citations', desc: 'Shows exact filename and page number' },
  { emoji: '💬', title: 'Multi-turn',     desc: 'Remembers context across questions' },
  { emoji: '⚡', title: 'Free & fast',    desc: 'Groq LPU — 300+ tokens per second' },
]

const SUGGESTIONS = [
  'What is the main diagnosis?',
  'What medications were prescribed?',
  'Summarise the key findings.',
  'What are the recommended next steps?',
]

export default function EmptyState({ hasDocuments, onSuggest }) {
  return (
    <div className={styles.wrap}>
      <div className={styles.icon}>
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/>
          <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/>
        </svg>
      </div>

      {!hasDocuments ? (
        <>
          <h2 className={styles.title}>Upload a document to begin</h2>
          <p className={styles.sub}>
            DocuMind reads your PDFs and answers questions<br />
            with exact page citations.
          </p>
        </>
      ) : (
        <>
          <h2 className={styles.title}>Ask a question</h2>
          <p className={styles.sub}>Your document is indexed. Try one of these:</p>
          <div className={styles.suggestions}>
            {SUGGESTIONS.map((s, i) => (
              <button key={i} className={styles.suggestion} onClick={() => onSuggest(s)}>
                {s}
              </button>
            ))}
          </div>
        </>
      )}

      <div className={styles.features}>
        {FEATURES.map((f, i) => (
          <div key={i} className={styles.feature}>
            <span className={styles.featureEmoji}>{f.emoji}</span>
            <p className={styles.featureTitle}>{f.title}</p>
            <p className={styles.featureDesc}>{f.desc}</p>
          </div>
        ))}
      </div>
    </div>
  )
}