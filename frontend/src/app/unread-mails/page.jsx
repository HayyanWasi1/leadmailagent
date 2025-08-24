'use client'
import { useState } from 'react';

function UnreadEmailsPage() {
  const [unreadEmails, setUnreadEmails] = useState([]);
  const [loading, setLoading] = useState(false);
  
  const checkForReplies = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://127.0.0.1:8000/unread-emails', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        const emails = await response.json();
        setUnreadEmails(emails);
      } else {
        alert('Failed to check for replies');
      }
    } catch (error) {
      console.error('Error:', error);
      alert('Error checking for replies');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Unread Emails</h1>
      
      <button 
        onClick={checkForReplies}
        disabled={loading}
        className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded mb-4"
      >
        {loading ? 'Checking...' : 'Check for Replies'}
      </button>
      
      {unreadEmails.length === 0 ? (
        <p>No unread emails found. Click the button above to check.</p>
      ) : (
        <div className="space-y-4">
          {unreadEmails.map((email, index) => (
            <div key={index} className="border p-4 rounded">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-bold">{email.sender_email}</h3>
                  <p className="text-gray-600">To: {email.recipient_email}</p>
                  <p className="text-sm text-gray-500">{email.time}</p>
                </div>
                <span className="bg-red-100 text-red-800 text-xs font-medium px-2.5 py-0.5 rounded">
                  Unread
                </span>
              </div>
              <h4 className="font-semibold mt-2">{email.subject}</h4>
              <p className="text-gray-700 mt-1">{email.preview}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default UnreadEmailsPage;