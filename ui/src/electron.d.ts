declare global {
  interface Window {
    snowShell?: {
      pickDirectory(options?: {
        title?: string;
        defaultPath?: string;
      }): Promise<string | null>;
    };
  }
}

export {};
