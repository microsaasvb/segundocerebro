'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Card, Tag, Skeleton, message } from 'antd';
import { listConnectors, type ConnectorCatalogItem } from '@/service/connectors';
import { ROUTER_PATH } from '@/utils/router';

const TYPE_TO_PATH: Record<string, string> = {
  llm_history: ROUTER_PATH.CONNECTORS_LLM_HISTORY
};

export default function ConnectorsPage(): JSX.Element {
  const [items, setItems] = useState<ConnectorCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listConnectors()
      .then((res) => {
        if (res.data.code === 0) {
          setItems(res.data.data || []);
        } else {
          throw new Error(res.data.message || 'Failed to load connectors');
        }
      })
      .catch((err: Error) => {
        message.error(err.message || 'Failed to load connectors');
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Connectors</h1>
        <p className="text-gray-600">
          Bring data from your tools into your Second Brain. Each connector ingests events into L0
          and the existing pipeline takes care of embedding, indexing and training.
        </p>
      </header>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Card key={i}>
              <Skeleton active />
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => {
            const target = TYPE_TO_PATH[item.type];
            const card = (
              <Card
                hoverable={item.ready}
                className={item.ready ? '' : 'opacity-60 cursor-not-allowed'}
                title={
                  <div className="flex items-center justify-between">
                    <span>{item.name}</span>
                    <Tag color={item.ready ? 'green' : 'default'}>
                      {item.ready ? 'Ready' : 'Coming soon'}
                    </Tag>
                  </div>
                }
              >
                <p className="text-sm text-gray-600 mb-3">{item.description}</p>
                <Tag>{item.category}</Tag>
                {item.providers && (
                  <div className="mt-3 flex gap-1 flex-wrap">
                    {item.providers.map((p) => (
                      <Tag key={p} color="blue">
                        {p}
                      </Tag>
                    ))}
                  </div>
                )}
              </Card>
            );
            return item.ready && target ? (
              <Link key={item.type} href={target}>
                {card}
              </Link>
            ) : (
              <div key={item.type}>{card}</div>
            );
          })}
        </div>
      )}
    </div>
  );
}
