import { Header } from '@/layouts/HeaderLayout/Header';

const HeaderLayout = ({ children }: { children: React.ReactNode }) => {
  return (
    <>
      <Header />
      <div className="flex-1 overflow-hidden">{children}</div>
    </>
  );
};

export default HeaderLayout;
