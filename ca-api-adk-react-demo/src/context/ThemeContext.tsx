import React, { createContext, useContext, useState, ReactNode } from 'react';

export interface CustomThemeData {
  bgColor: string;
  fontFamily: string;
  userAvatar: string | null;
}

export type ThemeType = 'light' | 'dark' | 'custom';

interface ThemeContextType {
  themeMode: ThemeType;
  setThemeMode: (mode: ThemeType) => void;
  customTheme: CustomThemeData;
  setCustomTheme: (data: CustomThemeData) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const AppThemeProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [themeMode, setThemeMode] = useState<ThemeType>('light');
  
  const [customTheme, setCustomTheme] = useState<CustomThemeData>({
    bgColor: '#E8F0FE',
    fontFamily: 'Inter',
    userAvatar: null 
  });

  return (
    <ThemeContext.Provider value={{ 
      themeMode, 
      setThemeMode,
      customTheme, 
      setCustomTheme 
    }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useAppTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useAppTheme must be used within AppThemeProvider');
  return context;
};