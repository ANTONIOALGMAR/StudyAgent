import { Suspense, lazy } from 'react'
import { 
  ExercisesPanel, 
  FlashcardsPanel, 
  StudyPlanPanel, 
  StatsPanel, 
  ProfilePanel, 
  AchievementsPanel 
} from './panels' // We will create this index file next

interface PanelManagerProps {
  panels: {
    exOpen: boolean;
    fcOpen: boolean;
    spOpen: boolean;
    stOpen: boolean;
    profOpen: boolean;
    achOpen: boolean;
  };
  setPanels: (panel: string, value: boolean) => void;
  onMood: (mood: any) => void;
}

export default function PanelManager({ panels, setPanels, onMood }: PanelManagerProps) {
  const PanelWrapper = ({ title, isOpen, id, children }: any) => {
    if (!isOpen) return null;
    return (
      <div className={`live-panel ${id}-panel`}>
        <div className="live-head">
          <strong>{title}</strong>
          <button className="btn-screen" onClick={() => setPanels(id, false)}>✕</button>
        </div>
        {children}
      </div>
    );
  };

  return (
    <Suspense fallback={<div style={{ padding: 20, textAlign: 'center', color: '#8b93a7' }}><span className="spinner" /> carregando…</div>}>
      <PanelWrapper title="🎯 exercícios" isOpen={panels.exOpen} id="exercises" onClose={() => setPanels('ex', false)}>
        <ExercisesPanel onMood={onMood} />
      </PanelWrapper>
      
      <PanelWrapper title="🃏 flashcards" isOpen={panels.fcOpen} id="flashcards" onClose={() => setPanels('fc', false)}>
        <FlashcardsPanel onMood={onMood} />
      </PanelWrapper>

      <PanelWrapper title="📋 plano de estudo" isOpen={panels.spOpen} id="studyplan" onClose={() => setPanels('sp', false)}>
        <StudyPlanPanel onMood={onMood} />
      </PanelWrapper>

      <PanelWrapper title="📊 progresso" isOpen={panels.stOpen} id="stats" onClose={() => setPanels('st', false)}>
        <StatsPanel />
      </PanelWrapper>

      <PanelWrapper title="👤 perfil" isOpen={panels.profOpen} id="profile" onClose={() => setPanels('prof', false)}>
        <ProfilePanel />
      </PanelWrapper>

      <PanelWrapper title="🏆 conquistas" isOpen={panels.achOpen} id="achievements" onClose={() => setPanels('ach', false)}>
        <AchievementsPanel />
      </PanelWrapper>
    </Suspense>
  );
}
