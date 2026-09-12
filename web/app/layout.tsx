import "./globals.css";
import { Nav } from "./nav";

export const metadata = {
  title: "Soulmate",
  description: "Entropy-driven matching MVP"
};

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        {children}
        <Nav />
      </body>
    </html>
  );
}

