import "./globals.css";
import { Nav } from "./nav";

export const metadata = {
  title: "SoulMate · 信息熵匹配 Demo",
  description: "由 /api/v1/space/state 驱动的四种界面状态"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <header className="topbar">
          <div className="topbarInner">
            <div className="brand">SoulMate</div>
            <div className="muted" style={{ fontSize: 12 }}>
              信息熵驱动的同频匹配 · Demo
            </div>
          </div>
        </header>
        {children}
        <Nav />
      </body>
    </html>
  );
}
