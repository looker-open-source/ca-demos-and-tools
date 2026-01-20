import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path'; 

// Export a function that receives the build/serve environment
export default defineConfig(({ mode }) => {
  
  // 1. Define the directory where your env files are
  const envDir = 'environments';

  // 2. Load environment variables. 
  // Argument 2: path.resolve(process.cwd(), envDir) -> Gets absolute path to /project-root/environments
  // Argument 3: 'VITE_' -> ONLY loads variables prefixed with VITE_
  const env = loadEnv(mode, path.resolve(process.cwd(), envDir), 'VITE_'); 
  
  // 3. Define the target URL with a CRITICAL check.
  const API_TARGET = env.VITE_ADK_API_BASE_URL; 

  // LOGGING: This log will confirm the target before the server starts
  console.log(`[Vite Config] API Proxy Target set to: ${API_TARGET}`);

  return {
    plugins: [react()],
    
    // Set the envDir for Vite's internal reference
    envDir: envDir, 
    
    server: {
      proxy: {
        '/api': {
          target: API_TARGET,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''), 
        },
      },
    }
  };
});