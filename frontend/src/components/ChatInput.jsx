import { useEffect, useRef, useState } from 'react'

function AttachmentIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m20.5 11.5-8.7 8.7a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7L9 17.4a2 2 0 0 1-2.8-2.8l8.2-8.2" />
    </svg>
  )
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m4 12 16-8-5.5 16-3-6.5L4 12Z" />
      <path d="M11.5 13.5 20 4" />
    </svg>
  )
}

export default function ChatInput({ onSend, isLoading }) {
  const [message, setMessage] = useState('')
  const [attachmentNotice, setAttachmentNotice] = useState(false)
  const textareaRef = useRef(null)

  const canSend = message.trim().length > 0 && !isLoading

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 144)}px`
  }, [message])

  function submit() {
    if (!canSend) return

    onSend(message.trim())
    setMessage('')
    setAttachmentNotice(false)
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  function showAttachmentNotice() {
    setAttachmentNotice(true)
    window.setTimeout(() => setAttachmentNotice(false), 3500)
  }

  return (
    <div className="composer-wrap">
      {attachmentNotice && (
        <div className="attachment-notice" role="status">
          Upload de planilha será habilitado na próxima etapa.
        </div>
      )}

      <div className={`composer ${isLoading ? 'composer--loading' : ''}`}>
        <button
          className="attachment-button"
          type="button"
          onClick={showAttachmentNotice}
          disabled={isLoading}
          aria-label="Anexar planilha (em breve)"
          title="Anexar planilha (em breve)"
        >
          <AttachmentIcon />
        </button>

        <textarea
          ref={textareaRef}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Digite sua mensagem..."
          rows="1"
          maxLength="20000"
          disabled={isLoading}
          aria-label="Mensagem para o assistente"
        />

        <button
          className="send-button"
          type="button"
          onClick={submit}
          disabled={!canSend}
          aria-label="Enviar mensagem"
        >
          <span>Enviar</span>
          <SendIcon />
        </button>
      </div>

      <p className="composer-hint">
        <span>Enter para enviar</span>
        <span className="hint-separator">•</span>
        <span>Shift + Enter para nova linha</span>
      </p>
    </div>
  )
}
