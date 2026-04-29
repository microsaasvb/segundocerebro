'use client';

import { useState } from 'react';
import { Alert, Button, Card, Descriptions, Radio, Upload, message } from 'antd';
import type { UploadFile } from 'antd/es/upload/interface';
import { InboxOutlined } from '@ant-design/icons';
import {
  importLLMHistory,
  type LLMHistoryImportSummary,
  type LLMHistoryProvider
} from '@/service/connectors';

const PROVIDER_HELP: Record<LLMHistoryProvider, string> = {
  chatgpt:
    'Em chat.openai.com → Settings → Data Controls → Export data. Você recebe um e-mail com um ZIP que contém conversations.json.',
  claude:
    'Em claude.ai → Settings → Account → Export data. O download é um ZIP com conversations.json.',
  gemini:
    'Em takeout.google.com escolha "Bard" ou "Gemini Apps". O ZIP contém uma pasta com MyActivity.json.'
};

export default function LLMHistoryConnectorPage(): JSX.Element {
  const [provider, setProvider] = useState<LLMHistoryProvider>('chatgpt');
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [summary, setSummary] = useState<LLMHistoryImportSummary | null>(null);

  const handleSubmit = async () => {
    if (fileList.length === 0 || !fileList[0].originFileObj) {
      message.error('Selecione um arquivo de export.');
      return;
    }
    setSubmitting(true);
    setSummary(null);
    try {
      const res = await importLLMHistory(provider, fileList[0].originFileObj as File);
      if (res.data.code !== 0) {
        throw new Error(res.data.message || 'Import failed');
      }
      setSummary(res.data.data);
      message.success(
        `Importação concluída: ${res.data.data.documents_created} conversas criadas.`
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Erro inesperado';
      message.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <header className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">LLM History</h1>
        <p className="text-gray-600">
          Importe sua história de conversas com ChatGPT, Claude ou Gemini. Cada conversa vira um
          documento em L0; o pipeline existente cuida de embedding e indexação.
        </p>
      </header>

      <Card className="mb-6">
        <h2 className="text-lg font-semibold mb-3">1. Escolha o provedor</h2>
        <Radio.Group
          value={provider}
          onChange={(e) => {
            setProvider(e.target.value);
            setFileList([]);
            setSummary(null);
          }}
        >
          <Radio.Button value="chatgpt">ChatGPT</Radio.Button>
          <Radio.Button value="claude">Claude</Radio.Button>
          <Radio.Button value="gemini">Gemini</Radio.Button>
        </Radio.Group>
        <Alert
          className="mt-4"
          type="info"
          showIcon
          message={`Como exportar do ${provider === 'chatgpt' ? 'ChatGPT' : provider === 'claude' ? 'Claude' : 'Gemini'}`}
          description={PROVIDER_HELP[provider]}
        />
      </Card>

      <Card className="mb-6">
        <h2 className="text-lg font-semibold mb-3">2. Suba o arquivo</h2>
        <Upload.Dragger
          accept=".zip,.json"
          beforeUpload={() => false /* prevent auto-upload, we handle it manually */}
          fileList={fileList}
          maxCount={1}
          onChange={({ fileList: newList }) => setFileList(newList)}
          onRemove={() => {
            setFileList([]);
            return true;
          }}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">Clique ou arraste o ZIP / JSON do export</p>
          <p className="ant-upload-hint">
            Aceita ZIP oficial ou conversations.json / MyActivity.json desempacotado.
          </p>
        </Upload.Dragger>
      </Card>

      <div className="flex justify-end mb-6">
        <Button
          type="primary"
          loading={submitting}
          disabled={fileList.length === 0}
          onClick={handleSubmit}
          size="large"
        >
          Importar
        </Button>
      </div>

      {summary && (
        <Card title="Resultado da importação">
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="Provedor">{summary.provider}</Descriptions.Item>
            <Descriptions.Item label="Conversas">{summary.conversations}</Descriptions.Item>
            <Descriptions.Item label="Documentos criados">
              {summary.documents_created}
            </Descriptions.Item>
            <Descriptions.Item label="Total de mensagens">{summary.total_events}</Descriptions.Item>
            <Descriptions.Item label="Mensagens do usuário">{summary.user_events}</Descriptions.Item>
            <Descriptions.Item label="Mensagens do assistente">
              {summary.assistant_events}
            </Descriptions.Item>
            {summary.earliest && (
              <Descriptions.Item label="Mais antiga">
                {new Date(summary.earliest).toLocaleString('pt-BR')}
              </Descriptions.Item>
            )}
            {summary.latest && (
              <Descriptions.Item label="Mais recente">
                {new Date(summary.latest).toLocaleString('pt-BR')}
              </Descriptions.Item>
            )}
          </Descriptions>
          <Alert
            className="mt-4"
            type="success"
            showIcon
            message="Próximos passos"
            description={
              <span>
                As conversas estão em L0. O pipeline de embedding vai processá-las em background.
                Você pode acompanhar em <strong>Train Second Me → Upload Your Memory</strong>.
              </span>
            }
          />
        </Card>
      )}
    </div>
  );
}
