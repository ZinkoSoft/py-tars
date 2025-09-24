interface ImportMetaEnv {
	readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
	readonly env: ImportMetaEnv;
}

declare const __API_BASE_URL__: string;
