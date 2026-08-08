function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2.75c.28 4.85 2.43 7 7.25 7.25-4.82.28-6.97 2.43-7.25 7.25-.28-4.82-2.43-6.97-7.25-7.25C9.57 9.75 11.72 7.6 12 2.75Z" />
      <path d="M18.5 15.25c.11 2.06 1.19 3.14 3.25 3.25-2.06.12-3.14 1.2-3.25 3.25-.12-2.05-1.2-3.13-3.25-3.25 2.05-.11 3.13-1.19 3.25-3.25Z" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7h16M9 7V4h6v3m3 0-1 13H7L6 7m4 4v5m4-5v5" />
    </svg>
  )
}

export default function Header({ onClear, canClear }) {
  return (
    <header className="app-header">
      <div className="brand-lockup">
        <span className="brand-mark">
          <SparkIcon />
        </span>
        <div>
          <span className="eyebrow">Catálogo inteligente</span>
          <h1>Assistente de Produtos</h1>
        </div>
      </div>

      <div className="header-actions">
        <span className="service-status" title="Assistente disponível">
          <span className="status-dot" />
          Online
        </span>
        <button
          className="clear-button"
          type="button"
          onClick={onClear}
          disabled={!canClear}
          aria-label="Limpar conversa"
          title="Limpar conversa"
        >
          <TrashIcon />
          <span>Limpar</span>
        </button>
      </div>
    </header>
  )
}
