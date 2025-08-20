'use client';
import { useState, useEffect } from 'react';
import Head from 'next/head';
import toast, { Toaster } from 'react-hot-toast';

export default function SendEmails() {
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

  useEffect(() => {
    const fetchData = async () => {
      try {
        const templatesRes = await fetch('http://127.0.0.1:8000/templates');
        const templatesData = await templatesRes.json();
        setTemplates(templatesData);
        setSelectedTemplate(templatesData[0]);
        setEmailContent(templatesData[0]?.content || '');
        setDistribution([{ templateId: templatesData[0]?.id || '', count: 0 }]);

        const countRes = await fetch('http://127.0.0.1:8000/leads/count');
        const countData = await countRes.json();
        setTotalLeads(countData.count);

        setIsLoading(false);
      } catch (error) {
        toast.error('Failed to load data');
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
        // This gets the base64 content after the comma
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

  const handleSendEmails = async () => {
    setIsSending(true);
    setShowProgressModal(true);
    setProgress(0);
    setCurrentEmail(0);

    try {
      const leadsRes = await fetch('http://127.0.0.1:8000/leads?limit=1000');
      const unsentLeads = await leadsRes.json();

      const leadsToSend = [];
      let remainingLeads = [...unsentLeads];

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
        throw new Error('No unsent leads available to send');
      }

      setTotalEmails(leadsToSend.length);

      // Sequential send with 15s delay
      for (let i = 0; i < leadsToSend.length; i++) {
        const { lead_id, template_id } = leadsToSend[i];

        await fetch('http://127.0.0.1:8000/send-emails', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            template_id,
            lead_ids: [lead_id],
            attachments: attachments.length > 0 ? attachments : undefined
          }),
        });

        setCurrentEmail(i + 1);
        setProgress(Math.round(((i + 1) / leadsToSend.length) * 100));

        if (i < leadsToSend.length - 1) {
          await new Promise((resolve) => setTimeout(resolve, 15000));
        }
      }

      const verifyRes = await fetch('http://127.0.0.1:8000/leads/count');
      const countData = await verifyRes.json();
      setTotalLeads(countData.count);

      toast.success(`Successfully sent ${leadsToSend.length} emails`);
    } catch (error) {
      toast.error(`Failed to send emails: ${error.message}`);
    } finally {
      setIsSending(false);
      setTimeout(() => {
        setShowProgressModal(false);
      }, 1000); // Give a small delay so user can see 100% completion
    }
  };

  const handleRephrase = async () => {
    if (!selectedTemplate) return;

    const toastId = toast.loading('Rephrasing email...');
    try {
      const response = await fetch('http://127.0.0.1:8000/rephrase-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_id: selectedTemplate.id,
          content: emailContent
        }),
      });

      const result = await response.json();

      if (result.success) {
        setEmailContent(result.rephrased_content);
        // Update the selected template with the new content
        setSelectedTemplate(result.template);
        // Update the templates list
        setTemplates(templates.map(t =>
          t.id === result.template.id ? result.template : t
        ));
        toast.success('Email rephrased and saved!', { id: toastId });
      } else {
        throw new Error('Rephrasing failed');
      }
    } catch (error) {
      toast.error('Failed to rephrase email', { id: toastId });
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
    const toastId = toast.loading('Creating template...');
    try {
      const response = await fetch('http://127.0.0.1:8000/templates', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: `Custom ${templates.length + 1}`,
          subject: `Regarding ${newTemplatePrompt.substring(0, 20)}`,
          content: `Hi {First Name},\n\n${newTemplatePrompt}\n\nBest,\nYour Team`
        }),
      });

      const savedTemplate = await response.json();
      setTemplates([...templates, savedTemplate]);
      setSelectedTemplate(savedTemplate);
      setEmailContent(savedTemplate.content);
      setShowNewTemplateModal(false);
      setNewTemplatePrompt('');
      toast.success('Template created!', { id: toastId });
    } catch (error) {
      toast.error('Failed to create template', { id: toastId });
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
                <h2 className="text-lg font-semibold text-gray-800">Available Leads</h2>
                <div className="text-3xl font-bold text-indigo-600">{totalLeads}</div>
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
                      onClick={handleRephrase}
                      disabled={isSending}
                      className="px-3 py-1.5 text-sm rounded-md text-gray-700 bg-gray-100 disabled:opacity-50"
                    >
                      Rephrase
                    </button>
                    <button
                      onClick={handleSendEmails}
                      disabled={emailsToSend === 0 || isSending}
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
                <p>Sending emails... Please don't close this window.</p>
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
    </div>
  );
}