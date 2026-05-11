import { useState, useRef, useCallback } from 'react'

const API = import.meta.env.VITE_API_URL 

function getSessionId() {
  let id = sessionStorage.getItem('documind_session')
  if (!id) {
    id = crypto.randomUUID()
    sessionStorage.setItem('documind_session', id)
  }
  return id
}

export function useDocuMind() {
  const sessionId = useRef(getSessionId())

  const [documents,       setDocuments]       = useState([])
  const [messages,        setMessages]        = useState([])
  const [input,           setInput]           = useState('')
  const [isStreaming,     setIsStreaming]      = useState(false)
  const [uploadProgress,  setUploadProgress]  = useState(null)
  // null | { name, status: 'uploading'|'done'|'error', error? }

  const msgId = useRef(0)
  const nextId = () => ++msgId.current

  // ── Upload PDF ────────────────────────────────────────────────────────────
  const uploadPdf = useCallback(async (file) => {
    if (!file) return
    if (file.type !== 'application/pdf') {
      alert('Please upload a PDF file')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      alert('File is too large. Maximum size is 10MB')
      return
    }

    setUploadProgress({ name: file.name, status: 'uploading' })

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('session_id', sessionId.current)

      const res  = await fetch(`${API}/api/upload`, {
        method: 'POST',
        body:   formData,
        // NOTE: do NOT set Content-Type header manually
        // The browser sets it automatically with the correct multipart boundary
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.error || 'Upload failed')
      }

      // Add to document list — avoid duplicates
      setDocuments(prev => {
        const exists = prev.find(d => d.doc_id === data.doc_id)
        if (exists) return prev
        return [...prev, {
          doc_id: data.doc_id,
          name:   data.name,
          pages:  data.pages,
          chunks: data.chunk_count,
        }]
      })

      setUploadProgress({ name: file.name, status: 'done' })
      setTimeout(() => setUploadProgress(null), 3000)

      // Add system notification to chat
      setMessages(prev => [...prev, {
        id:      nextId(),
        role:    'system',
        content: `"${data.name}" uploaded — ${data.pages} pages, ${data.chunk_count} chunks indexed.`,
        ts:      new Date(),
      }])

    } catch (err) {
      setUploadProgress({ name: file.name, status: 'error', error: err.message })
      setTimeout(() => setUploadProgress(null), 5000)
    }
  }, [])

  // ── Delete document ───────────────────────────────────────────────────────
  const deleteDoc = useCallback(async (docId) => {
    try {
      await fetch(`${API}/api/documents/${sessionId.current}/${docId}`, {
        method: 'DELETE'
      })
      setDocuments(prev => prev.filter(d => d.doc_id !== docId))
    } catch (err) {
      console.error('Delete error:', err)
    }
  }, [])

  // ── Send message + stream response ───────────────────────────────────────
  const sendMessage = useCallback(async (text) => {
    const question = text.trim()
    if (!question || isStreaming) return
    if (documents.length === 0) {
      alert('Please upload at least one PDF document first')
      return
    }

    const userMsg = {
      id:      nextId(),
      role:    'user',
      content: question,
      ts:      new Date(),
    }
    const aiId  = nextId()
    const aiMsg = {
      id:        aiId,
      role:      'assistant',
      content:   '',
      citations: [],
      streaming: true,
      ts:        new Date(),
    }

    setMessages(prev => [...prev, userMsg, aiMsg])
    setInput('')
    setIsStreaming(true)

    // Build history from last 4 exchanges
    const history = messages
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .slice(-8)
      .map(m => ({ role: m.role, content: m.content }))

    try {
      const res = await fetch(`${API}/api/chat`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          question,
          session_id: sessionId.current,
          history,
        }),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.error || 'Request failed')
      }

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const raw = decoder.decode(value)

        // Split on double newline — each SSE event ends with \n\n
        raw.split('\n\n').forEach(line => {
          if (!line.startsWith('data: ')) return
          const payload = line.slice(6).trim()
          if (payload === '[DONE]') return

          try {
            const data = JSON.parse(payload)

            if (data.type === 'citations') {
              // First event: set citations before any text arrives
              setMessages(prev => prev.map(m =>
                m.id === aiId ? { ...m, citations: data.citations } : m
              ))
            } else if (data.type === 'text' && data.text) {
              // Append each token to message content
              setMessages(prev => prev.map(m =>
                m.id === aiId
                  ? { ...m, content: m.content + data.text }
                  : m
              ))
            } else if (data.type === 'error') {
              throw new Error(data.message)
            }
          } catch (parseErr) {
            // Ignore malformed SSE lines
          }
        })
      }

      // Mark streaming complete
      setMessages(prev => prev.map(m =>
        m.id === aiId ? { ...m, streaming: false } : m
      ))

    } catch (err) {
      setMessages(prev => prev.map(m =>
        m.id === aiId
          ? { ...m, content: `Error: ${err.message}`, streaming: false, error: true }
          : m
      ))
    } finally {
      setIsStreaming(false)
    }
  }, [isStreaming, documents, messages])

  // ── Clear chat ────────────────────────────────────────────────────────────
  const clearChat = useCallback(() => {
    setMessages([])
  }, [])

  return {
    sessionId: sessionId.current,
    documents,
    messages,
    input,       setInput,
    isStreaming,
    uploadProgress,
    uploadPdf,
    deleteDoc,
    sendMessage,
    clearChat,
  }
}