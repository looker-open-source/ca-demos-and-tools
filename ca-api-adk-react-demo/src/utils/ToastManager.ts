// utils/ToastManager.ts

type ToastType = 'success' | 'error' | 'info' | 'warning';
type ToastListener = (message: string, type: ToastType) => void;

class ToastManager {
  private listener: ToastListener | null = null;

  // React component will call this to subscribe
  register(listener: ToastListener) {
    this.listener = listener;
  }

  // React component calls this to unsubscribe
  unregister() {
    this.listener = null;
  }

  // Service files call this to show a notification
  show(message: string, type: ToastType = 'info') {
    if (this.listener) {
      this.listener(message, type);
    } else {
      console.warn('ToastManager: Message missed (no listener):', message);
    }
  }
}

export const toastManager = new ToastManager();