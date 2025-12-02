import { create } from 'zustand';
import type { Operation } from '../types';

interface AppState {
  // Connection status
  browserConnected: boolean;
  loggedIn: boolean;

  // Current operation
  activeOperation: (Operation & { id: string }) | null;

  // UI state
  selectedUsers: Set<string>;
  activeTab: 'not-following-back' | 'unfollowers' | 'new-followers' | 'skip-list';
  settingsOpen: boolean;

  // Actions
  setBrowserConnected: (connected: boolean) => void;
  setLoggedIn: (loggedIn: boolean) => void;
  setActiveOperation: (op: (Operation & { id: string }) | null) => void;
  updateOperationProgress: (progress: number, total: number, message: string) => void;
  toggleUserSelection: (username: string) => void;
  selectAllUsers: (usernames: string[]) => void;
  clearSelection: () => void;
  setActiveTab: (tab: AppState['activeTab']) => void;
  setSettingsOpen: (open: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  browserConnected: false,
  loggedIn: false,
  activeOperation: null,
  selectedUsers: new Set(),
  activeTab: 'not-following-back',
  settingsOpen: false,

  setBrowserConnected: (connected) => set({ browserConnected: connected }),
  setLoggedIn: (loggedIn) => set({ loggedIn }),

  setActiveOperation: (op) => set({ activeOperation: op }),

  updateOperationProgress: (progress, total, message) =>
    set((state) => ({
      activeOperation: state.activeOperation
        ? { ...state.activeOperation, progress, total, message }
        : null,
    })),

  toggleUserSelection: (username) =>
    set((state) => {
      const newSet = new Set(state.selectedUsers);
      if (newSet.has(username)) {
        newSet.delete(username);
      } else {
        newSet.add(username);
      }
      return { selectedUsers: newSet };
    }),

  selectAllUsers: (usernames) =>
    set({ selectedUsers: new Set(usernames) }),

  clearSelection: () => set({ selectedUsers: new Set() }),

  setActiveTab: (tab) => set({ activeTab: tab }),

  setSettingsOpen: (open) => set({ settingsOpen: open }),
}));
