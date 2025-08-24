import Link from "next/link";
import "./globals.css";
import { Poppins } from 'next/font/google';
import { Toaster } from 'react-hot-toast';
import { FaChartBar, FaUserCog } from 'react-icons/fa';
import { AiOutlineMail, AiOutlineSearch } from 'react-icons/ai';
import { BsEnvelopeArrowUp } from "react-icons/bs";


const poppins = Poppins({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  display: 'swap',
});

export const metadata = {
  title: "Email Agent Pro | AI-Powered Outreach",
  description: "Advanced email automation and lead generation platform",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${poppins.className}`}>
      <body className="antialiased bg-slate-50 text-slate-800">
        <Toaster position="top-right" />
        <div className="flex min-h-screen">
          {/* Sidebar */}
          <aside className="w-64 bg-slate-900 text-white border-r border-slate-700/50">
            <div className="sticky top-0 h-screen flex flex-col">
              {/* Logo/Branding */}
              <div className="p-6 pb-4 border-b border-slate-700/50">
                <h1 className="text-2xl font-bold flex items-center gap-2 text-teal-400">
                  <AiOutlineMail className="w-6 h-6" />
                  <span>EmailAgent</span>
                </h1>
                <p className="text-xs text-slate-400 mt-1">AI-Powered Outreach</p>
              </div>

              {/* Navigation */}
              <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
                <Link
                  href="/analytics"
                  className="flex items-center gap-3 px-4 py-3 rounded-lg text-slate-300 hover:bg-slate-700/50 hover:text-white transition-colors group"
                >
                  <FaChartBar className="w-5 h-5 group-hover:scale-110 transition-transform" />
                  <span>Analytics</span>
                </Link>
                <Link
                  href="/generate-leads"
                  className="flex items-center gap-3 px-4 py-3 rounded-lg text-slate-300 hover:bg-slate-700/50 hover:text-white transition-colors group"
                >
                  <AiOutlineSearch className="w-5 h-5 group-hover:scale-110 transition-transform" />
                  <span>Generate Leads</span>
                </Link>
                <Link
                  href="/send-emails"
                  className="flex items-center gap-3 px-4 py-3 rounded-lg text-slate-300 hover:bg-slate-700/50 hover:text-white transition-colors group"
                >
                  <BsEnvelopeArrowUp className="w-5 h-5 group-hover:scale-110 transition-transform" />
                  <span>Send Emails</span>
                </Link>
                <Link
                  href="/unread-mails"
                  className="flex items-center gap-3 px-4 py-3 rounded-lg text-slate-300 hover:bg-slate-700/50 hover:text-white transition-colors group"
                >
                  <AiOutlineMail className="w-5 h-5 group-hover:scale-110 transition-transform" />
                  <span>Recent Emails</span>
                </Link>
              </nav>

              {/* User/Account section */}
              <div className="p-4 border-t border-slate-700/50">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-teal-500 flex items-center justify-center">
                    <span className="font-medium text-white">N</span>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">Admin - Nassar</p>
                  </div>
                </div>
              </div>
            </div>
          </aside>

          {/* Main content */}
          <main className="flex-1 min-h-screen overflow-y-auto">
            {/* Top bar */}
            <header className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-800">Dashboard</h2>
            </header>

            {/* Content area */}
            <div className="p-6">
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}