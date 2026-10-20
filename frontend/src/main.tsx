import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import '@xyflow/react/dist/style.css';
import './style.css';
import './session.css';
import './readability.css';
import './qwenw.css';
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
