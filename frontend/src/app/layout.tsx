import type { Metadata } from "next";
import { Cairo, Inter, JetBrains_Mono } from "next/font/google";
import Script from "next/script";
import "./globals.css";
import { Sidebar } from "@/components/layout/sidebar";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/components/auth-provider";
import { LanguageProvider } from "@/lib/i18n";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const cairo = Cairo({
  variable: "--font-cairo",
  subsets: ["arabic", "latin"],
});

const jetBrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "KarzounOS - Admin",
  description: "لوحة تحكم KarzounOS",
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
      suppressHydrationWarning
      className={`${cairo.variable} ${inter.variable} ${jetBrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex bg-gray-50">
        <Script id="admin-language-bootstrap" strategy="beforeInteractive">{`
          try {
            var savedLanguage = window.localStorage.getItem('admin-language');
            if (savedLanguage === 'en') {
              document.documentElement.lang = 'en';
              document.documentElement.dir = 'ltr';
            } else {
              document.documentElement.lang = 'ar';
              document.documentElement.dir = 'rtl';
            }
          } catch (error) {
            document.documentElement.lang = 'ar';
            document.documentElement.dir = 'rtl';
          }
        `}</Script>
        <LanguageProvider>
          <AuthProvider>
            <Sidebar />
            <main className="flex-1 pt-14 md:pt-0 min-h-screen bg-gradient-to-br from-gray-50 to-indigo-50/30">
              {children}
            </main>
          </AuthProvider>
          <Toaster position="top-right" />
        </LanguageProvider>
      </body>
    </html>
  );
}
