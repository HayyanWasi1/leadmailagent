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

  const handleSendEmails = async () => {
    setIsSending(true);
    const toastId = toast.loading(`Sending ${emailsToSend} emails...`);
    
    try {
      const leadsRes = await fetch('http://127.0.0.1:8000/leads?limit=1000');
      const unsentLeads = await leadsRes.json();
      
      const leadsToSend = [];
      let remainingLeads = [...unsentLeads];
      
      for (const dist of distribution) {
        if (dist.count <= 0) continue;
        const templateLeads = remainingLeads.splice(0, dist.count);
        leadsToSend.push(...templateLeads.map(lead => ({
          lead_id: lead.id,
          template_id: dist.templateId
        })));
      }
      
      if (leadsToSend.length === 0) {
        throw new Error('No unsent leads available to send');
      }
      
      const templateGroups = {};
      leadsToSend.forEach(item => {
        if (!templateGroups[item.template_id]) {
          templateGroups[item.template_id] = [];
        }
        templateGroups[item.template_id].push(item.lead_id);
      });
      
      const sendPromises = Object.entries(templateGroups).map(([templateId, leadIds]) => 
        fetch('http://127.0.0.1:8000/send-emails', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            template_id: templateId,
            lead_ids: leadIds
          }),
        })
      );
      
      await Promise.all(sendPromises);
      
      const verifyRes = await fetch('http://127.0.0.1:8000/leads/count');
      const countData = await verifyRes.json();
      setTotalLeads(countData.count);
      
      toast.success(`Successfully sent ${leadsToSend.length} emails`, { id: toastId });
    } catch (error) {
      toast.error(`Failed to send emails: ${error.message}`, { id: toastId });
    } finally {
      setIsSending(false);
    }
  };

  const handleRephrase = () => {
    setEmailContent(`Hi {First Name},\n\nAfter reviewing your work at {Company}, I wanted to connect about potential collaboration.\n\nBest regards,\nYour Name`);
    toast.success('Email rephrased');
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
                    onClick={() => !isSending && setSelectedTemplate(template)}
                    className={`p-4 rounded-lg border cursor-pointer ${
                      selectedTemplate?.id === template.id 
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
                  onChange={(e) => setSelectedTemplate({...selectedTemplate, subject: e.target.value})}
                  disabled={isSending}
                  className="mt-2 w-full rounded-md border-gray-300 shadow-sm text-lg font-medium py-2 disabled:opacity-50"
                  placeholder="Subject"
                />
              </div>
              <div className="flex-1 p-5 overflow-auto">
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
    </div>
  );
}