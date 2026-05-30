import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "IELTS CB Mock Tests",
  description: "Computer-Delivered IELTS practice — Reading, Listening, Writing, Speaking.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-exam text-exam-text bg-exam-bg min-h-screen">
        <div id="exam-root">{children}</div>
      </body>
    </html>
  );
}
