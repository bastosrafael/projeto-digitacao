function AssistantIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3c.25 4.42 2.2 6.37 6.62 6.62C14.2 9.87 12.25 11.82 12 16.24c-.25-4.42-2.2-6.37-6.62-6.62C9.8 9.37 11.75 7.42 12 3Z" />
      <path d="M18.25 15.25c.1 1.9 1.1 2.9 3 3-1.9.1-2.9 1.1-3 3-.1-1.9-1.1-2.9-3-3 1.9-.1 2.9-1.1 3-3Z" />
    </svg>
  )
}

function UserIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="8" r="4" />
      <path d="M4.5 21a7.5 7.5 0 0 1 15 0" />
    </svg>
  )
}

function formatTime(timestamp) {
  if (!timestamp) return ''

  return new Intl.DateTimeFormat('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(timestamp))
}

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user'

  return (
    <article
      className={`message-row ${isUser ? 'message-row--user' : ''}`}
      aria-label={`Mensagem ${isUser ? 'do usuário' : 'do assistente'}`}
    >
      <div className={`message-avatar ${isUser ? 'message-avatar--user' : ''}`}>
        {isUser ? <UserIcon /> : <AssistantIcon />}
      </div>

      <div className="message-content">
        <div className="message-meta">
          <strong>{isUser ? 'Você' : 'Assistente'}</strong>
          <time dateTime={message.timestamp}>{formatTime(message.timestamp)}</time>
        </div>
        <div className={`message-bubble ${message.isError ? 'message-bubble--error' : ''}`}>
          {message.text}
        </div>
      </div>
    </article>
  )
}

export function LoadingMessage() {
  return (
    <article className="message-row" aria-label="Assistente está respondendo">
      <div className="message-avatar">
        <AssistantIcon />
      </div>
      <div className="message-content">
        <div className="message-meta">
          <strong>Assistente</strong>
          <span>pensando</span>
        </div>
        <div className="message-bubble message-bubble--loading">
          <span />
          <span />
          <span />
        </div>
      </div>
    </article>
  )
}
