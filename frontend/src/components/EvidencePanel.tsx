import type { EvidenceData } from '../api'

interface Props {
  evidence: EvidenceData | null
  toolsUsed: string[]
  onClose: () => void
}

const INTENT_LABELS: Record<string, string> = {
  screen_read: 'Leitura de tela',
  camera_read: 'Leitura por câmera',
  document_read: 'Leitura de documento',
  generic: 'Pergunta geral',
  visual: 'Análise visual',
}

function Badge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 600,
        background: ok ? '#16a34a22' : '#dc262622',
        color: ok ? '#16a34a' : '#dc2626',
        border: `1px solid ${ok ? '#16a34a44' : '#dc262644'}`,
      }}
    >
      {ok ? '✓' : '✗'} {label}
    </span>
  )
}

export default function EvidencePanel({ evidence, toolsUsed, onClose }: Props) {
  if (!evidence && toolsUsed.length === 0) return null

  return (
    <div
      style={{
        position: 'fixed',
        top: 16,
        right: 16,
        width: 320,
        maxHeight: '80vh',
        overflowY: 'auto',
        background: '#1a1a2e',
        border: '1px solid #334155',
        borderRadius: 12,
        padding: 16,
        zIndex: 1000,
        fontFamily: 'system-ui, sans-serif',
        color: '#e2e8f0',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#94a3b8' }}>
          Evidence
        </h3>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: '#64748b',
            cursor: 'pointer',
            fontSize: 16,
            padding: '0 4px',
          }}
        >
          ×
        </button>
      </div>

      {evidence && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {evidence.intent && (
            <div style={{ fontSize: 12 }}>
              <span style={{ color: '#64748b' }}>Intent: </span>
              <span style={{ color: '#f1f5f9', fontWeight: 600 }}>
                {INTENT_LABELS[evidence.intent] || evidence.intent}
              </span>
            </div>
          )}

          {evidence.monitor !== undefined && (
            <div style={{ fontSize: 12 }}>
              <span style={{ color: '#64748b' }}>Monitor: </span>
              <span style={{ color: '#f1f5f9' }}>{evidence.monitor}</span>
            </div>
          )}

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            <Badge ok={!!evidence.has_screen} label="Tela" />
            <Badge ok={!!evidence.has_ocr} label="OCR" />
            <Badge ok={!!evidence.has_camera} label="Câmera" />
            <Badge ok={!!evidence.has_document} label="Documento" />
            <Badge ok={!!evidence.has_window} label="Janela" />
          </div>

          {evidence.ocr_length !== undefined && evidence.ocr_length > 0 && (
            <div style={{ fontSize: 11, color: '#64748b' }}>
              OCR: {evidence.ocr_length} caracteres
            </div>
          )}

          {evidence.pipeline_stages && evidence.pipeline_stages.length > 0 && (
            <div style={{ fontSize: 11 }}>
              <span style={{ color: '#64748b' }}>Pipeline: </span>
              {evidence.pipeline_stages.join(' → ')}
            </div>
          )}

          {evidence.issues && evidence.issues.length > 0 && (
            <div
              style={{
                fontSize: 11,
                padding: '6px 8px',
                borderRadius: 6,
                background: '#dc262622',
                border: '1px solid #dc262644',
                color: '#fca5a5',
              }}
            >
              {evidence.issues.join('; ')}
            </div>
          )}
        </div>
      )}

      {toolsUsed.length > 0 && (
        <div style={{ marginTop: 12, borderTop: '1px solid #334155', paddingTop: 10 }}>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Ferramentas usadas:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {toolsUsed.map((t) => (
              <span
                key={t}
                style={{
                  fontSize: 10,
                  padding: '2px 6px',
                  borderRadius: 4,
                  background: '#334155',
                  color: '#cbd5e1',
                }}
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
