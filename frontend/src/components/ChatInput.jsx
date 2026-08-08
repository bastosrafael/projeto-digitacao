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

function formatFileSize(sizeBytes) {
  const sizeMb = sizeBytes / (1024 * 1024)
  return `${new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 }).format(sizeMb)} MB`
}

export default function ChatInput({
  onSend,
  onUpload,
  isLoading,
  isUploading,
  uploadConfig,
}) {
  const [message, setMessage] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)
  const [attachmentNotice, setAttachmentNotice] = useState(null)
  const [uploadState, setUploadState] = useState('idle')
  const textareaRef = useRef(null)
  const fileInputRef = useRef(null)

  const isBusy = isLoading || isUploading
  const canSend = (message.trim().length > 0 || selectedFile !== null) && !isBusy

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 144)}px`
  }, [message])

  async function submit() {
    if (!canSend) return

    if (selectedFile) {
      setUploadState('uploading')
      setAttachmentNotice(
        `Enviando ${selectedFile.name} · ${formatFileSize(selectedFile.size)}...`,
      )
      try {
        const result = await onUpload(selectedFile)
        setUploadState('uploaded')
        setAttachmentNotice(
          `${selectedFile.name} · ${formatFileSize(selectedFile.size)} recebido com sucesso. ID: ${result.file_id}`,
        )
        setSelectedFile(null)
        if (fileInputRef.current) fileInputRef.current.value = ''
      } catch (error) {
        setUploadState('error')
        setAttachmentNotice(error.message || 'Não foi possível enviar a planilha.')
      }
      return
    }

    onSend(message.trim())
    setMessage('')
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  async function handleAttachmentClick() {
    if (!uploadConfig) {
      setUploadState('error')
      setAttachmentNotice('Não foi possível consultar o limite de upload. Tente novamente.')
      return
    }

    if (selectedFile) {
      setSelectedFile(null)
      setUploadState('idle')
      setAttachmentNotice('Anexo removido.')
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    fileInputRef.current?.click()
  }

  function handleFileSelection(event) {
    const file = event.target.files?.[0]
    if (!file) return

    if (!file.name.toLowerCase().endsWith('.xlsx')) {
      setSelectedFile(null)
      setUploadState('error')
      setAttachmentNotice('Selecione uma planilha no formato .xlsx.')
      event.target.value = ''
      return
    }

    const maxSizeBytes = uploadConfig.max_upload_size_mb * 1024 * 1024
    if (file.size > maxSizeBytes) {
      setSelectedFile(null)
      setUploadState('error')
      setAttachmentNotice(
        `Arquivo excede o limite permitido de ${uploadConfig.max_upload_size_mb} MB.`,
      )
      event.target.value = ''
      return
    }

    setSelectedFile(file)
    setUploadState('selected')
    setAttachmentNotice(
      `${file.name} · ${formatFileSize(file.size)}. Enviar confirma; o clipe remove.`,
    )
  }

  return (
    <div className="composer-wrap" data-upload-state={uploadState}>
      {attachmentNotice && (
        <div className="attachment-notice" role="status">
          {attachmentNotice}
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        onChange={handleFileSelection}
        hidden
      />

      <div className={`composer ${isBusy ? 'composer--loading' : ''}`}>
        <button
          className="attachment-button"
          type="button"
          onClick={handleAttachmentClick}
          disabled={isBusy}
          aria-label={selectedFile ? 'Remover planilha selecionada' : 'Anexar planilha'}
          title={selectedFile ? 'Remover planilha selecionada' : 'Anexar planilha'}
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
          disabled={isBusy}
          aria-label="Mensagem para o assistente"
        />

        <button
          className="send-button"
          type="button"
          onClick={submit}
          disabled={!canSend}
          aria-label={selectedFile ? 'Enviar planilha' : 'Enviar mensagem'}
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
