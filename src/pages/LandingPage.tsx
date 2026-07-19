import React from 'react';
import BrandMark from '../components/brand/BrandMark';
import SearchBar from '../components/search/SearchBar';

const LandingPage: React.FC = () => (
  <div className="min-h-screen bg-[radial-gradient(circle_at_50%_0%,#ecfdf5_0%,#ffffff_43%,#f8fafc_100%)] px-4 text-slate-900">
    <header className="mx-auto flex w-full max-w-6xl items-center justify-between py-5">
      <BrandMark />
      <span className="rounded-full border border-emerald-100 bg-white/80 px-3 py-1.5 text-xs font-medium text-[#006a4e]">বাংলাদেশের জন্য</span>
    </header>

    <main className="mx-auto flex min-h-[calc(100vh-152px)] w-full max-w-3xl flex-col items-center justify-center pb-20">
      <div className="mb-9 text-center">
        <p className="text-sm font-medium text-[#006a4e]">স্থানীয় তথ্য, আপনার ভাষায়</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-[-0.05em] text-slate-950 sm:text-6xl">খুঁজুন যা আপনার কাছে জরুরি</h1>
        <p className="mx-auto mt-4 max-w-xl text-sm leading-6 text-slate-600 sm:text-base">খোঁজো বাংলা, Banglish এবং English প্রশ্ন থেকে নির্ভরযোগ্য স্থানীয় উৎস খুঁজে আনবে।</p>
      </div>
      <SearchBar autoFocus className="w-full" />
      <p className="mt-4 text-center text-xs text-slate-500">সাজেশন, উৎস ও ফলাফল—সবকিছু ধাপে ধাপে যাচাই করা হবে।</p>
    </main>

    <footer className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3 border-t border-slate-200 py-5 text-xs text-slate-500">
      <span>বাংলাদেশ</span>
      <span>খোঁজো একটি স্থানীয় জ্ঞানভিত্তিক অনুসন্ধান প্রকল্প</span>
    </footer>
  </div>
);

export default LandingPage;
