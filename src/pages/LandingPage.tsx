import React from 'react';
import SearchBar from '../components/search/SearchBar';

const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col items-center justify-start bg-white px-4 pt-32">
      <div className="w-full max-w-2xl flex flex-col items-center space-y-8">
        {/* Logo Section */}
        <div className="text-center">
          <img src="/src/assets/logo.png" alt="খোঁজো" className="h-32 w-auto mx-auto" />
        </div>

        {/* Search Bar Section */}
        <SearchBar autoFocus className="w-full" />

        {/* Bangladesh Text */}
        <div className="text-center">
          <p className="text-sm text-gray-700 font-medium">বাংলাদেশ</p>
        </div>
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
