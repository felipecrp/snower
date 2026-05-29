declare global {
  interface Window {
    snowShell?: {
      isElectron: true;
      platform: 'darwin' | 'win32' | 'linux';
      pickDirectory(options?: {
        title?: string;
        defaultPath?: string;
      }): Promise<string | null>;
      minimize(): void;
      maximizeToggle(): void;
      close(): void;
      onMaximizeChange(cb: (isMaximized: boolean) => void): void;
    };
  }
}

export {};
