import { Request } from '../utils/request';
import type { CommonResponse } from '../types/responseModal';

export type LLMHistoryProvider = 'chatgpt' | 'claude' | 'gemini';

export interface ConnectorCatalogItem {
  type: string;
  name: string;
  description: string;
  ready: boolean;
  category: string;
  providers?: string[];
}

export interface LLMHistoryImportSummary {
  provider: LLMHistoryProvider;
  total_events: number;
  user_events: number;
  assistant_events: number;
  conversations: number;
  documents_created: number;
  earliest: string | null;
  latest: string | null;
  skipped_empty: number;
  document_ids: number[];
}

export const listConnectors = () => {
  return Request<CommonResponse<ConnectorCatalogItem[]>>({
    method: 'get',
    url: '/api/connectors'
  });
};

export const importLLMHistory = (
  provider: LLMHistoryProvider,
  file: File,
  userHandle = 'me'
) => {
  const formData = new FormData();
  formData.append('provider', provider);
  formData.append('user_handle', userHandle);
  formData.append('file', file);
  return Request<CommonResponse<LLMHistoryImportSummary>>({
    method: 'post',
    url: '/api/connectors/llm-history/import',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    timeout: 600 * 1000
  });
};
