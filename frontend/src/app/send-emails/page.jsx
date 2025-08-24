'use client';
import { useState, useEffect } from 'react';
import Head from 'next/head';
import toast, { Toaster } from 'react-hot-toast';

export default function SendEmails() {
  const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL;

  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [emailContent, setEmailContent] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [totalLeads, setTotalLeads] = useState(0);
  const [emailsToSend, setEmailsToSend] = useState(0);
  const [distribution, setDistribution] = useState([{ templateId: '', count: 0 }]);
  const [showNewTemplateModal, setShowNewTemplateModal] = useState(false);
  const [newTemplatePrompt, setNewTemplatePrompt] = useState('');
  const [templates, setTemplates] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showProgressModal, setShowProgressModal] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentEmail, setCurrentEmail] = useState(0);
  const [totalEmails, setTotalEmails] = useState(0);
  const [attachments, setAttachments] = useState([]);
  const [emailAccounts, setEmailAccounts] = useState([]);
  const [selectedAccounts, setSelectedAccounts] = useState([]);
  const [showEmailAccountsModal, setShowEmailAccountsModal] = useState(false);
  const [newEmailAccount, setNewEmailAccount] = useState({
    email: '',
    password: '',
    sender_name: '',
    daily_limit: 0
  });
  
  // New state for manual lead addition
  const [showAddLeadModal, setShowAddLeadModal] = useState(false);
  const [newLead, setNewLead] = useState({
    company_name: '',
    contact_number: '',
    email: '',
    owner_name: ''
  });

  // Function to get auth token from localStorage
  const getAuthToken = () => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('token');
    }
    return null;
  };

  // Function to get headers with authentication
  const getAuthHeaders = () => {
    const token = getAuthToken();
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const token = getAuthToken();
        if (!token) {
          throw new Error('No authentication token found');
        }

        const headers = {
          'Authorization': `Bearer ${token}`,
        };

        const [templatesRes, countRes, accountsRes] = await Promise.all([
          fetch(`${BASE_URL}/templates`, { headers }),
          fetch(`${BASE_URL}/leads/count?sent=false`, { headers }), // ✅ add sent=false
          fetch(`${BASE_URL}/email-accounts`, { headers })
        ]);

        if (!templatesRes.ok) {
          if (templatesRes.status === 401) {
            throw new Error('Authentication failed. Please log in again.');
          }
          throw new Error(`Failed to load templates: ${templatesRes.statusText}`);
        }

        if (!countRes.ok) {
          if (countRes.status === 401) {
            throw new Error('Authentication failed. Please log in again.');
          }
          throw new Error(`Failed to load lead count: ${countRes.statusText}`);
        }

        if (!accountsRes.ok) {
          if (accountsRes.status === 401) {
            throw new Error('Authentication failed. Please log in again.');
          }
          throw new Error(`Failed to load email accounts: ${accountsRes.statusText}`);
        }

        const templatesData = await templatesRes.json();
        const countData = await countRes.json();
        const accountsData = await accountsRes.json();

        setTemplates(templatesData);
        setSelectedTemplate(templatesData[0]);
        setEmailContent(templatesData[0]?.content || '');
        setDistribution([{ templateId: templatesData[0]?.id || '', count: 0 }]);

        setTotalLeads(countData.count);
        setEmailAccounts(accountsData);
        setSelectedAccounts(accountsData.map(acc => acc.id));

        setIsLoading(false);
      } catch (error) {
        toast.error(error.message || 'Failed to load data');
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleFileUpload = (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    const newAttachments = [];

    files.forEach(file => {
      if (file.type !== 'application/pdf') {
        toast.error('Only PDF files are allowed');
        return;
      }

      const reader = new FileReader();
      reader.onload = (event) => {
        const base64Content = event.target.result.split(',')[1];
        newAttachments.push({
          filename: file.name,
          content: base64Content
        });

        if (newAttachments.length === files.length) {
          setAttachments(prev => [...prev, ...newAttachments]);
        }
      };
      reader.readAsDataURL(file);
    });
  };

  // Update the handleSendEmails function
  const handleSendEmails = async () => {
    const token = getAuthToken();
    if (!token) {
      toast.error('Please log in to send emails');
      return;
    }

    setIsSending(true);
    setShowProgressModal(true);
    setProgress(0);
    setCurrentEmail(0);

    try {
      const headers = {
        'Authorization': `Bearer ${token}`,
      };

      // Get only unsent leads
      const leadsRes = await fetch(`${BASE_URL}/leads?sent=false&limit=1000`, { headers });

      if (!leadsRes.ok) {
        if (leadsRes.status === 401) {
          throw new Error('Authentication failed. Please log in again.');
        }
        throw new Error(`Failed to fetch leads: ${leadsRes.statusText}`);
      }

      const unsentLeads = await leadsRes.json();

      // Filter out leads without email addresses
      const leadsWithEmail = unsentLeads.filter(lead => lead.email && lead.email.trim() !== '');

      if (leadsWithEmail.length === 0) {
        throw new Error('No leads with valid email addresses available to send');
      }

      const leadsToSend = [];
      let remainingLeads = [...leadsWithEmail];

      for (const dist of distribution) {
        if (dist.count <= 0) continue;
        const templateLeads = remainingLeads.splice(0, dist.count);
        leadsToSend.push(
          ...templateLeads.map((lead) => ({
            lead_id: lead.id,
            template_id: dist.templateId,
          }))
        );
      }

      if (leadsToSend.length === 0) {
        throw new Error('No valid leads selected for sending');
      }

      setTotalEmails(leadsToSend.length);

      // Send all emails at once using the new bulk endpoint
      const response = await fetch(`${BASE_URL}/send-emails`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          template_id: distribution[0].templateId,
          lead_ids: leadsToSend.map(item => item.lead_id),
          attachments: attachments.length > 0 ? attachments : undefined,
          email_account_ids: selectedAccounts
        }),
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication failed. Please log in again.');
        }
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to send emails: ${response.statusText}`);
      }

      const result = await response.json();

      if (result.status === 'queued') {
        // Poll for completion
        let attempts = 0;
        const maxAttempts = 60; // 5 minutes max
        let isComplete = false;

        while (attempts < maxAttempts && !isComplete) {
          await new Promise(resolve => setTimeout(resolve, 5000)); // Check every 5 seconds

          const countRes = await fetch(`${BASE_URL}/leads/count?sent=false`, { headers });

          if (!countRes.ok) {
            if (countRes.status === 401) {
              throw new Error('Authentication failed. Please log in again.');
            }
            throw new Error(`Failed to fetch lead count: ${countRes.statusText}`);
          }

          const countData = await countRes.json();
          const remainingLeadsCount = countData.count;
          const sentCount = totalLeads - remainingLeadsCount;
          const currentProgress = Math.min(100, Math.round((sentCount / leadsToSend.length) * 100));

          setCurrentEmail(sentCount);
          setProgress(currentProgress);

          if (sentCount >= leadsToSend.length || currentProgress === 100) {
            isComplete = true;
            break;
          }

          attempts++;
        }

        // Update total leads count
        const finalCountRes = await fetch(`${BASE_URL}/leads/count?sent=false`, { headers });
        if (finalCountRes.ok) {
          const finalCountData = await finalCountRes.json();
          setTotalLeads(finalCountData.count);
        }

        toast.success(`Successfully sent ${leadsToSend.length} emails`);
      } else {
        throw new Error(result.message || 'Failed to send emails');
      }
    } catch (error) {
      toast.error(error.message || 'Failed to send emails');
    } finally {
      setIsSending(false);
      // Close modal after a short delay to show completion
      setTimeout(() => {
        setShowProgressModal(false);
        setProgress(0);
        setCurrentEmail(0);
      }, 2000);
    }
  };

  // Add a cleanup function to handle modal closing
  useEffect(() => {
    if (!showProgressModal && progress === 100) {
      // Reset progress when modal is closed
      setProgress(0);
      setCurrentEmail(0);
    }
  }, [showProgressModal, progress]);

  const handleRephrase = async () => {
    if (!selectedTemplate) return;

    const token = getAuthToken();
    if (!token) {
      toast.error('Please log in to rephrase emails');
      return;
    }

    console.log('Selected template:', selectedTemplate); // Debug log
    console.log('Auth token:', token); // Debug log

    const toastId = toast.loading('Rephrasing email...');
    try {
      const response = await fetch(`${BASE_URL}/rephrase-email`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          template_id: selectedTemplate.id,
          content: emailContent
        }),
      });

      console.log('Response status:', response.status); // Debug log

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error('Error details:', errorData); // Debug log

        if (response.status === 401) {
          throw new Error('Authentication failed. Please log in again.');
        }
        throw new Error(errorData.detail || `Rephrasing failed: ${response.status}`);
      }

      const result = await response.json();
      // ... rest of the function
    } catch (error) {
      console.error('Rephrase error:', error);
      toast.error(error.message || 'Failed to rephrase email', { id: toastId });
    }
  };

  const handleAddDistribution = () => {
    if (templates.length > 0) {
      setDistribution([...distribution, { templateId: templates[0].id, count: 0 }]);
    }
  };

  const handleDistributionChange = (index, field, value) => {
    const newDistribution = [...distribution];
    newDistribution[index][field] = field === 'count' ? parseInt(value) || 0 : value;

    const totalSelected = newDistribution.reduce((sum, item) => sum + item.count, 0);
    const remainingLeads = totalLeads - totalSelected;

    if (remainingLeads < 0) {
      newDistribution[index].count = Math.max(0, newDistribution[index].count + remainingLeads);
    }

    setEmailsToSend(newDistribution.reduce((sum, item) => sum + item.count, 0));
    setDistribution(newDistribution);
  };

  const handleGenerateNewTemplate = async () => {
    const token = getAuthToken();
    if (!token) {
      toast.error('Please log in to create templates');
      return;
    }

    const toastId = toast.loading('Creating template...');
    try {
      const response = await fetch(`${BASE_URL}/templates`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: `Custom ${templates.length + 1}`,
          subject: `Regarding ${newTemplatePrompt.substring(0, 20)}`,
          content: `Hi {First Name},\n\n${newTemplatePrompt}\n\nBest,\nYour Team`
        }),
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication failed. Please log in again.');
        }
        throw new Error('Failed to create template');
      }

      const savedTemplate = await response.json();
      setTemplates([...templates, savedTemplate]);
      setSelectedTemplate(savedTemplate);
      setEmailContent(savedTemplate.content);
      setShowNewTemplateModal(false);
      setNewTemplatePrompt('');
      toast.success('Template created!', { id: toastId });
    } catch (error) {
      toast.error(error.message || 'Failed to create template', { id: toastId });
    }
  };

  const handleAddEmailAccount = async () => {
    const token = getAuthToken();
    if (!token) {
      toast.error('Please log in to add email accounts');
      return;
    }

    const toastId = toast.loading('Adding email account...');
    try {
      const response = await fetch(`${BASE_URL}/email-accounts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(newEmailAccount),
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication failed. Please log in again.');
        }
        throw new Error('Failed to add email account');
      }

      const savedAccount = await response.json();
      setEmailAccounts([...emailAccounts, savedAccount]);
      setSelectedAccounts([...selectedAccounts, savedAccount.id]);
      setNewEmailAccount({
        email: '',
        password: '',
        sender_name: '',
        daily_limit: 0
      });
      toast.success('Email account added!', { id: toastId });
    } catch (error) {
      toast.error(error.message || 'Failed to add email account', { id: toastId });
    }
  };

  const handleAccountSelection = (accountId) => {
    if (selectedAccounts.includes(accountId)) {
      setSelectedAccounts(selectedAccounts.filter(id => id !== accountId));
    } else {
      setSelectedAccounts([...selectedAccounts, accountId]);
    }
  };

  const handleResetAccount = async (accountId) => {
    const token = getAuthToken();
    if (!token) {
      toast.error('Please log in to reset accounts');
      return;
    }

    const toastId = toast.loading('Resetting account...');
    try {
      const response = await fetch(`${BASE_URL}/email-accounts/${accountId}/reset`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication failed. Please log in again.');
        }
        throw new Error('Failed to reset account');
      }

      // Refresh accounts
      const accountsRes = await fetch(`${BASE_URL}/email-accounts`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!accountsRes.ok) {
        if (accountsRes.status === 401) {
          throw new Error('Authentication failed. Please log in again.');
        }
        throw new Error('Failed to refresh accounts');
      }

      const accountsData = await accountsRes.json();
      setEmailAccounts(accountsData);

      toast.success('Account reset successfully!', { id: toastId });
    } catch (error) {
      toast.error(error.message || 'Failed to reset account', { id: toastId });
    }
  };

  // Function to handle manual lead addition
  const handleAddLead = async () => {
    const token = getAuthToken();
    if (!token) {
      toast.error('Please log in to add leads');
      return;
    }

    // Basic validation
    if (!newLead.company_name && !newLead.email) {
      toast.error('Please provide at least a company name or email');
      return;
    }

    if (newLead.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(newLead.email)) {
      toast.error('Please enter a valid email address');
      return;
    }

    const toastId = toast.loading('Adding lead...');
    try {
      const response = await fetch(`${BASE_URL}/leads/manual`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(newLead),
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication failed. Please log in again.');
        }
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to add lead');
      }

      const savedLead = await response.json();
      
      // Update the total leads count
      setTotalLeads(prev => prev + 1);
      
      // Reset form and close modal
      setNewLead({
        company_name: '',
        contact_number: '',
        email: '',
        owner_name: ''
      });
      setShowAddLeadModal(false);
      
      toast.success('Lead added successfully!', { id: toastId });
    } catch (error) {
      toast.error(error.message || 'Failed to add lead', { id: toastId });
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Head>
        <title>Email Agent</title>
      </Head>
      <Toaster position="top-right" />

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex flex-col lg:flex-row gap-6">
          <div className="lg:w-1/3 space-y-6">
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
              <div className="p-5 border-b border-gray-200">
                <div className="flex justify-between items-center">
                  <h2 className="text-lg font-semibold text-gray-800">Available Leads</h2>
                  <button
                    onClick={() => setShowAddLeadModal(true)}
                    className="text-sm text-indigo-600"
                  >
                    + Add Lead
                  </button>
                </div>
                <div className="text-3xl font-bold text-indigo-600">{totalLeads}</div>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
              <div className="p-5 border-b border-gray-200">
                <div className="flex justify-between items-center">
                  <h2 className="text-lg font-semibold text-gray-800">Email Accounts</h2>
                  <button
                    onClick={() => setShowEmailAccountsModal(true)}
                    className="text-sm text-indigo-600"
                  >
                    Manage
                  </button>
                </div>
              </div>
              <div className="p-5 space-y-2">
                {emailAccounts.filter(acc => acc.is_active).slice(0, 3).map(account => (
                  <div key={account.id} className="flex items-center justify-between text-sm">
                    <span className="truncate">{account.email}</span>
                    <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">
                      {account.emails_sent_today} sent
                    </span>
                  </div>
                ))}
                {emailAccounts.filter(acc => acc.is_active).length > 3 && (
                  <div className="text-xs text-gray-500 text-center">
                    +{emailAccounts.filter(acc => acc.is_active).length - 3} more accounts
                  </div>
                )}
              </div>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
              <div className="p-5 border-b border-gray-200">
                <div className="flex justify-between items-center">
                  <h2 className="text-lg font-semibold text-gray-800">Distribution</h2>
                  <button
                    onClick={handleAddDistribution}
                    disabled={isSending}
                    className="text-sm text-indigo-600 disabled:opacity-50"
                  >
                    + Add
                  </button>
                </div>
              </div>
              <div className="p-5 space-y-4">
                {distribution.map((item, index) => (
                  <div key={index} className="grid grid-cols-12 gap-2 items-center">
                    <div className="col-span-5">
                      <select
                        value={item.templateId}
                        onChange={(e) => handleDistributionChange(index, 'templateId', e.target.value)}
                        disabled={isSending}
                        className="w-full rounded-md border-gray-300 shadow-sm text-sm disabled:opacity-50"
                      >
                        {templates.map(template => (
                          <option key={template.id} value={template.id}>{template.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="col-span-5 flex items-center">
                      <input
                        type="range"
                        min="0"
                        max={totalLeads}
                        value={item.count}
                        onChange={(e) => handleDistributionChange(index, 'count', e.target.value)}
                        disabled={isSending}
                        className="w-full h-2 bg-gray-200 rounded-lg cursor-pointer disabled:opacity-50"
                      />
                      <span className="ml-3 text-sm font-medium w-12">{item.count}</span>
                    </div>
                    <div className="col-span-2 flex justify-end">
                      {index > 0 && (
                        <button
                          onClick={() => setDistribution(distribution.filter((_, i) => i !== index))}
                          disabled={isSending}
                          className="text-gray-400 hover:text-red-500 disabled:opacity-50"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                <div className="pt-4 mt-4 border-t border-gray-100">
                  <div className="text-sm text-gray-600">
                    Total: <span className="font-medium">{emailsToSend}</span> emails
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
              <div className="p-5 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-800">Templates</h2>
              </div>
              <div className="p-5 grid grid-cols-1 gap-3">
                {templates.map(template => (
                  <div
                    key={template.id}
                    onClick={() => {
                      if (!isSending) {
                        setSelectedTemplate(template);
                        setEmailContent(template.content);
                      }
                    }}
                    className={`p-4 rounded-lg border cursor-pointer ${selectedTemplate?.id === template.id
                      ? 'border-indigo-500 bg-indigo-50'
                      : 'border-gray-200'
                      } ${isSending ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <div className="font-medium text-gray-800">{template.name}</div>
                    <div className="text-sm text-gray-500 mt-1 truncate">{template.subject}</div>
                  </div>
                ))}
                <button
                  onClick={() => setShowNewTemplateModal(true)}
                  disabled={isSending}
                  className="mt-2 p-3 rounded-lg border border-dashed border-gray-300 text-gray-600 disabled:opacity-50"
                >
                  + New Template
                </button>
              </div>
            </div>
          </div>

          <div className="lg:w-2/3">
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm h-full flex flex-col">
              <div className="p-5 border-b border-gray-200">
                <div className="flex justify-between items-center">
                  <h2 className="text-xl font-bold text-gray-800">Editor</h2>
                  <div className="flex gap-2">
                    <button
                      onClick={handleSendEmails}
                      disabled={emailsToSend === 0 || isSending || selectedAccounts.length === 0}
                      className="px-4 py-1.5 text-sm rounded-md text-white bg-indigo-600 disabled:opacity-70"
                    >
                      Send
                    </button>
                  </div>
                </div>
                <input
                  type="text"
                  value={selectedTemplate?.subject || ''}
                  onChange={(e) => setSelectedTemplate({ ...selectedTemplate, subject: e.target.value })}
                  disabled={isSending}
                  className="mt-2 w-full rounded-md border-gray-300 shadow-sm text-lg font-medium py-2 disabled:opacity-50"
                  placeholder="Subject"
                />
              </div>
              <div className="flex-1 p-5 overflow-auto">
                <div className="mt-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Attachments
                  </label>
                  <input
                    type="file"
                    onChange={handleFileUpload}
                    multiple
                    accept=".pdf"
                    disabled={isSending}
                    className="block w-full text-sm text-gray-500
                    file:mr-4 file:py-2 file:px-4
                    file:rounded-md file:border-0
                    file:text-sm file:font-semibold
                    file:bg-indigo-50 file:text-indigo-700
                    hover:file:bg-indigo-100
                    disabled:opacity-50"
                  />
                  {attachments.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {attachments.map((file, index) => (
                        <div key={index} className="flex items-center text-sm text-gray-600">
                          <span className="truncate">{file.filename}</span>
                          <button
                            onClick={() => setAttachments(attachments.filter((_, i) => i !== index))}
                            className="ml-2 text-red-500 hover:text-red-700"
                          >
                            &times;
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <textarea
                  value={emailContent}
                  onChange={(e) => setEmailContent(e.target.value)}
                  disabled={isSending}
                  className="w-full h-full rounded-md border-gray-300 shadow-sm text-sm font-mono min-h-[300px] disabled:opacity-50"
                  placeholder="Email content..."
                />
                <div className="mt-4 pt-4 border-t border-gray-100">
                  <p className="text-xs text-gray-500">
                    Variables: <span className="font-mono bg-gray-100 px-1 py-0.5 rounded">{"{First Name}"}</span>{' '}
                    <span className="font-mono bg-gray-100 px-1 py-0.5 rounded">{"{Company}"}</span>
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {showNewTemplateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold">New Template</h3>
              <button onClick={() => setShowNewTemplateModal(false)} className="text-gray-400">
                &times;
              </button>
            </div>
            <textarea
              rows={4}
              value={newTemplatePrompt}
              onChange={(e) => setNewTemplatePrompt(e.target.value)}
              className="w-full rounded-md border-gray-300 shadow-sm p-3 mb-4"
              placeholder="Describe your template..."
            />
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowNewTemplateModal(false)}
                className="px-4 py-2 text-sm rounded-md text-gray-700 bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={handleGenerateNewTemplate}
                disabled={!newTemplatePrompt}
                className="px-4 py-2 text-sm rounded-md text-white bg-indigo-600 disabled:opacity-50"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {showEmailAccountsModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-2xl w-full p-6 max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold">Manage Email Accounts</h3>
              <button onClick={() => setShowEmailAccountsModal(false)} className="text-gray-400">
                &times;
              </button>
            </div>

            <div className="mb-6 p-4 bg-gray-50 rounded-lg">
              <h4 className="font-medium mb-3">Add New Account</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <input
                  type="email"
                  placeholder="Email address"
                  value={newEmailAccount.email}
                  onChange={(e) => setNewEmailAccount({ ...newEmailAccount, email: e.target.value })}
                  className="rounded-md border-gray-300 shadow-sm p-2 text-sm"
                />
                <input
                  type="password"
                  placeholder="App password"
                  value={newEmailAccount.password}
                  onChange={(e) => setNewEmailAccount({ ...newEmailAccount, password: e.target.value })}
                  className="rounded-md border-gray-300 shadow-sm p-2 text-sm"
                />
                <input
                  type="text"
                  placeholder="Sender name (optional)"
                  value={newEmailAccount.sender_name}
                  onChange={(e) => setNewEmailAccount({ ...newEmailAccount, sender_name: e.target.value })}
                  className="rounded-md border-gray-300 shadow-sm p-2 text-sm"
                />
              </div>
              <button
                onClick={handleAddEmailAccount}
                disabled={!newEmailAccount.email || !newEmailAccount.password}
                className="mt-3 px-4 py-2 text-sm rounded-md text-white bg-indigo-600 disabled:opacity-50"
              >
                Add Account
              </button>
            </div>

            <div className="space-y-3">
              <h4 className="font-medium">Active Accounts</h4>
              {emailAccounts.filter(acc => acc.is_active).map(account => (
                <div key={account.id} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={selectedAccounts.includes(account.id)}
                      onChange={() => handleAccountSelection(account.id)}
                      className="rounded text-indigo-600"
                    />
                    <div>
                      <div className="font-medium">{account.email}</div>
                      <div className="text-sm text-gray-500">
                        {account.sender_name && `From: ${account.sender_name}`}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">
                      {account.emails_sent_today} sent
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setShowEmailAccountsModal(false)}
                className="px-4 py-2 text-sm rounded-md text-gray-700 bg-gray-100"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {showProgressModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold">Sending Emails</h3>
              <span className="text-sm text-gray-600">
                {currentEmail} of {totalEmails}
              </span>
            </div>

            <div className="w-full bg-gray-200 rounded-full h-2.5 mb-4">
              <div
                className="bg-indigo-600 h-2.5 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              ></div>
            </div>

            <div className="flex justify-between text-sm text-gray-600 mb-2">
              <span>Progress:</span>
              <span>{progress}%</span>
            </div>

            <div className="text-sm text-gray-500">
              {progress < 100 ? (
                <p>Sending emails using {selectedAccounts.length} accounts... Please don't close this window.</p>
              ) : (
                <p className="text-green-600">All emails sent successfully!</p>
              )}
            </div>

            {progress === 100 && (
              <div className="mt-4 flex justify-end">
                <button
                  onClick={() => setShowProgressModal(false)}
                  className="px-4 py-2 text-sm rounded-md text-white bg-indigo-600"
                >
                  Close
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {showAddLeadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold">Add New Lead</h3>
              <button 
                onClick={() => setShowAddLeadModal(false)} 
                className="text-gray-400 hover:text-gray-600"
              >
                &times;
              </button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Company Name
                </label>
                <input
                  type="text"
                  value={newLead.company_name}
                  onChange={(e) => setNewLead({...newLead, company_name: e.target.value})}
                  className="w-full rounded-md border-gray-300 shadow-sm p-2 text-sm"
                  placeholder="Enter company name"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Contact Person
                </label>
                <input
                  type="text"
                  value={newLead.owner_name}
                  onChange={(e) => setNewLead({...newLead, owner_name: e.target.value})}
                  className="w-full rounded-md border-gray-300 shadow-sm p-2 text-sm"
                  placeholder="Enter contact person name"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email Address
                </label>
                <input
                  type="email"
                  value={newLead.email}
                  onChange={(e) => setNewLead({...newLead, email: e.target.value})}
                  className="w-full rounded-md border-gray-300 shadow-sm p-2 text-sm"
                  placeholder="Enter email address"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Phone Number
                </label>
                <input
                  type="tel"
                  value={newLead.contact_number}
                  onChange={(e) => setNewLead({...newLead, contact_number: e.target.value})}
                  className="w-full rounded-md border-gray-300 shadow-sm p-2 text-sm"
                  placeholder="Enter phone number"
                />
              </div>
            </div>
            
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setShowAddLeadModal(false)}
                className="px-4 py-2 text-sm rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={handleAddLead}
                disabled={!newLead.company_name && !newLead.email}
                className="px-4 py-2 text-sm rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
              >
                Add Lead
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}