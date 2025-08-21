'use client'
import React, { useState, useEffect } from 'react';
import { Bar, Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
} from 'chart.js';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  TimeScale
);

const AnalyticsDashboard = () => {
  const [dailyStats, setDailyStats] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [daysRange, setDaysRange] = useState(30);

  useEffect(() => {
    fetchAnalyticsData();
  }, [daysRange]);

  const fetchAnalyticsData = async () => {
    try {
      setLoading(true);
      
      // Fetch daily stats
      const statsResponse = await fetch(`http://localhost:8000/analytics/daily-stats?days=${daysRange}`);
      const statsData = await statsResponse.json();
      setDailyStats(statsData);
      
      // Fetch summary
      const summaryResponse = await fetch('http://localhost:8000/analytics/summary');
      const summaryData = await summaryResponse.json();
      setSummary(summaryData);
      
    } catch (error) {
      console.error('Error fetching analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  // Prepare chart data
  const chartData = {
    labels: dailyStats.map(stat => stat.date),
    datasets: [
      {
        label: 'Leads Generated',
        data: dailyStats.map(stat => stat.leads),
        backgroundColor: 'rgba(54, 162, 235, 0.6)',
        borderColor: 'rgba(54, 162, 235, 1)',
        borderWidth: 2,
        yAxisID: 'y',
      },
      {
        label: 'Emails Sent',
        data: dailyStats.map(stat => stat.emails_sent),
        backgroundColor: 'rgba(75, 192, 192, 0.6)',
        borderColor: 'rgba(75, 192, 192, 1)',
        borderWidth: 2,
        yAxisID: 'y',
      }
    ]
  };

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: `Daily Leads & Emails (Last ${daysRange} Days)`,
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: 'Date'
        }
      },
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Count'
        }
      }
    },
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-lg text-gray-600">Loading analytics...</div>
      </div>
    );
  }

  return (
    <div className="p-6 bg-gray-50 min-h-screen">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Analytics Dashboard</h1>
        
        {/* Summary Cards */}
        {summary && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-700 mb-2">Total Leads</h3>
              <p className="text-3xl font-bold text-blue-600">{summary.total_leads}</p>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-700 mb-2">Emails Sent</h3>
              <p className="text-3xl font-bold text-green-600">{summary.total_emails_sent}</p>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-700 mb-2">Pending Leads</h3>
              <p className="text-3xl font-bold text-orange-600">{summary.unsent_leads}</p>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-700 mb-2">Success Rate</h3>
              <p className="text-3xl font-bold text-purple-600">
                {summary.success_rate.toFixed(1)}%
              </p>
            </div>
          </div>
        )}

        {/* Date Range Selector */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-800">Daily Statistics</h2>
            <select
              value={daysRange}
              onChange={(e) => setDaysRange(parseInt(e.target.value))}
              className="border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value={7}>Last 7 Days</option>
              <option value={30}>Last 30 Days</option>
              <option value={90}>Last 90 Days</option>
            </select>
          </div>

          {/* Chart */}
          <div className="h-96">
            <Bar data={chartData} options={chartOptions} />
          </div>
        </div>

        {/* Detailed Stats Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-800">Daily Breakdown</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Leads Generated
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Emails Sent
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {dailyStats.map((stat, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {stat.date}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-blue-600 font-medium">
                      {stat.leads}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-green-600 font-medium">
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