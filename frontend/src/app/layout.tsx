import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/sidebar";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/components/auth-provider";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetBrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "KarzounOS — Admin",
  description: "نظام التشغيل للموظفين الرقميين — لوحة التحكم",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ar"
      dir="rtl"
      className={`${inter.variable} ${jetBrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex bg-gray-50">
        <AuthProvider>
          <Sidebar />
          <main className="flex-1 pt-14 md:pt-0 min-h-screen bg-gradient-to-br from-gray-50 to-indigo-50/30">
            {children}
          </main>
        </AuthProvider>
        <Toaster position="top-right" />
      </body>
    </html>
  );
}
