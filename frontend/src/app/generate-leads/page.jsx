'use client';

import React, { useState, useEffect, useRef } from 'react';
import toast, { Toaster } from 'react-hot-toast';

const GoogleMapsScraper = () => {
  const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL;

  // State for form inputs
  const [query, setQuery] = useState('');
  const [maxBusinesses, setMaxBusinesses] = useState(10);
  // State for scraping process
  const [isScraping, setIsScraping] = useState(false);
  const [scrapeProgress, setScrapeProgress] = useState({
    scraped: 0,
    total: 0,
    status: 'idle' // 'idle', 'starting', 'in_progress', 'complete', 'error'
  });
  // State for displaying leads
  const [recentLeads, setRecentLeads] = useState([]);
  const [isLoadingLeads, setIsLoadingLeads] = useState(true);

  // Use a ref to hold the polling interval so we can clear it later.
  const pollingIntervalRef = useRef(null);

  // Helper function to get the authentication token from local storage.
  const getAuthToken = () => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('token');
    }
    return null;
  };

  // Effect to fetch recent leads on component mount and whenever a scrape completes.
  useEffect(() => {
    fetchRecentLeads();

    // Cleanup function for the interval on component unmount.
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  /**
   * Fetches the 10 most recent unsent leads from the backend API.
   * Displays an error toast if the fetch fails.
   */
  const fetchRecentLeads = async () => {
    try {
      setIsLoadingLeads(true);
      const token = getAuthToken();
      if (!token) {
        throw new Error('No authentication token found. Please log in.');
      }

      const response = await fetch(`${BASE_URL}/leads?limit=10&sent=false`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        }
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication failed. Please log in again.');
        }
        throw new Error(`Failed to fetch leads: ${response.statusText}`);
      }

      const leads = await response.json();
      setRecentLeads(leads);
    } catch (error) {
      console.error('Failed to fetch leads:', error);
      toast.error(error.message || 'Failed to load recent leads');
    } finally {
      setIsLoadingLeads(false);
    }
  };

  /**
   * Starts the Google Maps scraping process by making a POST request to the backend.
   * Handles validation and updates the UI state.
   */
  const startScraping = async () => {
    // Input validation
    if (!query.trim()) {
      toast.error('Please enter a search query');
      return;
    }
    if (maxBusinesses < 1 || maxBusinesses > 100) {
      toast.error('Please enter a number between 1 and 100');
      return;
    }
    const token = getAuthToken();
    if (!token) {
      toast.error('Please log in to start scraping');
      return;
    }

    // Set UI state to indicate scraping has started
    setIsScraping(true);
    setScrapeProgress({
      scraped: 0,
      total: maxBusinesses,
      status: 'starting'
    });

    try {
      const response = await fetch(`${BASE_URL}/scrape-google-maps`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          query: query.trim(),
          max_businesses: maxBusinesses
        })
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication failed. Please log in again.');
        }
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to start scraping: ${response.statusText}`);
      }

      const result = await response.json();
      toast.success(result.message);
      setScrapeProgress(prev => ({
        ...prev,
        status: 'in_progress'
      }));

      // Start polling for progress after a successful API call
      startProgressPolling(maxBusinesses);
    } catch (error) {
      toast.error(error.message || 'Failed to start scraping');
      setIsScraping(false);
      setScrapeProgress({
        scraped: 0,
        total: 0,
        status: 'error'
      });
    }
  };

  /**
   * Polls the backend API at a regular interval to check for scraping progress.
   * Clears the interval when the scraping is complete or an error occurs.
   */
  const startProgressPolling = (total) => {
    // Clear any existing interval to prevent multiple polling loops.
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    const intervalId = setInterval(async () => {
      try {
        const token = getAuthToken();
        if (!token) {
          clearInterval(intervalId);
          toast.error('Authentication lost. Please log in again.');
          return;
        }

        // Get count of unsent leads (newly scraped ones)
        const countRes = await fetch(`${BASE_URL}/leads/count?sent=false`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          }
        });

        if (!countRes.ok) {
          if (countRes.status === 401) {
            clearInterval(intervalId);
            toast.error('Authentication failed. Please log in again.');
            return;
          }
          throw new Error(`Failed to fetch lead count: ${countRes.statusText}`);
        }

        const countData = await countRes.json();
        const newLeads = countData.count;

        // Update the progress state
        setScrapeProgress(prev => {
          const newProgress = {
            ...prev,
            scraped: newLeads,
            total: total
          };

          // Check for completion criteria
          if (newLeads >= total) {
            newProgress.status = 'complete';
            return newProgress;
          } else {
            return newProgress;
          }
        });

        // Check again after state update to see if we should stop polling
        if (newLeads >= total) {
          setIsScraping(false);
          clearInterval(intervalId);
          fetchRecentLeads(); // Fetch the new leads to display in the table
          toast.success(`Scraping completed! Found ${newLeads} businesses.`);
        }
      } catch (error) {
        console.error('Error polling progress:', error);
        toast.error(error.message || 'An error occurred during scraping.');
        setIsScraping(false);
        clearInterval(intervalId);
        setScrapeProgress({
          scraped: 0,
          total: 0,
          status: 'error'
        });
      }
    }, 3000); // Poll every 3 seconds

    pollingIntervalRef.current = intervalId;
  };

  /**
   * Returns a user-friendly status message based on the scraping progress.
   */
  const getStatusMessage = () => {
    switch (scrapeProgress.status) {
      case 'starting':
        return 'Starting scraping process...';
      case 'in_progress':
        return `Scraping in progress: ${scrapeProgress.scraped}/${scrapeProgress.total} businesses found`;
      case 'complete':
        return `Scraping complete! Found ${scrapeProgress.scraped} businesses.`;
      case 'error':
        return 'Scraping failed. Please try again.';
      default:
        return 'Ready to start scraping';
    }
  };

  /**
   * Calculates the percentage of scraping progress for the progress bar.
   */
  const getProgressPercentage = () => {
    if (scrapeProgress.total === 0) return 0;
    return Math.min(100, (scrapeProgress.scraped / scrapeProgress.total) * 100);
  };

  /**
   * Helper function to format phone numbers for display.
   */
  const formatPhoneNumber = (phone) => {
    return phone && phone !== 'Not found' ? phone : 'N/A';
  };

  /**
   * Helper function to truncate long text strings for table display.
   */
  const truncateText = (text, maxLength = 25) => {
    if (!text) return 'N/A';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6 sm:p-8 font-sans">
      <Toaster position="top-right" />

      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Google Maps Scraper 🗺️</h1>
          <p className="text-gray-600">Find and extract business contact information from Google Maps.</p>
        </div>

        {/* Scraping Form */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-lg p-6 mb-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-6 flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6 text-indigo-600">
              <path fillRule="evenodd" d="M10.5 3.75a6.75 6.75 0 1 0 0 13.5 6.75 6.75 0 0 0 0-13.5ZM2.25 10.5a8.25 8.25 0 1 1 14.59 5.28l4.698 4.698a.75.75 0 1 1-1.06 1.06l-4.698-4.698A8.25 8.25 0 0 1 2.25 10.5Z" clipRule="evenodd" />
            </svg>
            Start a New Search
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Search Query
              </label>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g., 'restaurants in London'"
                className="w-full rounded-lg border-gray-300 shadow-sm p-3 border focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                disabled={isScraping}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Number of Businesses
              </label>
              <input
                type="number"
                value={maxBusinesses}
                onChange={(e) =>
                  setMaxBusinesses(Math.max(1, Math.min(100, parseInt(e.target.value) || 1)))
                }
                min="1"
                max="100"
                className="w-full rounded-lg border-gray-300 shadow-sm p-3 border focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                disabled={isScraping}
              />
            </div>
          </div>

          <div className="mt-6">
            <button
              onClick={startScraping}
              disabled={isScraping || !query.trim()}
              className="w-full bg-indigo-600 text-white py-3 px-6 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 font-medium shadow-md"
            >
              {isScraping ? (
                <div className="flex items-center justify-center">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                  Scraping...
                </div>
              ) : (
                'Start Scraping'
              )}
            </button>
          </div>

          {/* Progress Section */}
          {(isScraping || scrapeProgress.status !== 'idle') && (
            <div className="mt-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div className="flex justify-between items-center mb-3">
                <span className="text-sm font-medium text-gray-700">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 inline-block mr-1 text-gray-500">
                    <path fillRule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25ZM12.75 6a.75.75 0 0 0-1.5 0v6a.75.75 0 0 0 .231.53l5.004 5.005a.75.75 0 0 0 1.06-1.06l-4.25-4.249V6Z" clipRule="evenodd" />
                  </svg>
                  {getStatusMessage()}
                </span>
                <span className="text-sm text-gray-600 font-semibold">
                  {Math.round(getProgressPercentage())}%
                </span>
              </div>

              <div className="w-full bg-gray-200 rounded-full h-2.5 mb-3">
                <div
                  className="bg-indigo-600 h-2.5 rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${getProgressPercentage()}%` }}
                ></div>
              </div>
              
              <div className="text-xs text-gray-500 space-y-1">
                <p>• This may take several minutes depending on the number of businesses.</p>
                <p>• Do not close this window while scraping is in progress.</p>
              </div>
            </div>
          )}
        </div>

        {/* Recent Leads Section */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-lg p-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-6 flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6 text-indigo-600">
              <path fillRule="evenodd" d="M11.54 22.351A8.25 8.25 0 0 1 18 20.25h.75a6 6 0 0 0 0-12H18a8.25 8.25 0 0 1-6.46-2.851A8.25 8.25 0 0 0 5.25 6.75v1.5a.75.75 0 0 1-1.5 0v-1.5a8.25 8.25 0 0 1 8.25-8.25Z" clipRule="evenodd" />
              <path fillRule="evenodd" d="M12 11.25a.75.75 0 0 1 .75.75v5.757l2.247-2.248a.75.75 0 0 1 1.06 1.06l-3.5 3.5a.75.75 0 0 1-1.06 0l-3.5-3.5a.75.75 0 1 1 1.06-1.06l2.248 2.247V12a.75.75 0 0 1 .75-.75Z" clipRule="evenodd" />
            </svg>
            Recent Leads
          </h2>
          
          {isLoadingLeads ? (
            <div className="flex justify-center items-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            </div>
          ) : recentLeads.length > 0 ? (
            <>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Company
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Phone
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Email
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {recentLeads.map((lead, index) => (
                      <tr key={index} className="hover:bg-gray-50 transition-colors">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900">
                            {truncateText(lead.company_name, 30)}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {formatPhoneNumber(lead.contact_number)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {truncateText(lead.email, 25)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                            lead.mail_sent 
                              ? 'bg-green-100 text-green-800' 
                              : 'bg-yellow-100 text-yellow-800'
                          }`}>
                            {lead.mail_sent ? 'Sent' : 'Pending'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="text-center py-8">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="mx-auto h-12 w-12 text-gray-400">
                <path d="M11.47 1.72a.75.75 0 0 0-1.06 0L1.97 9.18a.75.75 0 0 0 1.06 1.06l.72-.72v5.19a3 3 0 0 0 3 3h5.25a.75.75 0 0 0 0-1.5H7.75a1.5 1.5 0 0 1-1.5-1.5v-5.19l3.72 3.72a.75.75 0 0 0 1.06 0l5.25-5.25Zm0 12.72v4.56a3 3 0 0 0 3 3h5.25a.75.75 0 0 0 0-1.5h-5.25a1.5 1.5 0 0 1-1.5-1.5v-4.56l3.72 3.72a.75.75 0 0 0 1.06 0l.72-.72a.75.75 0 0 0 0-1.06l-5.25-5.25a.75.75 0 0 0-1.06 0l-.72.72v-1.94a3 3 0 0 0-3-3h-5.25a.75.75 0 0 0 0 1.5H5.75a1.5 1.5 0 0 1 1.5 1.5v1.94l-3.72-3.72a.75.75 0 0 0-1.06 0L1.97 9.18a.75.75 0 0 0 1.06 1.06l.72-.72v5.19a3 3 0 0 0 3 3h5.25a.75.75 0 0 0 0-1.5h-5.25a1.5 1.5 0 0 1-1.5-1.5v-5.19l3.72 3.72a.75.75 0 0 0 1.06 0Z" />
              </svg>
              <h3 className="mt-2 text-sm font-medium text-gray-900">No leads yet</h3>
              <p className="mt-1 text-sm text-gray-500">
                Start scraping to find businesses and generate leads.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default GoogleMapsScraper;
