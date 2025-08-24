'use client'

import React, { useState, useEffect } from 'react';
import { Bar } from 'react-chartjs-2';
import toast from 'react-hot-toast';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { AiOutlineUserAdd, AiOutlineMail, AiOutlineClockCircle } from 'react-icons/ai';

// Register ChartJS components. This is necessary for the charts to work.
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
);

const AnalyticsDashboard = () => {
  const [dailyStats, setDailyStats] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [daysRange, setDaysRange] = useState(30);
  const [error, setError] = useState(null);

  // Use a useEffect hook to fetch data whenever the daysRange changes.
  useEffect(() => {
    fetchAnalyticsData();
  }, [daysRange]);

  // Function to retrieve the authentication token from local storage.
  const getAuthToken = () => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('token');
    }
    return null;
  };

  // Asynchronous function to fetch all analytics data.
  const fetchAnalyticsData = async () => {
    try {
      setLoading(true);
      setError(null);

      const token = getAuthToken();
      if (!token) {
        // Show an error toast if no token is found.
        const authError = 'No authentication token found. Please log in.';
        toast.error(authError);
        throw new Error(authError);
      }

      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      };

      // Fetch daily stats from the API.
      const statsResponse = await fetch(`http://localhost:8000/analytics/daily-stats?days=${daysRange}`, {
        headers: headers
      });

      if (!statsResponse.ok) {
        if (statsResponse.status === 401) {
          const authError = 'Authentication failed. Please log in again.';
          toast.error(authError);
          throw new Error(authError);
        }
        const fetchError = `Failed to fetch daily stats: ${statsResponse.statusText}`;
        toast.error(fetchError);
        throw new Error(fetchError);
      }

      const statsData = await statsResponse.json();
      setDailyStats(statsData);

      // Fetch summary data from the API.
      const summaryResponse = await fetch('http://localhost:8000/analytics/summary', {
        headers: headers
      });

      if (!summaryResponse.ok) {
        if (summaryResponse.status === 401) {
          const authError = 'Authentication failed. Please log in again.';
          toast.error(authError);
          throw new Error(authError);
        }
        const fetchError = `Failed to fetch summary: ${summaryResponse.statusText}`;
        toast.error(fetchError);
        throw new Error(fetchError);
      }

      const summaryData = await summaryResponse.json();
      setSummary(summaryData);

    } catch (error) {
      console.error('Error fetching analytics:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  // Prepare data for the bar chart.
  const chartData = {
    labels: dailyStats.map(stat => stat.date),
    datasets: [
      {
        label: 'Leads Generated',
        data: dailyStats.map(stat => stat.leads),
        backgroundColor: '#008080', // Teal
        borderRadius: 4,
      },
      {
        label: 'Emails Sent',
        data: dailyStats.map(stat => stat.emails_sent),
        backgroundColor: '#87CEEB', // Sky Blue
        borderRadius: 4,
      }
    ]
  };

  // Configure options for the chart.
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: '#334155', // slate-700
          font: {
            size: 14,
            family: 'Poppins'
          }
        },
      },
      title: {
        display: true,
        text: `Daily Leads & Emails (Last ${daysRange} Days)`,
        color: '#1f2937', // gray-800
        font: {
          size: 18,
          family: 'Poppins',
          weight: '600'
        }
      },
      tooltip: {
        backgroundColor: 'rgba(51, 65, 85, 0.9)', // slate-700
        titleColor: '#fff',
        bodyColor: '#fff',
        bodyFont: {
          size: 14
        },
        padding: 12,
        cornerRadius: 8,
      }
    },
    scales: {
      x: {
        title: {
          display: true,
          text: 'Date',
          color: '#475569', // slate-600
          font: {
            size: 14
          }
        },
        grid: {
          display: false,
        },
      },
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Count',
          color: '#475569', // slate-600
          font: {
            size: 14
          }
        },
        grid: {
          color: '#e2e8f0', // slate-200
        },
      }
    },
  };

  // Display a loading state while data is being fetched.
  if (loading) {
    return (
      <div className="flex justify-center items-center h-64 bg-white rounded-xl shadow-lg">
        <div className="text-xl text-slate-600 animate-pulse">Loading analytics...</div>
      </div>
    );
  }

  // Display an error message if the data fetching fails.
  if (error) {
    return (
      <div className="flex flex-col justify-center items-center h-64 bg-white rounded-xl shadow-lg">
        <div className="text-xl text-red-600 mb-4">
          Error: {error}
        </div>
        <button
          onClick={fetchAnalyticsData}
          className="px-6 py-3 bg-teal-600 text-white rounded-full font-semibold hover:bg-teal-700 transition-colors shadow-md"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 bg-slate-50 min-h-screen">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold text-slate-800 mb-8">Analytics Dashboard</h1>
        
        {/* Summary Cards */}
        {summary && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
            <div 
              className="bg-white rounded-xl shadow-lg p-6 flex items-center gap-4 border border-slate-200"
            >
              <div className="p-4 rounded-full bg-teal-100 text-teal-600">
                <AiOutlineUserAdd className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-sm font-medium text-slate-500 uppercase">Total Leads</h3>
                <p className="text-3xl font-bold text-teal-700 mt-1">{summary.total_leads}</p>
              </div>
            </div>
            
            <div 
              className="bg-white rounded-xl shadow-lg p-6 flex items-center gap-4 border border-slate-200"
            >
              <div className="p-4 rounded-full bg-sky-100 text-sky-600">
                <AiOutlineMail className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-sm font-medium text-slate-500 uppercase">Emails Sent</h3>
                <p className="text-3xl font-bold text-sky-700 mt-1">{summary.total_emails_sent}</p>
              </div>
            </div>

            <div 
              className="bg-white rounded-xl shadow-lg p-6 flex items-center gap-4 border border-slate-200"
            >
              <div className="p-4 rounded-full bg-orange-100 text-orange-600">
                <AiOutlineClockCircle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-sm font-medium text-slate-500 uppercase">Pending Leads</h3>
                <p className="text-3xl font-bold text-orange-700 mt-1">{summary.unsent_leads}</p>
              </div>
            </div>
          </div>
        )}

        {/* Chart and Date Range Selector */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-8 border border-slate-200">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-4 gap-4">
            <h2 className="text-xl font-semibold text-slate-800">Daily Statistics</h2>
            <select
              value={daysRange}
              onChange={(e) => setDaysRange(parseInt(e.target.value))}
              className="border border-slate-300 rounded-md px-3 py-2 text-slate-700 focus:outline-none focus:ring-2 focus:ring-teal-500 transition-colors"
            >
              <option value={7}>Last 7 Days</option>
              <option value={30}>Last 30 Days</option>
              <option value={90}>Last 90 Days</option>
            </select>
          </div>

          {/* Chart container */}
          <div className="h-80">
            <Bar data={chartData} options={chartOptions} />
          </div>
        </div>

        {/* Detailed Stats Table */}
        <div className="bg-white rounded-xl shadow-lg overflow-hidden border border-slate-200">
          <div className="px-6 py-4 border-b border-slate-200">
            <h2 className="text-xl font-semibold text-slate-800">Daily Breakdown</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Leads Generated
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Emails Sent
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {dailyStats.map((stat, index) => (
                  <tr key={index} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900">
                      {stat.date}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-teal-600 font-medium">
                      {stat.leads}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-sky-600 font-medium">
                      {stat.emails_sent}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalyticsDashboard;
