import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UserProfile {
  name: string;
  level: string;
  xp: number;
  streak: number;
  mastery: Record<string, number>;
}

interface UserState {
  profile: UserProfile | null;
  setProfile: (profile: UserProfile) => void;
  addXp: (amount: number) => void;
  updateMastery: (theme: string, score: number) => void;
  resetProfile: () => void;
}

export const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      profile: null,
      setProfile: (profile) => set({ profile }),
      addXp: (amount) => set((state) => {
        if (!state.profile) return state;
        const newXp = state.profile.xp + amount;
        
        // Level logic based on the project's gamification rules
        let newLevel = state.profile.level;
        if (newXp >= 1000) newLevel = 'Mestre';
        else if (newXp >= 600) newLevel = 'Especialista';
        else if (newXp >= 300) newLevel = 'Graduado';
        else if (newXp >= 100) newLevel = 'Estudante';
        else newLevel = 'Iniciante';

        return {
          profile: { ...state.profile, xp: newXp, level: newLevel }
        };
      }),
      updateMastery: (theme, score) => set((state) => {
        if (!state.profile) return state;
        return {
          profile: {
            ...state.profile,
            mastery: { ...state.profile.mastery, [theme]: score }
          }
        };
      }),
      resetProfile: () => set({ profile: null }),
    }),
    {
      name: 'studyagent-user-storage',
    }
  )
)
