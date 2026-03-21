/**
 * Theme Store
 * Manages dark/light theme with localStorage persistence using Zustand.
 */

import { create } from 'zustand';

const useThemeStore = create((set) => ({
  theme: localStorage.getItem('ca-theme') || 'dark',
  
  toggleTheme: () => set((state) => {
    const newTheme = state.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('ca-theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
    return { theme: newTheme };
  }),
  
  setTheme: (theme) => {
    localStorage.setItem('ca-theme', theme);
    document.documentElement.setAttribute('data-theme', theme);
    set({ theme });
  },
}));

// Initialize theme on load
const savedTheme = localStorage.getItem('ca-theme') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);

export default useThemeStore;
