'use client';

import React, { useState } from 'react';
import toast, { Toaster } from 'react-hot-toast';

function UnreadEmailsPage() {
  const [unreadEmails, setUnreadEmails] = useState([]);
  const [loading, setLoading] = useState(false);

  /**
   * Fetches unread emails from the backend API.
   * Uses react-hot-toast for user-friendly, non-blocking notifications.
   */
  const checkForReplies = async () => {
    setLoading(true);
    try {
      // Get the authentication token securely
      const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
      if (!token) {
        toast.error('Authentication token not found. Please log in.');
        setLoading(false);
        return;
      }

      const response = await fetch('http://127.0.0.1:8000/unread-emails', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        const emails = await response.json();
        setUnreadEmails(emails);
        if (emails.length > 0) {
          toast.success(`Found ${emails.length} new unread emails!`);
        } else {
          toast('No new replies found.', { icon: '👏' });
        }
      } else {
        toast.error('Failed to check for replies.');
      }
    } catch (error) {
      console.error('Error:', error);
      toast.error('Error checking for replies.');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="min-h-screen bg-gray-50 p-6 sm:p-8 font-sans">
      <Toaster position="top-right" />
      <div className="max-w-4xl mx-auto">
        
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-gray-800">Emails</h1>
          <button 
            onClick={checkForReplies}
            disabled={loading}
            className="flex items-center gap-2 bg-indigo-600 text-white font-semibold py-2 px-5 rounded-lg shadow-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Checking...
              </>
            ) : (
              <>
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                  <path d="M1.5 8.67v8.586a.75.75 0 0 0 1.258.558L8.75 13.916V9.456a.75.75 0 0 0-.544-.721L1.5 8.67ZM12 6a.75.75 0 0 1 .75-.75h5.586a.75.75 0 0 1 .53.22L22.5 9.456a.75.75 0 0 1-.544.721L18 10.422V6.75A.75.75 0 0 1 18.75 6H20a.75.75 0 0 0 0-1.5h-.54a.75.75 0 0 1-.53-.22L12.5 1.77a.75.75 0 0 0-1.06 0L1.72 9.18a.75.75 0 0 0 1.06 1.06l.72-.72v-1.94a3 3 0 0 0-3-3h-5.25a.75.75 0 0 0 0 1.5H5.75a1.5 1.5 0 0 1 1.5 1.5v5.19l3.72-3.72a.75.75 0 0 0 1.06 0Z" />
                  <path d="m14.25 15.654-.784 1.408A.75.75 0 0 0 14.25 18H22a.75.75 0 0 0 .75-.75v-1.5a.75.75 0 0 0-1.5 0v1.179l-4.22-3.798A3.75 3.75 0 0 0 12 10.975v-.016h-.016A3.75 3.75 0 0 0 8.25 14.25v2.25a.75.75 0 0 0 1.5 0v-2.25a2.25 2.25 0 0 1 2.25-2.25h.016a2.25 2.25 0 0 1 2.234 2.181Z" />
                </svg>
                Check for Replies
              </>
            )}
          </button>
        </div>
        
        {/* Content Area */}
        {unreadEmails.length === 0 ? (
          <div className="bg-white rounded-lg p-8 text-center shadow-sm border border-gray-200">
            <svg className="mx-auto h-12 w-12 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No unread emails</h3>
            <p className="mt-1 text-sm text-gray-500">
              Click the button above to check for new replies.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {unreadEmails.map((email, index) => (
              <div key={index} className="bg-white rounded-lg p-5 border border-gray-200 shadow-sm transition-transform hover:scale-[1.01] hover:shadow-lg">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <h3 className="text-lg font-bold text-gray-800">{email.sender_email}</h3>
                    <p className="text-sm text-gray-600">to: {email.recipient_email}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-gray-500 mt-1">{email.time}</p>
                  </div>
                </div>
                <h4 className="text-md font-semibold text-gray-900 mt-2">{email.subject}</h4>
                <p className="text-gray-700 mt-2 text-sm leading-relaxed">
                  {email.preview}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default UnreadEmailsPage;
