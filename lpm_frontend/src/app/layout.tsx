import type { Metadata } from 'next';
import './globals.css';
import { Suspense } from 'react';
import { Analytics } from '@vercel/analytics/next';
import { Space_Grotesk } from 'next/font/google';
import { AntdRegistry } from '@ant-design/nextjs-registry';
import { App as AntdApp, ConfigProvider } from 'antd';
import HeaderLayout from '@/layouts/HeaderLayout';

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-display'
});

export const metadata: Metadata = {
  title: 'Segundo Cerebro',
  description: 'Crie e treine seu segundo cérebro',
  icons: {
    icon: '/favicon.png'
  }
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html className={`h-full ${spaceGrotesk.variable}`} lang="en">
      <body className="flex flex-col font-sans antialiased h-full">
        <AntdRegistry>
          <ConfigProvider theme={{ hashed: false }}>
            <AntdApp>
              <Suspense>
                <HeaderLayout>{children}</HeaderLayout>
              </Suspense>
            </AntdApp>
          </ConfigProvider>
        </AntdRegistry>
        <Analytics />
      </body>
    </html>
  );
}
