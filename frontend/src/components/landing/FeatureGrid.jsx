import React from 'react';
import { FileText, Shield, Zap, Search } from 'lucide-react';

export const FeatureGrid = () => {
  const features = [
    {
      icon: <FileText size={20} style={{ color: '#38bdf8' }} />,
      title: 'Chat with Any Document',
      description: 'Drag and drop PDFs, docs, or web links to summarize key points, analyze data, and ask questions.',
    },
    {
      icon: <Search size={20} style={{ color: '#818cf8' }} />,
      title: 'Deep Multi-Step Research',
      description: 'Generates structured, academic-grade research reports by gathering live web and paper insights.',
    },
    {
      icon: <Shield size={20} style={{ color: '#34d399' }} />,
      title: 'Private & Secure Account',
      description: 'Your workspace and uploaded documents are encrypted, isolated, and strictly protected.',
    },
    {
      icon: <Zap size={20} style={{ color: '#fbbf24' }} />,
      title: 'Lightning Fast Responses',
      description: 'Optimized intelligence models deliver instant answers without lag or unnecessary fluff.',
    },
  ];

  return (
    <section className="features-section">
      <div className="section-header">
        <h2>Everything You Need to Work Smarter</h2>
        <p>Built for speed, accuracy, and effortless productivity</p>
      </div>

      <div className="feature-cards">
        {features.map((feat, idx) => (
          <div key={idx} className="feature-item">
            <div className="feature-item-header">
              {feat.icon}
              <h4>{feat.title}</h4>
            </div>
            <p>{feat.description}</p>
          </div>
        ))}
      </div>
    </section>
  );
};
