import React from 'react';
import { Globe } from 'lucide-react';
import SearchBar from '../components/search/SearchBar';

const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-white px-4">
      <div className="w-full max-w-2xl flex flex-col items-center">
        {/* Logo Section */}
        <div className="mb-8 text-center">
          <img src="/src/assets/logo.png" alt="খোঁজো" className="h-16 w-auto mx-auto mb-4" />
          {/* Search Bar Section <p className="mt-2 text-sm text-gray-500 font-medium tracking-widest uppercase">
            Bangladesh's Own Search Engine 
          </p> */}
        </div>

        {/* Search Bar Section */}
        <SearchBar autoFocus className="w-full" />
      </div>

      {/* Footer */}
      <footer className="absolute bottom-0 left-0 right-0 bg-gray-100 border-t border-gray-200 px-8 py-4 text-xs text-gray-600">
        <div className="max-w-full flex justify-between items-center flex-wrap gap-6">
          <div className="flex space-x-6">
            <a href="#" className="hover:underline">সবসময়</a>
            <a href="#" className="hover:underline">বিজ্ঞাপন</a>
            <a href="#" className="hover:underline">ব্যবসা</a>
            <a href="#" className="hover:underline">আমাৰ কীভাবে কাজ করে</a>
          </div>
          <div className="flex space-x-6">
            <a href="#" className="hover:underline">গোপনীয়তা</a>
            <a href="#" className="hover:underline">শর্তাবলী</a>
            <a href="#" className="hover:underline">সেটিংস</a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
