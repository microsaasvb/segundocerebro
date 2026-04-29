'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import CreateSecondMe from '@/app/home/components/Create';
import dynamic from 'next/dynamic';
import type { ILoadInfo } from '@/service/info';
import { getCurrentInfo } from '@/service/info';
import { ROUTER_PATH } from '@/utils/router';

const NetworkSphere = dynamic(() => import('@/components/NetworkSphere'), {
  ssr: false,
  loading: () => <div className="fixed inset-0 -z-10 w-screen h-screen overflow-hidden bg-white" />
});

export default function Home() {
  const router = useRouter();
  const [showCreate, setShowCreate] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const [contentVisible, setContentVisible] = useState(false);

  const [loading, setLoading] = useState(true);
  const [loadInfo, setLoadInfo] = useState<ILoadInfo | null>(null);

  useEffect(() => {
    getCurrentInfo()
      .then((res) => {
        if (res.data.code === 0) {
          setLoadInfo(res.data.data);
          localStorage.setItem('upload', JSON.stringify(res.data.data));
        }
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const handleExistingUploadClick = () => {
    router.push(ROUTER_PATH.DASHBOARD);
  };

  const handleSphereInitialized = () => {
    setTimeout(() => {
      setContentVisible(true);
    }, 300);
  };

  // Only render content on the client side
  if (!isMounted) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-4 relative bg-brand-deep">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-brand-neon" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 relative">
      {/* Dark page backdrop - sits behind the animated network sphere */}
      <div className="fixed inset-0 -z-20 bg-brand-deep" />

      {/* Network sphere background */}
      <NetworkSphere onInitialized={handleSphereInitialized} />

      {/* Background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div
          className={`absolute top-20 left-20 w-64 h-64 rounded-full bg-brand-pink/30 blur-3xl delay-[400ms] transition-opacity duration-1000 ease-in-out ${contentVisible ? 'opacity-100' : 'opacity-0'}`}
        />
        <div
          className={`absolute bottom-20 right-20 w-64 h-64 rounded-full bg-brand-neon/30 blur-3xl delay-[500ms] transition-opacity duration-1000 ease-in-out ${contentVisible ? 'opacity-100' : 'opacity-0'}`}
        />
        <div
          className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 rounded-full bg-brand-accent/30 blur-3xl delay-[600ms] transition-opacity duration-1000 ease-in-out ${contentVisible ? 'opacity-100' : 'opacity-0'}`}
        />
      </div>

      <div className="relative z-10 text-center mt-[-8vh] w-full overflow-visible px-4 font-[var(--font-display)]">
        <div
          className={`transition-opacity duration-700 ease-in-out ${contentVisible ? 'opacity-100' : 'opacity-0'}`}
        >
          <h1 className="text-5xl md:text-6xl font-bold mb-3 mx-auto leading-tight px-4 flex items-center justify-center">
            <img
              alt="Segundo Cerebro Logo"
              className="h-20 md:h-28 mr-5"
              src="/images/icone-escuro.png"
            />
            <span
              className="text-white inline-block tracking-tight"
              style={{
                textShadow: '0 0 30px rgba(0,255,148,0.2)'
              }}
            >
              Create Your AI self
            </span>
          </h1>
          <p className="text-2xl md:text-3xl mb-14 mx-auto px-4 flex flex-wrap justify-center tracking-tight font-medium">
            <span className="inline-block mx-2 text-white">Locally Trained</span>
            <span className="inline-block text-brand-neon mx-2">·</span>
            <span className="inline-block mx-2 text-white">Globally Connected</span>
          </p>
        </div>

        {!loading && (
          <div
            className={`transition-opacity duration-700 ease-in-out delay-[300ms] ${contentVisible ? 'opacity-100' : 'opacity-0'}`}
          >
            {loadInfo ? (
              <button className="btn-primary" onClick={handleExistingUploadClick}>
                Continue as {loadInfo.name}
              </button>
            ) : (
              <button className="btn-primary" onClick={() => setShowCreate(true)}>
                Create my Second Me
              </button>
            )}
          </div>
        )}
      </div>

      {showCreate && <CreateSecondMe onClose={() => setShowCreate(false)} />}
    </div>
  );
}
