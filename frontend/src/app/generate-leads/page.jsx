'use client';
import { useState, useEffect } from 'react';
import Head from 'next/head';
import toast, { Toaster } from 'react-hot-toast';

export default function BingMapsScraper() {
  const [query, setQuery] = useState('');
  const [maxBusinesses, setMaxBusinesses] = useState(10);
  const [isScraping, setIsScraping] = useState(false);
  const [scrapeProgress, setScrapeProgress] = useState({
    scraped: 0,
    total: 0,
    status: 'idle'
  });
  const [recentLeads, setRecentLeads] = useState([]);
  const [isLoadingLeads, setIsLoadingLeads] = useState(true);

  useEffect(() => {
    fetchRecentLeads();
  }, []);

  const fetchRecentLeads = async () => {
    try {
      setIsLoadingLeads(true);
      const response = await fetch('http://127.0.0.1:8000/leads?limit=10&sent=false');
      const leads = await response.json();
      setRecentLeads(leads);
    } catch (error) {
      console.error('Failed to fetch leads:', error);
      toast.error('Failed to load recent leads');
    } finally {
      setIsLoadingLeads(false);
    }
  };

  const startScraping = async () => {
    if (!query.trim()) {
      toast.error('Please enter a search query');
      return;
    }

    if (maxBusinesses < 1 || maxBusinesses > 100) {
      toast.error('Please enter a number between 1 and 100');
      return;
    }

    setIsScraping(true);
    setScrapeProgress({
      scraped: 0,
      total: maxBusinesses,
      status: 'starting'
    });

    try {
      const response = await fetch('http://127.0.0.1:8000/scrape-bing-maps', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query.trim(),
          max_businesses: maxBusinesses
        })
      });

      const result = await response.json();
      if (response.ok) {
        toast.success(result.message);
        setScrapeProgress(prev => ({
          ...prev,
          status: 'in_progress'
        }));

        // Start polling for progress
        startProgressPolling(maxBusinesses);
      } else {
        throw new Error(result.detail || 'Failed to start scraping');
      }
    } catch (error) {
      toast.error(`Failed to start scraping: ${error.message}`);
      setIsScraping(false);
      setScrapeProgress({
        scraped: 0,
        total: 0,
        status: 'error'
      });
    }
  };

  const startProgressPolling = (total) => {
    const interval = setInterval(async () => {
      try {
        // Get count of unsent leads (newly scraped ones)
        const countRes = await fetch('http://127.0.0.1:8000/leads/count?sent=false');
        const countData = await countRes.json();
        const newLeads = countData.count;

        let shouldComplete = false;

        setScrapeProgress(prev => {
          const newProgress = {
            ...prev,
            scraped: newLeads,
            total: total
          };

          if (newLeads >= total || prev.scraped === newLeads) {
            if (prev.scraped === newLeads && prev.status === 'in_progress') {
              newProgress.status = 'complete';
              shouldComplete = true;
            }
          }
          return newProgress;
        });

        // ✅ side effects outside setState
        if (shouldComplete) {
          setIsScraping(false);
          clearInterval(interval);
          fetchRecentLeads();
          toast.success(`Scraping completed! Found ${newLeads} businesses`);
        }
      } catch (error) {
        console.error('Error polling progress:', error);
        clearInterval(interval);
      }
    }, 3000); // Poll every 3 seconds
  };

  const getStatusMessage = () => {
    switch (scrapeProgress.status) {
      case 'starting':
        return 'Starting scraping process...';
      case 'in_progress':
        return `Scraping in progress: ${scrapeProgress.scraped}/${scrapeProgress.total} businesses found`;
      case 'complete':
        return `Scraping complete! Found ${scrapeProgress.scraped} businesses`;
      case 'error':
        return 'Scraping failed. Please try again.';
      default:
        return 'Ready to start scraping';
    }
  };

  const getProgressPercentage = () => {
    if (scrapeProgress.total === 0) return 0;
    return Math.min(100, (scrapeProgress.scraped / scrapeProgress.total) * 100);
  };

  const formatPhoneNumber = (phone) => {
    if (!phone || phone === 'Not found') return 'N/A';
    return phone;
  };

  const truncateText = (text, maxLength = 25) => {
    if (!text) return 'N/A';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <Head>
        <title>Bing Maps Scraper - Email Agent</title>
      </Head>
      <Toaster position="top-right" />

      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Bing Maps Scraper</h1>
          <p className="text-gray-600">Find businesses and extract contact information from Bing Maps</p>
        </div>

        {/* Scraping Form */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-6">Start New Scraping</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Search Query *
              </label>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g., 'restaurants in London', 'dentists in New York'"
                className="w-full rounded-md border-gray-300 shadow-sm p-3 border focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                disabled={isScraping}
              />
              <p className="text-xs text-gray-500 mt-1">
                What type of businesses are you looking for?
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Number of Businesses *
              </label>
              <input
                type="number"
                value={maxBusinesses}
                onChange={(e) =>
                  setMaxBusinesses(Math.max(1, Math.min(100, parseInt(e.target.value) || 1)))
                }
                min="1"
                max="100"
                className="w-full rounded-md border-gray-300 shadow-sm p-3 border focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                disabled={isScraping}
              />
              <p className="text-xs text-gray-500 mt-1">
                Maximum 100 businesses per search
              </p>
            </div>
          </div>

          <div className="mt-6">
            <button
              onClick={startScraping}
              disabled={isScraping || !query.trim()}
              className="w-full bg-indigo-600 text-white py-3 px-6 rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 font-medium"
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
          {(isScraping || scrapeProgress.status === 'complete') && (
            <div className="mt-6 p-4 bg-gray-50 rounded-lg border">
              <div className="flex justify-between items-center mb-3">
                <span className="text-sm font-medium text-gray-700">
                  {getStatusMessage()}
                </span>
                <span className="text-sm text-gray-600">
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
                <p>• This may take several minutes depending on the number of businesses</p>
                <p>• Do not close this window while scraping is in progress</p>
                <p>• Results will be automatically saved to your leads database</p>
              </div>

              {scrapeProgress.status === 'complete' && (
                <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-md">
                  <div className="flex items-center">
                    <svg className="w-5 h-5 text-green-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span className="text-green-800 font-medium">Scraping completed successfully!</span>
                  </div>
                  <p className="text-green-700 text-sm mt-1">
                    Found {scrapeProgress.scraped} businesses. You can now send emails from the main dashboard.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {recentLeads.length > 0 && (
            <div className="mt-4 flex justify-between items-center text-sm text-gray-500">
              <span>Showing {recentLeads.length} most recent leads</span>
              <a
                href="/send-emails"
                className="text-indigo-600 hover:text-indigo-700 font-medium"
              >
                Go to Email Dashboard →
              </a>
            </div>
          )}
      </div>
    </div>
  );
}
