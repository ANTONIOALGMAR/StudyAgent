import { documentFileUrl, type UploadedDoc } from '../api'

interface Props {
  doc: UploadedDoc
  onClose: () => void
}

export default function PdfViewer({ doc, onClose }: Props) {
  return (
    <div className="live-panel pdf-panel">
      <div className="live-head">
        <strong>📄 {doc.name}</strong>
        <span className="pdf-pages">
          {doc.pages} página{doc.pages > 1 ? 's' : ''}
        </span>
        <a
          className="btn-screen"
          href={documentFileUrl(doc.id)}
          target="_blank"
          rel="noreferrer"
          title="Abrir em nova aba"
        >
          ↗
        </a>
        <button className="btn-screen" onClick={onClose} title="Fechar leitor">
          ✕
        </button>
      </div>
      <iframe
        src={`${documentFileUrl(doc.id)}#toolbar=1&view=FitH`}
        title={`Visualização de ${doc.name}`}
        className="pdf-frame"
      />
    </div>
  )
}
