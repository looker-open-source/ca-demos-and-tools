import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

// 1. Define Types
export type ThemeType = 'light' | 'dark' | 'custom';

interface ThemeContextType {
  themeMode: ThemeType;
  setThemeMode: (theme: ThemeType) => void;
}

// 2. Create Context
const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

// 3. Helper to determine initial theme (moved from App.tsx)
const getInitialTheme = (): ThemeType => {
  const savedTheme = localStorage.getItem('app_theme');
  if (savedTheme === 'light' || savedTheme === 'dark' || savedTheme === 'custom') {
    return savedTheme;
  }
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  return 'light';
};

// 4. Create the Provider Component
export const AppThemeProvider = ({ children }: { children: ReactNode }) => {
  const [themeMode, setThemeMode] = useState<ThemeType>(getInitialTheme);

  // Persistence Effect
  useEffect(() => {
    localStorage.setItem('app_theme', themeMode);
  }, [themeMode]);

  return (
    <ThemeContext.Provider value={{ themeMode, setThemeMode }}>
      {children}
    </ThemeContext.Provider>
  );
};

// 5. Custom Hook for easy usage
export const useAppTheme = () => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useAppTheme must be used within an AppThemeProvider');
  }
  return context;
};